import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import StrategyDetailPage from "@/app/dashboard/strategies/[id]/page";
import api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

// Mock lightweight-charts (dynamically imported in the component)
// We need { virtual: true } because the module isn't resolved in the test environment
jest.mock("lightweight-charts", () => ({
  createChart: () => ({
    addSeries: () => ({ setData: jest.fn() }),
    timeScale: () => ({ fitContent: jest.fn() }),
    remove: jest.fn(),
  }),
  BaselineSeries: "BaselineSeries",
}), { virtual: true });

const mockPush = jest.fn();
const mockParams = { id: "strategy-1" };

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
    back: jest.fn(),
    prefetch: jest.fn(),
  }),
  useParams: () => mockParams,
  usePathname: () => "/dashboard/strategies/strategy-1",
  useSearchParams: () => new URLSearchParams(),
}));

const mockStrategyDetail = {
  id: "strategy-1",
  name: "MACD Crossover Strategy",
  stock_code: "005930",
  stock_name: "Samsung Electronics",
  strategy_type: "momentum",
  parameters: {
    fast_period: 12,
    slow_period: 26,
    signal_period: 9,
    rsi_period: 14,
  },
  entry_rules: { rule1: "MACD crosses above signal" },
  exit_rules: { rule1: "MACD crosses below signal" },
  risk_params: { stop_loss: 3, take_profit: 8 },
  composite_score: 82.5,
  validation_results: {
    wfa: { wfa_score: 78.3, stability: 85.1, mean_sharpe: 1.42, mean_return: 15.6 },
    mc: {
      mc_score: 72.5,
      statistics: { mean_return: 22.3, worst_case: -18.5, risk_of_ruin_pct: 2.1 },
      percentiles: { "5th": -15.2, "25th": 5.3, "50th": 18.7, "75th": 32.1, "95th": 48.5 },
    },
    oos: { oos_score: 68.9 },
    oos_detail: {
      in_sample: { sharpe_ratio: 1.85, total_return: 35.2, max_drawdown: -12.3, total_trades: 42 },
      out_of_sample: { sharpe_ratio: 1.35, total_return: 22.1, max_drawdown: -15.8, total_trades: 18 },
      degradation: { sharpe_retention: 73.0, return_retention: 62.8, winrate_retention: 88.5 },
    },
  },
  status: "validated",
  is_auto_trading: false,
  created_at: "2025-01-15T10:30:00Z",
  backtest: {
    id: "bt-1",
    date_range_start: "2024-01-01",
    date_range_end: "2025-06-30",
    metrics: {
      total_return: 28.5,
      annual_return: 18.3,
      sharpe_ratio: 1.65,
      sortino_ratio: 2.12,
      max_drawdown: -14.2,
      win_rate: 58.3,
      profit_factor: 1.82,
      total_trades: 60,
      calmar_ratio: 1.29,
    },
    validation: { wfa_score: 78.3, mc_score: 72.5, oos_score: 68.9 },
    equity_curve: [
      { date: "2024-01-02", value: 10000000 },
      { date: "2024-06-15", value: 11500000 },
      { date: "2025-06-30", value: 12850000 },
    ],
    trade_log: [
      {
        entry_date: "2024-01-15 09:30:00",
        exit_date: "2024-02-10 15:00:00",
        entry_price: 72000,
        exit_price: 78000,
        pnl_percent: 8.33,
        hold_days: 26,
      },
      {
        entry_date: "2024-03-05 10:00:00",
        exit_date: "2024-03-20 14:30:00",
        entry_price: 76000,
        exit_price: 73500,
        pnl_percent: -3.29,
        hold_days: 15,
      },
    ],
  },
};

describe("StrategyDetailPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedApi.get.mockResolvedValue({ data: mockStrategyDetail });
  });

  it("shows loading state initially", () => {
    // Make the API call hang so loading is visible
    mockedApi.get.mockReturnValue(new Promise(() => {}));

    render(<StrategyDetailPage />);

    expect(screen.getByText("로딩 중...")).toBeInTheDocument();
  });

  it("redirects to strategies list on API error", async () => {
    mockedApi.get.mockRejectedValue(new Error("Not found"));

    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/dashboard/strategies");
    });
  });

  it("renders strategy name and header details", async () => {
    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("MACD Crossover Strategy")).toBeInTheDocument();
    });

    // Stock code and name
    expect(
      screen.getByText(/005930.*Samsung Electronics.*momentum.*validated/)
    ).toBeInTheDocument();
  });

  it("renders GradeBadge with score in detail page format", async () => {
    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      // Detail page GradeBadge shows "A (82.5)" for score 82.5
      expect(screen.getByText("A (82.5)")).toBeInTheDocument();
    });
  });

  it("renders strategy parameters", async () => {
    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("전략 파라미터")).toBeInTheDocument();
      expect(screen.getByText("fast_period")).toBeInTheDocument();
      expect(screen.getByText("12")).toBeInTheDocument();
      expect(screen.getByText("slow_period")).toBeInTheDocument();
      expect(screen.getByText("26")).toBeInTheDocument();
      expect(screen.getByText("signal_period")).toBeInTheDocument();
      expect(screen.getByText("9")).toBeInTheDocument();
    });
  });

  it("renders overview tab with MetricCards by default", async () => {
    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("총 수익률")).toBeInTheDocument();
      expect(screen.getByText("+28.50%")).toBeInTheDocument();

      expect(screen.getByText("연 수익률")).toBeInTheDocument();
      expect(screen.getByText("+18.30%")).toBeInTheDocument();

      expect(screen.getByText("샤프 비율")).toBeInTheDocument();
      // 1.65.toFixed(1) = "1.6" due to JS floating point rounding
      expect(screen.getByText("+1.6")).toBeInTheDocument();

      expect(screen.getByText("최대 낙폭")).toBeInTheDocument();
      expect(screen.getByText("-14.20%")).toBeInTheDocument();

      expect(screen.getByText("승률")).toBeInTheDocument();
      // MetricCard adds "+" for positive values regardless of color
      expect(screen.getByText("+58.30%")).toBeInTheDocument();

      expect(screen.getByText("수익 팩터")).toBeInTheDocument();
      expect(screen.getByText("+1.82x")).toBeInTheDocument();

      expect(screen.getByText("총 거래수")).toBeInTheDocument();
      expect(screen.getByText("60.0 trades")).toBeInTheDocument();
    });
  });

  it("renders MetricCard as N/A when value is null", async () => {
    const noBacktestData = {
      ...mockStrategyDetail,
      backtest: {
        ...mockStrategyDetail.backtest,
        metrics: {
          ...mockStrategyDetail.backtest.metrics,
          calmar_ratio: null as unknown as number,
        },
      },
    };
    mockedApi.get.mockResolvedValue({ data: noBacktestData });

    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("칼마 비율")).toBeInTheDocument();
    });

    // The card for calmar_ratio should show N/A
    const calmarLabel = screen.getByText("칼마 비율");
    const card = calmarLabel.closest("div.bg-gray-800");
    expect(card).toHaveTextContent("N/A");
  });

  it("shows all four tab buttons", async () => {
    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("성과 지표")).toBeInTheDocument();
      expect(screen.getByText("에쿼티 커브")).toBeInTheDocument();
      expect(screen.getByText("거래 내역")).toBeInTheDocument();
      expect(screen.getByText("검증 결과")).toBeInTheDocument();
    });
  });

  it("switches to trades tab and shows trade log", async () => {
    const user = userEvent.setup();

    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("거래 내역")).toBeInTheDocument();
    });

    await user.click(screen.getByText("거래 내역"));

    await waitFor(() => {
      expect(screen.getByText("거래 내역 (2건)")).toBeInTheDocument();
      // Table headers
      expect(screen.getByText("진입일")).toBeInTheDocument();
      expect(screen.getByText("청산일")).toBeInTheDocument();
      expect(screen.getByText("손익(%)")).toBeInTheDocument();
      // Trade data
      expect(screen.getByText("2024-01-15")).toBeInTheDocument();
      expect(screen.getByText("2024-02-10")).toBeInTheDocument();
      expect(screen.getByText("+8.33%")).toBeInTheDocument();
      expect(screen.getByText("-3.29%")).toBeInTheDocument();
      expect(screen.getByText("26일")).toBeInTheDocument();
      expect(screen.getByText("15일")).toBeInTheDocument();
    });
  });

  it("switches to equity tab and shows chart container", async () => {
    const user = userEvent.setup();

    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("에쿼티 커브")).toBeInTheDocument();
    });

    await user.click(screen.getByText("에쿼티 커브"));

    await waitFor(() => {
      // Equity tab header
      const headings = screen.getAllByText("에쿼티 커브");
      expect(headings.length).toBeGreaterThanOrEqual(1);
      // Equity tab shows start capital
      expect(screen.getByText("시작 자본")).toBeInTheDocument();
      expect(screen.getByText("10,000,000원")).toBeInTheDocument();
      // Final capital
      expect(screen.getByText("최종 자본")).toBeInTheDocument();
      expect(screen.getByText("12,850,000원")).toBeInTheDocument();
      // Date range
      expect(screen.getByText("기간")).toBeInTheDocument();
      expect(screen.getByText("2024-01-01 ~ 2025-06-30")).toBeInTheDocument();
    });
  });

  it("switches to validation tab and shows WFA, MC, OOS sections", async () => {
    const user = userEvent.setup();

    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("검증 결과")).toBeInTheDocument();
    });

    await user.click(screen.getByText("검증 결과"));

    await waitFor(() => {
      // WFA section
      expect(screen.getByText("Walk-Forward Analysis")).toBeInTheDocument();
      expect(screen.getByText("78.3")).toBeInTheDocument(); // wfa_score
      expect(screen.getByText("85.1")).toBeInTheDocument(); // stability
      expect(screen.getByText("1.42")).toBeInTheDocument(); // mean_sharpe
      expect(screen.getByText("+15.60%")).toBeInTheDocument(); // mean_return

      // Monte Carlo section
      expect(screen.getByText("Monte Carlo Simulation")).toBeInTheDocument();
      expect(screen.getByText("72.5%")).toBeInTheDocument(); // mc_score

      // OOS section
      expect(screen.getByText("Out-of-Sample 검증")).toBeInTheDocument();
      expect(screen.getByText("68.9")).toBeInTheDocument(); // oos_score

      // Degradation stats
      expect(screen.getByText("73.0%")).toBeInTheDocument(); // sharpe_retention
      expect(screen.getByText("62.8%")).toBeInTheDocument(); // return_retention
      expect(screen.getByText("88.5%")).toBeInTheDocument(); // winrate_retention
    });
  });

  it("renders auto-trading status indicator", async () => {
    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      // is_auto_trading: false -> "비활성"
      expect(screen.getByText("비활성")).toBeInTheDocument();
    });
  });

  it("renders auto-trading active indicator when enabled", async () => {
    const activeStrategy = { ...mockStrategyDetail, is_auto_trading: true };
    mockedApi.get.mockResolvedValue({ data: activeStrategy });

    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("자동매매 활성")).toBeInTheDocument();
    });
  });

  it("renders back link to strategy list", async () => {
    const user = userEvent.setup();

    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText(/전략 목록/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/전략 목록/));

    expect(mockPush).toHaveBeenCalledWith("/dashboard/strategies");
  });

  it("GradeBadge shows N/A when score is null", async () => {
    const noScoreStrategy = { ...mockStrategyDetail, composite_score: null };
    mockedApi.get.mockResolvedValue({ data: noScoreStrategy });

    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("N/A")).toBeInTheDocument();
    });
  });

  it("renders validation scores in overview tab", async () => {
    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("WFA 점수")).toBeInTheDocument();
      expect(screen.getByText("MC 수익 확률")).toBeInTheDocument();
      expect(screen.getByText("OOS 점수")).toBeInTheDocument();
    });
  });
});
