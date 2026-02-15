import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import StrategyComparePage from "@/app/dashboard/strategies/compare/page";
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
  usePathname: () => "/dashboard/strategies/compare",
  useSearchParams: () => new URLSearchParams(),
}));

const mockStrategies = [
  {
    id: "s1",
    name: "MACD Strategy",
    stock_code: "005930",
    strategy_type: "macd_crossover",
    composite_score: 85,
    status: "active",
  },
  {
    id: "s2",
    name: "RSI Strategy",
    stock_code: "035720",
    strategy_type: "rsi_mean_reversion",
    composite_score: 62,
    status: "validated",
  },
  {
    id: "s3",
    name: "BB Strategy",
    stock_code: "000660",
    strategy_type: "bb_width_breakout",
    composite_score: 40,
    status: "draft",
  },
];

const mockCompareResult = {
  strategies: [
    {
      strategy_id: "s1",
      name: "MACD Strategy",
      stock_code: "005930",
      strategy_type: "macd_crossover",
      composite_score: 85,
      status: "active",
      backtest: {
        id: "bt1",
        total_return: 32.5,
        annual_return: 18.0,
        sharpe_ratio: 1.85,
        sortino_ratio: 2.1,
        max_drawdown: -12.3,
        win_rate: 58.5,
        profit_factor: 1.65,
        calmar_ratio: 1.46,
        wfa_score: 75,
        mc_score: 80,
        oos_score: 70,
        equity_curve: [10000000, 10100000, 10250000],
        date_range_start: "2024-01-01",
      },
    },
    {
      strategy_id: "s2",
      name: "RSI Strategy",
      stock_code: "035720",
      strategy_type: "rsi_mean_reversion",
      composite_score: 62,
      status: "validated",
      backtest: {
        id: "bt2",
        total_return: 18.2,
        annual_return: 10.5,
        sharpe_ratio: 1.2,
        sortino_ratio: 1.4,
        max_drawdown: -18.0,
        win_rate: 52.0,
        profit_factor: 1.3,
        calmar_ratio: 0.58,
        wfa_score: 60,
        mc_score: 55,
        oos_score: 50,
        equity_curve: [10000000, 9900000, 10050000],
        date_range_start: "2024-01-01",
      },
    },
  ],
  ranking: [
    { rank: 1, strategy_id: "s1", name: "MACD Strategy", score: 85 },
    { rank: 2, strategy_id: "s2", name: "RSI Strategy", score: 62 },
  ],
};

describe("StrategyComparePage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("loads and displays strategy checkboxes", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockStrategies } as never);

    await act(async () => {
      render(<StrategyComparePage />);
    });

    await waitFor(() => {
      expect(screen.getByText("MACD Strategy")).toBeInTheDocument();
    });

    expect(screen.getByText("RSI Strategy")).toBeInTheDocument();
    expect(screen.getByText("BB Strategy")).toBeInTheDocument();
    expect(screen.getAllByRole("checkbox")).toHaveLength(3);
  });

  it("shows empty state when no strategies", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: [] } as never);

    await act(async () => {
      render(<StrategyComparePage />);
    });

    await waitFor(() => {
      expect(screen.getByText(/No strategies yet/i)).toBeInTheDocument();
    });
  });

  it("disables compare button when fewer than 2 strategies selected", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockStrategies } as never);

    await act(async () => {
      render(<StrategyComparePage />);
    });

    await waitFor(() => {
      expect(screen.getByText("MACD Strategy")).toBeInTheDocument();
    });

    const compareButton = screen.getByRole("button", { name: /Compare Strategies/i });
    expect(compareButton).toBeDisabled();

    // Select one — still disabled
    const user = userEvent.setup();
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]);
    expect(compareButton).toBeDisabled();

    // Select second — enabled
    await user.click(checkboxes[1]);
    expect(compareButton).not.toBeDisabled();
  });

  it("runs comparison and renders metric table", async () => {
    mockedApi.get
      .mockResolvedValueOnce({ data: mockStrategies } as never)
      .mockResolvedValueOnce({ data: mockCompareResult } as never);

    await act(async () => {
      render(<StrategyComparePage />);
    });

    await waitFor(() => {
      expect(screen.getByText("MACD Strategy")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]);
    await user.click(checkboxes[1]);

    const compareButton = screen.getByRole("button", { name: /Compare Strategies/i });
    await user.click(compareButton);

    await waitFor(() => {
      expect(screen.getByText("Ranking")).toBeInTheDocument();
    });

    // Switch to metrics tab
    const metricsTab = screen.getByRole("button", { name: /Performance Metrics/i });
    await user.click(metricsTab);

    await waitFor(() => {
      expect(screen.getByText("+32.50%")).toBeInTheDocument();
      expect(screen.getByText("+18.20%")).toBeInTheDocument();
    });
  });

  it("displays ranking cards after comparison", async () => {
    mockedApi.get
      .mockResolvedValueOnce({ data: mockStrategies } as never)
      .mockResolvedValueOnce({ data: mockCompareResult } as never);

    await act(async () => {
      render(<StrategyComparePage />);
    });

    await waitFor(() => {
      expect(screen.getByText("MACD Strategy")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]);
    await user.click(checkboxes[1]);

    const compareButton = screen.getByRole("button", { name: /Compare Strategies/i });
    await user.click(compareButton);

    await waitFor(() => {
      expect(screen.getByText("#1")).toBeInTheDocument();
      expect(screen.getByText("#2")).toBeInTheDocument();
      expect(screen.getByText("85.0 pts")).toBeInTheDocument();
    });
  });

  it("shows error when comparison fails", async () => {
    mockedApi.get
      .mockResolvedValueOnce({ data: mockStrategies } as never)
      .mockRejectedValueOnce({
        response: { data: { detail: "Need at least 2 strategy IDs" } },
      } as never);

    await act(async () => {
      render(<StrategyComparePage />);
    });

    await waitFor(() => {
      expect(screen.getByText("MACD Strategy")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]);
    await user.click(checkboxes[1]);

    const compareButton = screen.getByRole("button", { name: /Compare Strategies/i });
    await user.click(compareButton);

    await waitFor(() => {
      expect(screen.getByText("Need at least 2 strategy IDs")).toBeInTheDocument();
    });
  });
});
