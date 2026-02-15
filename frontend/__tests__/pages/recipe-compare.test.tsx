import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RecipeComparePage from "@/app/dashboard/recipes/compare/page";
import api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    back: jest.fn(),
    prefetch: jest.fn(),
  }),
  usePathname: () => "/dashboard/recipes/compare",
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
}));

const mockRecipes = [
  {
    id: "r1",
    name: "Momentum Recipe",
    description: "Momentum",
    signal_config: { combinator: "AND", signals: [{ type: "momentum", params: {}, weight: 1 }] },
    custom_filters: {},
    stock_codes: ["005930"],
    risk_config: {},
    is_active: false,
    is_template: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "r2",
    name: "RSI Recipe",
    description: "RSI-based",
    signal_config: { combinator: "OR", signals: [{ type: "rsi", params: {}, weight: 1 }, { type: "macd", params: {}, weight: 1 }] },
    custom_filters: {},
    stock_codes: ["035420"],
    risk_config: {},
    is_active: false,
    is_template: false,
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
  {
    id: "r3",
    name: "MACD Recipe",
    description: "MACD strategy",
    signal_config: { combinator: "AND", signals: [{ type: "macd", params: {}, weight: 1 }] },
    custom_filters: {},
    stock_codes: [],
    risk_config: {},
    is_active: false,
    is_template: false,
    created_at: "2026-01-03T00:00:00Z",
    updated_at: "2026-01-03T00:00:00Z",
  },
];

const mockBacktestResult = (name: string, score: number) => ({
  data: {
    composite_score: score,
    grade: score >= 70 ? "A" : "B",
    metrics: {
      total_return: 0.25,
      annual_return: 0.15,
      sharpe_ratio: 1.5,
      max_drawdown: -0.1,
      win_rate: 60,
      total_trades: 50,
      sortino_ratio: 2.0,
      profit_factor: 1.8,
      calmar_ratio: 1.5,
    },
    equity_curve: [
      { date: "2024-01-01", value: 0 },
      { date: "2024-06-01", value: 10 },
      { date: "2024-12-31", value: 25 },
    ],
    trade_log: [],
  },
});

describe("RecipeComparePage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders recipe checkboxes", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockRecipes });

    await act(async () => {
      render(<RecipeComparePage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Momentum Recipe")).toBeInTheDocument();
      expect(screen.getByText("RSI Recipe")).toBeInTheDocument();
      expect(screen.getByText("MACD Recipe")).toBeInTheDocument();
    });

    // All checkboxes unchecked
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(3);
    checkboxes.forEach((cb) => expect(cb).not.toBeChecked());
  });

  it("disables compare button when fewer than 2 selected", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockRecipes });

    await act(async () => {
      render(<RecipeComparePage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Momentum Recipe")).toBeInTheDocument();
    });

    const btn = screen.getByRole("button", { name: /Run Comparison/i });
    expect(btn).toBeDisabled();

    // Select one checkbox
    const user = userEvent.setup();
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]);

    // Still disabled (need stock code too)
    expect(btn).toBeDisabled();
  });

  it("disables compare button when stock code is empty", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockRecipes });

    await act(async () => {
      render(<RecipeComparePage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Momentum Recipe")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]);
    await user.click(checkboxes[1]);

    // 2 selected but no stock code
    const btn = screen.getByRole("button", { name: /Run Comparison/i });
    expect(btn).toBeDisabled();
  });

  it("runs comparison and shows ranking", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockRecipes });
    mockedApi.post
      .mockResolvedValueOnce(mockBacktestResult("Momentum Recipe", 78))
      .mockResolvedValueOnce(mockBacktestResult("RSI Recipe", 65));

    await act(async () => {
      render(<RecipeComparePage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Momentum Recipe")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]);
    await user.click(checkboxes[1]);

    const input = screen.getByPlaceholderText(/stock code/i);
    await user.type(input, "005930");

    const btn = screen.getByRole("button", { name: /Run Comparison/i });
    expect(btn).not.toBeDisabled();
    await user.click(btn);

    await waitFor(() => {
      expect(screen.getByText("#1")).toBeInTheDocument();
      expect(screen.getByText("#2")).toBeInTheDocument();
    });

    // API was called for both recipes
    expect(mockedApi.post).toHaveBeenCalledTimes(2);
    expect(mockedApi.post).toHaveBeenCalledWith("/recipes/r1/backtest", {
      stock_code: "005930",
    });
    expect(mockedApi.post).toHaveBeenCalledWith("/recipes/r2/backtest", {
      stock_code: "005930",
    });
  });

  it("shows metrics table when switching tab", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockRecipes });
    mockedApi.post
      .mockResolvedValueOnce(mockBacktestResult("Momentum Recipe", 78))
      .mockResolvedValueOnce(mockBacktestResult("RSI Recipe", 65));

    await act(async () => {
      render(<RecipeComparePage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Momentum Recipe")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]);
    await user.click(checkboxes[1]);
    await user.type(screen.getByPlaceholderText(/stock code/i), "005930");
    await user.click(screen.getByRole("button", { name: /Run Comparison/i }));

    await waitFor(() => {
      expect(screen.getByText("#1")).toBeInTheDocument();
    });

    // Switch to metrics tab
    await user.click(screen.getByRole("button", { name: /Performance Metrics/i }));

    await waitFor(() => {
      expect(screen.getByText("Total Return")).toBeInTheDocument();
      expect(screen.getByText("Win Rate")).toBeInTheDocument();
    });
  });

  it("shows error when comparison fails", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockRecipes });
    mockedApi.post.mockRejectedValueOnce({
      response: { data: { detail: "No data available" } },
    });

    await act(async () => {
      render(<RecipeComparePage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Momentum Recipe")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]);
    await user.click(checkboxes[1]);
    await user.type(screen.getByPlaceholderText(/stock code/i), "005930");
    await user.click(screen.getByRole("button", { name: /Run Comparison/i }));

    await waitFor(() => {
      expect(screen.getByText("No data available")).toBeInTheDocument();
    });
  });
});
