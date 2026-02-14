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
    name: "macd_crossover_opt",
    stock_code: "005930",
    stock_name: "Samsung",
    strategy_type: "macd_crossover",
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
    name: "rsi_mean_reversion_opt",
    stock_code: "035720",
    stock_name: "Kakao",
    strategy_type: "rsi_mean_reversion",
    composite_score: 62.3,
    validation_results: null,
    status: "validated",
    is_auto_trading: false,
    created_at: "2025-01-02T00:00:00Z",
  },
  {
    id: "s3",
    name: "bb_width_breakout_opt",
    stock_code: "000660",
    stock_name: "SK Hynix",
    strategy_type: "bb_width_breakout",
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

    // Strategy names are displayed via typeName(strategy_type)
    expect(screen.getByText("MACD 크로스")).toBeInTheDocument();
    expect(screen.getByText("RSI 평균회귀")).toBeInTheDocument();
    expect(screen.getByText("볼린저 돌파")).toBeInTheDocument();
  });

  it("renders GradeBadge with correct grades for different scores", async () => {
    mockedApi.get.mockResolvedValue({ data: mockStrategies });

    await act(async () => {
      render(<StrategiesPage />);
    });

    await waitFor(() => {
      // score 85.5 => grade "A" (also appears in grade reference)
      const gradeA = screen.getAllByText("A");
      expect(gradeA.length).toBeGreaterThanOrEqual(1);
      // score 62.3 => grade "B"
      const gradeB = screen.getAllByText("B");
      expect(gradeB.length).toBeGreaterThanOrEqual(1);
      // score 35.0 => grade "D"
      const gradeD = screen.getAllByText("D");
      expect(gradeD.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows backtest metrics for strategies that have them", async () => {
    mockedApi.get.mockResolvedValue({ data: mockStrategies });

    await act(async () => {
      render(<StrategiesPage />);
    });

    await waitFor(() => {
      // Strategy s1 has backtest data (Korean format)
      expect(screen.getByText(/수익률 \+32\.5%/)).toBeInTheDocument();
      expect(screen.getByText(/샤프 1\.85/)).toBeInTheDocument();
      expect(screen.getByText(/MDD -12\.3%/)).toBeInTheDocument();
    });
  });

  it("shows composite score for strategies without backtest data", async () => {
    mockedApi.get.mockResolvedValue({ data: mockStrategies });

    await act(async () => {
      render(<StrategiesPage />);
    });

    await waitFor(() => {
      // Strategy s2 has no backtest but has score 62.3 (Korean format)
      expect(screen.getByText(/종합점수 62\.3점/)).toBeInTheDocument();
    });
  });

  it("displays correct status badges", async () => {
    mockedApi.get.mockResolvedValue({ data: mockStrategies });

    await act(async () => {
      render(<StrategiesPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("자동매매 중")).toBeInTheDocument();
      expect(screen.getByText("검증 완료")).toBeInTheDocument();
      expect(screen.getByText("초안")).toBeInTheDocument();
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
      expect(screen.getByText("MACD 크로스")).toBeInTheDocument();
    });

    await user.click(screen.getByText("MACD 크로스"));

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
      expect(screen.getByText("매매 중지")).toBeInTheDocument();
    });

    // Strategy s1 has is_auto_trading: true, so button shows "매매 중지"
    await user.click(screen.getByText("매매 중지"));

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
      expect(screen.getByText("자동매매 시작")).toBeInTheDocument();
    });

    await user.click(screen.getByText("자동매매 시작"));

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

    expect(screen.getByText(/Grid Search/)).toBeInTheDocument();
    expect(screen.getByText(/Genetic/)).toBeInTheDocument();
    expect(screen.getByText(/Bayesian/)).toBeInTheDocument();
  });
});
