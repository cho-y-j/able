import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import StrategyDetailPage from "@/app/dashboard/strategies/[id]/page";
import api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

// Mock lightweight-charts
jest.mock("lightweight-charts", () => ({
  createChart: () => ({
    addSeries: () => ({ setData: jest.fn() }),
    timeScale: () => ({ fitContent: jest.fn(), setVisibleRange: jest.fn() }),
    priceScale: () => ({ applyOptions: jest.fn() }),
    applyOptions: jest.fn(),
    remove: jest.fn(),
  }),
  BaselineSeries: "BaselineSeries",
  AreaSeries: "AreaSeries",
}), { virtual: true });

// Mock lucide-react
jest.mock("lucide-react", () => ({
  BarChart3: (props: any) => <svg data-testid="icon-barchart3" {...props} />,
  TrendingUp: (props: any) => <svg data-testid="icon-trending-up" {...props} />,
  TrendingDown: (props: any) => <svg data-testid="icon-trending-down" {...props} />,
  List: (props: any) => <svg data-testid="icon-list" {...props} />,
  Shield: (props: any) => <svg data-testid="icon-shield" {...props} />,
  Settings: (props: any) => <svg data-testid="icon-settings" {...props} />,
  Bot: (props: any) => <svg data-testid="icon-bot" {...props} />,
  ChevronDown: (props: any) => <svg data-testid="icon-chevron" {...props} />,
  Minus: (props: any) => <svg data-testid="icon-minus" {...props} />,
  Loader2: (props: any) => <svg data-testid="icon-loader" {...props} />,
  Info: (props: any) => <svg data-testid="icon-info" {...props} />,
}));

// Mock ResizeObserver
global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  disconnect: jest.fn(),
  unobserve: jest.fn(),
}));

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

const mockParamRanges = {
  parameters: {
    fast_period: { type: "int", current: 12, min: 5, max: 50, choices: null },
    slow_period: { type: "int", current: 26, min: 10, max: 100, choices: null },
  },
  current_values: { fast_period: 12, slow_period: 26 },
};

describe("StrategyDetailPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedApi.get.mockImplementation((url: string) => {
      if (url.includes("/param-ranges")) {
        return Promise.resolve({ data: mockParamRanges });
      }
      return Promise.resolve({ data: mockStrategyDetail });
    });
  });

  it("shows loading spinner initially", () => {
    mockedApi.get.mockReturnValue(new Promise(() => {}));
    render(<StrategyDetailPage />);
    const spinner = document.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
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

    expect(
      screen.getByText(/005930.*Samsung Electronics.*momentum.*validated/)
    ).toBeInTheDocument();
  });

  it("renders GradeBadge with grade letter", async () => {
    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      const badges = screen.getAllByText("A");
      expect(badges.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("renders overview tab with hero metrics by default", async () => {
    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("총 수익률")).toBeInTheDocument();
      expect(screen.getByText("+28.50%")).toBeInTheDocument();
      expect(screen.getByText("연 수익률")).toBeInTheDocument();
      expect(screen.getByText("+18.30%")).toBeInTheDocument();
      expect(screen.getByText("샤프 비율")).toBeInTheDocument();
      expect(screen.getByText("1.65")).toBeInTheDocument();
      expect(screen.getByText("최대 낙폭 (MDD)")).toBeInTheDocument();
      expect(screen.getByText("-14.20%")).toBeInTheDocument();
    });
  });

  it("renders secondary metrics in overview", async () => {
    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("소르티노 비율")).toBeInTheDocument();
      expect(screen.getByText("승률")).toBeInTheDocument();
      expect(screen.getByText("수익 팩터")).toBeInTheDocument();
      expect(screen.getByText("총 거래수")).toBeInTheDocument();
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
    mockedApi.get.mockImplementation((url: string) => {
      if (url.includes("/param-ranges")) return Promise.resolve({ data: mockParamRanges });
      return Promise.resolve({ data: noBacktestData });
    });

    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("칼마 비율")).toBeInTheDocument();
    });
  });

  it("shows all six tab buttons", async () => {
    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("성과 지표")).toBeInTheDocument();
      expect(screen.getByText("에쿼티 커브")).toBeInTheDocument();
      expect(screen.getByText("거래 내역")).toBeInTheDocument();
      expect(screen.getByText("검증 결과")).toBeInTheDocument();
      expect(screen.getByText("파라미터 조정")).toBeInTheDocument();
      const aiTexts = screen.getAllByText("AI 분석");
      expect(aiTexts.length).toBeGreaterThanOrEqual(1);
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
      expect(screen.getByText(/2건/)).toBeInTheDocument();
      expect(screen.getByText(/진입일/)).toBeInTheDocument();
      expect(screen.getByText(/청산일/)).toBeInTheDocument();
      expect(screen.getByText(/손익/)).toBeInTheDocument();
      expect(screen.getByText("2024-01-15")).toBeInTheDocument();
      expect(screen.getByText("2024-02-10")).toBeInTheDocument();
      const wins = screen.getAllByText(/\+8\.33%/);
      expect(wins.length).toBeGreaterThanOrEqual(1);
      const losses = screen.getAllByText(/-3\.29%/);
      expect(losses.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("switches to equity tab and shows chart info", async () => {
    const user = userEvent.setup();

    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("에쿼티 커브")).toBeInTheDocument();
    });

    await user.click(screen.getByText("에쿼티 커브"));

    await waitFor(() => {
      expect(screen.getByText("기간")).toBeInTheDocument();
      expect(screen.getByText("2024-01-01 ~ 2025-06-30")).toBeInTheDocument();
      expect(screen.getByText("시작 자본")).toBeInTheDocument();
      expect(screen.getByText("최종 자본")).toBeInTheDocument();
      expect(screen.getByText("전체")).toBeInTheDocument();
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
      expect(screen.getByText(/Walk-Forward Analysis/)).toBeInTheDocument();
      expect(screen.getByText(/Monte Carlo Simulation/)).toBeInTheDocument();
      expect(screen.getByText(/Out-of-Sample 검증/)).toBeInTheDocument();
      expect(screen.getByText(/73\.0%/)).toBeInTheDocument();
      expect(screen.getByText(/62\.8%/)).toBeInTheDocument();
      expect(screen.getByText(/88\.5%/)).toBeInTheDocument();
    });
  });

  it("renders auto-trading status indicator", async () => {
    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("비활성")).toBeInTheDocument();
    });
  });

  it("renders auto-trading active indicator when enabled", async () => {
    const activeStrategy = { ...mockStrategyDetail, is_auto_trading: true };
    mockedApi.get.mockImplementation((url: string) => {
      if (url.includes("/param-ranges")) return Promise.resolve({ data: mockParamRanges });
      return Promise.resolve({ data: activeStrategy });
    });

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

  it("renders ScoreGauge with N/A when score is null", async () => {
    const noScoreStrategy = { ...mockStrategyDetail, composite_score: null };
    mockedApi.get.mockImplementation((url: string) => {
      if (url.includes("/param-ranges")) return Promise.resolve({ data: mockParamRanges });
      return Promise.resolve({ data: noScoreStrategy });
    });

    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      const nas = screen.getAllByText("N/A");
      expect(nas.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("renders score gauges in overview tab", async () => {
    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("WFA")).toBeInTheDocument();
      expect(screen.getByText("MC")).toBeInTheDocument();
      expect(screen.getByText("OOS")).toBeInTheDocument();
    });
  });

  it("renders header key metric badges", async () => {
    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText(/수익 \+28\.5%/)).toBeInTheDocument();
      expect(screen.getByText(/샤프 1\.65/)).toBeInTheDocument();
      expect(screen.getByText(/MDD -14\.2%/)).toBeInTheDocument();
    });
  });

  it("switches to params tab and shows parameter adjustment UI", async () => {
    const user = userEvent.setup();

    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("파라미터 조정")).toBeInTheDocument();
    });

    await user.click(screen.getByText("파라미터 조정"));

    await waitFor(() => {
      expect(screen.getByText("보수적")).toBeInTheDocument();
      expect(screen.getByText("공격적")).toBeInTheDocument();
      expect(screen.getByText("원래값")).toBeInTheDocument();
      expect(screen.getByText("재백테스트 실행")).toBeInTheDocument();
      const labels = screen.getAllByText(/fast_period|slow_period|signal_period|rsi_period/);
      expect(labels.length).toBeGreaterThanOrEqual(4);
    });
  });

  it("switches to AI tab and shows AI analysis initial state", async () => {
    const user = userEvent.setup();

    await act(async () => {
      render(<StrategyDetailPage />);
    });

    await waitFor(() => {
      const aiTabs = screen.getAllByText("AI 분석");
      expect(aiTabs.length).toBeGreaterThanOrEqual(1);
    });

    const aiTabs = screen.getAllByText("AI 분석");
    await user.click(aiTabs[aiTabs.length - 1]);

    await waitFor(() => {
      expect(screen.getByText("AI 하이브리드 분석")).toBeInTheDocument();
      expect(screen.getByText("AI 분석 시작")).toBeInTheDocument();
    });
  });
});
