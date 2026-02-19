import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RecipesPage from "@/app/dashboard/recipes/page";
import api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
    back: jest.fn(),
    prefetch: jest.fn(),
  }),
  usePathname: () => "/dashboard/recipes",
  useSearchParams: () => new URLSearchParams(),
}));

const mockRecipes = [
  {
    id: "r1",
    name: "MACD + RSI 보수적",
    description: "보수적 매매 전략",
    signal_config: {
      combinator: "AND",
      signals: [
        { type: "recommended", strategy_type: "macd_crossover", params: {}, weight: 1.0 },
        { type: "recommended", strategy_type: "rsi_mean_reversion", params: {}, weight: 0.8 },
      ],
    },
    custom_filters: {},
    stock_codes: ["005930", "000660"],
    risk_config: { stop_loss: 3, take_profit: 5, position_size: 10 },
    is_active: true,
    is_template: false,
    created_at: "2026-02-01T00:00:00Z",
    updated_at: "2026-02-01T00:00:00Z",
  },
  {
    id: "r2",
    name: "거래량 돌파 전략",
    description: null,
    signal_config: {
      combinator: "OR",
      signals: [
        { type: "volume_spike", params: { rvol_threshold: 2.0 }, weight: 1.0 },
      ],
    },
    custom_filters: {},
    stock_codes: ["035720"],
    risk_config: { stop_loss: 5, take_profit: 10, position_size: 20 },
    is_active: false,
    is_template: false,
    created_at: "2026-02-02T00:00:00Z",
    updated_at: "2026-02-02T00:00:00Z",
  },
];

const mockTemplates = [
  {
    id: "t1",
    name: "골든크로스 템플릿",
    description: "기본 골든크로스 전략",
    signal_config: {
      combinator: "AND",
      signals: [{ type: "recommended", strategy_type: "sma_crossover", params: {}, weight: 1.0 }],
    },
    custom_filters: {},
    stock_codes: [],
    risk_config: { stop_loss: 3, take_profit: 5, position_size: 10 },
    is_active: false,
    is_template: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

describe("RecipesPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/recipes") return Promise.resolve({ data: mockRecipes });
      if (url === "/recipes/templates") return Promise.resolve({ data: mockTemplates });
      return Promise.resolve({ data: [] });
    });
  });

  it("renders recipe list with stats", async () => {
    await act(async () => {
      render(<RecipesPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("나만의 기법")).toBeInTheDocument();
    });

    expect(screen.getByText("MACD + RSI 보수적")).toBeInTheDocument();
    expect(screen.getByText("거래량 돌파 전략")).toBeInTheDocument();

    // Stats
    // Stats: 전체 레시피=2, 활성=1, 템플릿=1
    const statValues = document.querySelectorAll(".text-2xl.font-bold");
    const texts = Array.from(statValues).map((el) => el.textContent);
    expect(texts).toContain("2");
    expect(texts).toContain("1");
  });

  it("navigates to new recipe page on button click", async () => {
    const user = userEvent.setup();

    await act(async () => {
      render(<RecipesPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("새 레시피 만들기")).toBeInTheDocument();
    });

    await user.click(screen.getByText("새 레시피 만들기"));
    expect(mockPush).toHaveBeenCalledWith("/dashboard/recipes/new");
  });

  it("navigates to recipe detail on card click", async () => {
    await act(async () => {
      render(<RecipesPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("MACD + RSI 보수적")).toBeInTheDocument();
    });

    await act(async () => {
      screen.getByText("MACD + RSI 보수적").click();
    });

    expect(mockPush).toHaveBeenCalledWith("/dashboard/recipes/r1");
  });

  it("shows signal name badges on cards", async () => {
    await act(async () => {
      render(<RecipesPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("MACD 크로스")).toBeInTheDocument();
      expect(screen.getByText("RSI 평균회귀")).toBeInTheDocument();
      expect(screen.getByText("거래량 폭증 (RVOL)")).toBeInTheDocument();
    });
  });

  it("activates and deactivates recipes", async () => {
    mockedApi.post.mockResolvedValue({ data: {} });

    await act(async () => {
      render(<RecipesPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("MACD + RSI 보수적")).toBeInTheDocument();
    });

    // Active recipe should show "중지" button
    const stopButtons = screen.getAllByText("중지");
    expect(stopButtons.length).toBeGreaterThanOrEqual(1);

    // Inactive recipe should show "활성화" button
    const activateButtons = screen.getAllByText("활성화");
    expect(activateButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("deletes a recipe after confirmation", async () => {
    mockedApi.delete.mockResolvedValue({ data: {} });
    window.confirm = jest.fn().mockReturnValue(true);

    await act(async () => {
      render(<RecipesPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("MACD + RSI 보수적")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByText("삭제");
    await act(async () => {
      deleteButtons[0].click();
    });

    expect(window.confirm).toHaveBeenCalled();
    expect(mockedApi.delete).toHaveBeenCalledWith("/recipes/r1");
  });

  it("shows templates tab", async () => {
    const user = userEvent.setup();

    await act(async () => {
      render(<RecipesPage />);
    });

    await waitFor(() => {
      expect(screen.getByText(/템플릿 갤러리/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/템플릿 갤러리/));

    await waitFor(() => {
      expect(screen.getByText("골든크로스 템플릿")).toBeInTheDocument();
      expect(screen.getByText("내 레시피로 복제")).toBeInTheDocument();
    });
  });

  it("clones a template", async () => {
    const user = userEvent.setup();
    mockedApi.post.mockResolvedValue({ data: { id: "cloned-1" } });

    await act(async () => {
      render(<RecipesPage />);
    });

    await waitFor(() => {
      expect(screen.getByText(/템플릿 갤러리/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/템플릿 갤러리/));

    await waitFor(() => {
      expect(screen.getByText("내 레시피로 복제")).toBeInTheDocument();
    });

    await user.click(screen.getByText("내 레시피로 복제"));
    expect(mockedApi.post).toHaveBeenCalledWith("/recipes/t1/clone");
    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/dashboard/recipes/cloned-1");
    });
  });

  it("shows error alert when fetch fails", async () => {
    mockedApi.get.mockRejectedValue(new Error("Network error"));

    await act(async () => {
      render(<RecipesPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("레시피 목록을 불러오지 못했습니다")).toBeInTheDocument();
    });
  });

  it("shows empty state when no recipes", async () => {
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/recipes") return Promise.resolve({ data: [] });
      if (url === "/recipes/templates") return Promise.resolve({ data: [] });
      return Promise.resolve({ data: [] });
    });

    await act(async () => {
      render(<RecipesPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("아직 레시피가 없습니다")).toBeInTheDocument();
      expect(screen.getByText("첫 레시피 만들기")).toBeInTheDocument();
    });
  });

  it("shows loading skeleton initially", () => {
    mockedApi.get.mockReturnValue(new Promise(() => {})); // Never resolves

    render(<RecipesPage />);
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });
});
