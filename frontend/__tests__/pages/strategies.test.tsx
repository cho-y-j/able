import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import StrategiesPage from "@/app/dashboard/strategies/page";
import api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

// Capture the router.push mock so we can assert on it
const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
    back: jest.fn(),
    prefetch: jest.fn(),
  }),
  usePathname: () => "/dashboard/strategies",
  useSearchParams: () => new URLSearchParams(),
}));

const mockStrategies = [
  {
    id: "s1",
    name: "MACD Crossover",
    stock_code: "005930",
    stock_name: "Samsung",
    strategy_type: "momentum",
    composite_score: 85.5,
    validation_results: {
      backtest: { total_return: 32.5, sharpe_ratio: 1.85, max_drawdown: -12.3 },
    },
    status: "active",
    is_auto_trading: true,
    created_at: "2025-01-01T00:00:00Z",
  },
  {
    id: "s2",
    name: "RSI Mean Reversion",
    stock_code: "035720",
    stock_name: "Kakao",
    strategy_type: "mean_reversion",
    composite_score: 62.3,
    validation_results: null,
    status: "validated",
    is_auto_trading: false,
    created_at: "2025-01-02T00:00:00Z",
  },
  {
    id: "s3",
    name: "Bollinger Bounce",
    stock_code: "000660",
    stock_name: "SK Hynix",
    strategy_type: "volatility",
    composite_score: 35.0,
    validation_results: null,
    status: "draft",
    is_auto_trading: false,
    created_at: "2025-01-03T00:00:00Z",
  },
];

describe("StrategiesPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();

    // Default: /strategies returns empty array
    mockedApi.get.mockResolvedValue({ data: [] });
    mockedApi.post.mockResolvedValue({ data: { job_id: "job-123" } });
    mockedApi.delete.mockResolvedValue({ data: {} });

    window.alert = jest.fn();
    window.confirm = jest.fn(() => true);
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("renders page title and AI search section", async () => {
    await act(async () => {
      render(<StrategiesPage />);
    });

    expect(screen.getByText("Trading Strategies")).toBeInTheDocument();
    expect(screen.getByText("AI Strategy Search")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Stock code or name (e.g., 005930, 삼성전자)")
    ).toBeInTheDocument();
    expect(screen.getByText("Search Strategy")).toBeInTheDocument();
  });

  it("shows empty strategies message when no strategies exist", async () => {
    await act(async () => {
      render(<StrategiesPage />);
    });

    expect(
      screen.getByText(
        "No strategies yet. Use AI Strategy Search above to find optimal strategies."
      )
    ).toBeInTheDocument();
  });

  it("fetches and displays strategies list with correct count", async () => {
    mockedApi.get.mockResolvedValue({ data: mockStrategies });

    await act(async () => {
      render(<StrategiesPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("My Strategies (3)")).toBeInTheDocument();
    });

    expect(screen.getByText("MACD Crossover")).toBeInTheDocument();
    expect(screen.getByText("RSI Mean Reversion")).toBeInTheDocument();
    expect(screen.getByText("Bollinger Bounce")).toBeInTheDocument();
  });

  it("renders GradeBadge with correct grades for different scores", async () => {
    mockedApi.get.mockResolvedValue({ data: mockStrategies });

    await act(async () => {
      render(<StrategiesPage />);
    });

    await waitFor(() => {
      // score 85.5 => grade "A"
      expect(screen.getByText("A")).toBeInTheDocument();
      // score 62.3 => grade "B"
      expect(screen.getByText("B")).toBeInTheDocument();
      // score 35.0 => grade "D"
      expect(screen.getByText("D")).toBeInTheDocument();
    });
  });

  it("shows backtest metrics for strategies that have them", async () => {
    mockedApi.get.mockResolvedValue({ data: mockStrategies });

    await act(async () => {
      render(<StrategiesPage />);
    });

    await waitFor(() => {
      // Strategy s1 has backtest data
      expect(screen.getByText("+32.5%")).toBeInTheDocument();
      expect(screen.getByText("Sharpe: 1.85")).toBeInTheDocument();
      expect(screen.getByText("MDD: -12.3%")).toBeInTheDocument();
    });
  });

  it("shows composite score for strategies without backtest data", async () => {
    mockedApi.get.mockResolvedValue({ data: mockStrategies });

    await act(async () => {
      render(<StrategiesPage />);
    });

    await waitFor(() => {
      // Strategy s2 has no backtest but has score 62.3
      expect(screen.getByText("Score: 62.3")).toBeInTheDocument();
    });
  });

  it("displays correct status badges", async () => {
    mockedApi.get.mockResolvedValue({ data: mockStrategies });

    await act(async () => {
      render(<StrategiesPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("active")).toBeInTheDocument();
      expect(screen.getByText("validated")).toBeInTheDocument();
      expect(screen.getByText("draft")).toBeInTheDocument();
    });
  });

  it("submits search and shows progress bar during polling", async () => {
    jest.useRealTimers();
    const user = userEvent.setup();

    mockedApi.get.mockResolvedValue({ data: [] });
    mockedApi.post.mockResolvedValue({ data: { job_id: "job-abc" } });

    await act(async () => {
      render(<StrategiesPage />);
    });

    const input = screen.getByPlaceholderText(
      "Stock code or name (e.g., 005930, 삼성전자)"
    );
    await user.type(input, "005930");
    await user.click(screen.getByText("Search Strategy"));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith("/strategies/search", {
        stock_code: "005930",
        date_range_start: "2024-01-01",
        date_range_end: "2025-12-31",
        optimization_method: "grid",
      });
    });

    // After posting, a progress bar should appear (status "running")
    await waitFor(() => {
      expect(screen.getByText("0%")).toBeInTheDocument();
    });
  });

  it("disables search button when stock code is empty", async () => {
    await act(async () => {
      render(<StrategiesPage />);
    });

    const button = screen.getByText("Search Strategy");
    expect(button).toBeDisabled();
  });

  it("navigates to strategy detail on row click", async () => {
    jest.useRealTimers();
    const user = userEvent.setup();
    mockedApi.get.mockResolvedValue({ data: [mockStrategies[0]] });

    await act(async () => {
      render(<StrategiesPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("MACD Crossover")).toBeInTheDocument();
    });

    await user.click(screen.getByText("MACD Crossover"));

    expect(mockPush).toHaveBeenCalledWith("/dashboard/strategies/s1");
  });

  it("toggles auto trading from active to inactive", async () => {
    jest.useRealTimers();
    const user = userEvent.setup();

    mockedApi.get.mockResolvedValue({ data: [mockStrategies[0]] });

    await act(async () => {
      render(<StrategiesPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Stop")).toBeInTheDocument();
    });

    // Strategy s1 has is_auto_trading: true, so button shows "Stop"
    await user.click(screen.getByText("Stop"));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith(
        "/strategies/s1/deactivate"
      );
    });
  });

  it("toggles auto trading from inactive to active", async () => {
    jest.useRealTimers();
    const user = userEvent.setup();

    mockedApi.get.mockResolvedValue({ data: [mockStrategies[1]] });

    await act(async () => {
      render(<StrategiesPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Activate")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Activate"));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith(
        "/strategies/s2/activate"
      );
    });
  });

  it("deletes a strategy after confirmation", async () => {
    jest.useRealTimers();
    const user = userEvent.setup();

    mockedApi.get.mockResolvedValue({ data: [mockStrategies[0]] });

    await act(async () => {
      render(<StrategiesPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("삭제")).toBeInTheDocument();
    });

    await user.click(screen.getByText("삭제"));

    await waitFor(() => {
      expect(mockedApi.delete).toHaveBeenCalledWith("/strategies/s1");
    });
  });

  it("renders optimization method selector with all options", async () => {
    await act(async () => {
      render(<StrategiesPage />);
    });

    expect(screen.getByText("Grid Search")).toBeInTheDocument();
    expect(screen.getByText("Genetic Algorithm")).toBeInTheDocument();
    expect(screen.getByText("Bayesian (Optuna)")).toBeInTheDocument();
  });
});
