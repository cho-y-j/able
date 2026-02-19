import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RecipeBuilderPage from "@/app/dashboard/recipes/[id]/page";
import api from "@/lib/api";

jest.mock("@/lib/api");
jest.mock("@/lib/useStockSearch", () => ({
  useStockSearch: () => ({ results: [], loading: false }),
  __esModule: true,
}));
const mockedApi = api as jest.Mocked<typeof api>;

const mockPush = jest.fn();
const mockReplace = jest.fn();
let mockParams = { id: "new" };

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
    back: jest.fn(),
    prefetch: jest.fn(),
  }),
  useParams: () => mockParams,
  usePathname: () => "/dashboard/recipes/new",
  useSearchParams: () => new URLSearchParams(),
}));

const mockExistingRecipe = {
  id: "r1",
  name: "MACD + RSI 보수적",
  description: "보수적 매매 전략",
  signal_config: {
    combinator: "AND",
    min_agree: 2,
    signals: [
      { type: "recommended", strategy_type: "macd_crossover", params: {}, weight: 1.0 },
    ],
  },
  custom_filters: {},
  stock_codes: ["005930"],
  risk_config: { stop_loss: 3, take_profit: 5, position_size: 10 },
  is_active: false,
  is_template: false,
  created_at: "2026-02-01T00:00:00Z",
  updated_at: "2026-02-01T00:00:00Z",
};

describe("RecipeBuilderPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockParams = { id: "new" };
  });

  it("renders new recipe form", () => {
    render(<RecipeBuilderPage />);

    expect(screen.getByText("새 레시피 만들기")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("예: MACD + RSI 보수적 전략")).toBeInTheDocument();
    expect(screen.getByText("저장")).toBeInTheDocument();
  });

  it("shows 4 step navigation tabs", () => {
    render(<RecipeBuilderPage />);

    // Step tabs are button elements with step labels
    const stepButtons = screen.getAllByRole("button").filter(
      (btn) => btn.textContent?.includes("시그널") || btn.textContent?.includes("파라미터") ||
        btn.textContent?.includes("필터") || btn.textContent?.includes("리스크")
    );
    expect(stepButtons.length).toBeGreaterThanOrEqual(4);
  });

  it("navigates between steps", async () => {
    const user = userEvent.setup();
    render(<RecipeBuilderPage />);

    // Click step 2 (파라미터 조정) by finding the step button specifically
    const stepButtons = screen.getAllByRole("button");
    const paramStep = stepButtons.find((b) => b.textContent?.includes("파라미터 조정"));
    expect(paramStep).toBeTruthy();
    await user.click(paramStep!);
    expect(screen.getByText(/선택된 시그널이 없습니다/)).toBeInTheDocument();

    // Click step 3
    const filterStep = stepButtons.find((b) => b.textContent?.includes("필터 + 종목"));
    await user.click(filterStep!);
    expect(screen.getByText("커스텀 필터 + 대상 종목")).toBeInTheDocument();

    // Click step 4
    const riskStep = stepButtons.find((b) => b.textContent?.includes("리스크 + 백테스트"));
    await user.click(riskStep!);
    expect(screen.getByText("리스크 설정 + 백테스트")).toBeInTheDocument();
  });

  it("prev/next navigation buttons work", async () => {
    const user = userEvent.setup();
    render(<RecipeBuilderPage />);

    // "이전" should be disabled on step 0
    const prevButton = screen.getByText(/이전/);
    expect(prevButton).toBeDisabled();

    // Click "다음"
    await user.click(screen.getByText(/다음/));
    // Now on step 1 — prev should be enabled
    expect(screen.getByText(/이전/)).not.toBeDisabled();
  });

  it("save button is disabled without name", () => {
    render(<RecipeBuilderPage />);

    const saveButton = screen.getByText("저장");
    expect(saveButton).toBeDisabled();
  });

  it("creates a new recipe on save", async () => {
    const user = userEvent.setup();
    mockedApi.post.mockResolvedValue({ data: { id: "new-recipe-1" } });

    render(<RecipeBuilderPage />);

    // Type name
    const nameInput = screen.getByPlaceholderText("예: MACD + RSI 보수적 전략");
    await user.type(nameInput, "테스트 레시피");

    // Save
    await user.click(screen.getByText("저장"));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith(
        "/recipes",
        expect.objectContaining({
          name: "테스트 레시피",
          signal_config: expect.objectContaining({
            combinator: "AND",
          }),
        })
      );
    });
  });

  it("loads existing recipe in edit mode", async () => {
    mockParams = { id: "r1" };
    mockedApi.get.mockResolvedValue({ data: mockExistingRecipe });

    await act(async () => {
      render(<RecipeBuilderPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("레시피 편집")).toBeInTheDocument();
    });

    expect(screen.getByDisplayValue("MACD + RSI 보수적")).toBeInTheDocument();
    expect(screen.getByDisplayValue("보수적 매매 전략")).toBeInTheDocument();
    expect(screen.getByText("자동매매 활성화")).toBeInTheDocument();
  });

  it("updates existing recipe on save", async () => {
    const user = userEvent.setup();
    mockParams = { id: "r1" };
    mockedApi.get.mockResolvedValue({ data: mockExistingRecipe });
    mockedApi.put.mockResolvedValue({ data: mockExistingRecipe });

    await act(async () => {
      render(<RecipeBuilderPage />);
    });

    await waitFor(() => {
      expect(screen.getByDisplayValue("MACD + RSI 보수적")).toBeInTheDocument();
    });

    await user.click(screen.getByText("저장"));

    await waitFor(() => {
      expect(mockedApi.put).toHaveBeenCalledWith(
        "/recipes/r1",
        expect.objectContaining({ name: "MACD + RSI 보수적" })
      );
    });
  });

  it("activates recipe and navigates back", async () => {
    const user = userEvent.setup();
    mockParams = { id: "r1" };
    mockedApi.get.mockResolvedValue({ data: mockExistingRecipe });
    mockedApi.post.mockResolvedValue({ data: {} });

    await act(async () => {
      render(<RecipeBuilderPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("자동매매 활성화")).toBeInTheDocument();
    });

    await user.click(screen.getByText("자동매매 활성화"));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith("/recipes/r1/activate");
    });
  });

  it("shows error alert when load fails", async () => {
    mockParams = { id: "r1" };
    mockedApi.get.mockRejectedValue(new Error("Not found"));

    await act(async () => {
      render(<RecipeBuilderPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("레시피를 불러오지 못했습니다")).toBeInTheDocument();
    });
  });

  it("shows success alert when save succeeds", async () => {
    const user = userEvent.setup();
    mockedApi.post.mockResolvedValue({ data: { id: "new-1" } });

    render(<RecipeBuilderPage />);

    await user.type(screen.getByPlaceholderText("예: MACD + RSI 보수적 전략"), "새 전략");
    await user.click(screen.getByText("저장"));

    await waitFor(() => {
      expect(screen.getByText("레시피가 생성되었습니다")).toBeInTheDocument();
    });
  });

  it("shows loading skeleton for existing recipe", () => {
    mockParams = { id: "r1" };
    mockedApi.get.mockReturnValue(new Promise(() => {}));

    render(<RecipeBuilderPage />);
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("navigates back to list on back button click", async () => {
    const user = userEvent.setup();
    render(<RecipeBuilderPage />);

    await user.click(screen.getByText(/레시피 목록/));
    expect(mockPush).toHaveBeenCalledWith("/dashboard/recipes");
  });
});
