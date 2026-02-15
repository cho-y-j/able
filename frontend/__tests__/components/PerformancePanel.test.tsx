import { render, screen, waitFor, act } from "@testing-library/react";
import PerformancePanel from "@/app/dashboard/recipes/[id]/_components/PerformancePanel";
import api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

// Mock lightweight-charts (dynamic import, not installed as direct dep in test env)
jest.mock("lightweight-charts", () => ({
  createChart: jest.fn(() => ({
    addSeries: jest.fn(() => ({ setData: jest.fn() })),
    timeScale: jest.fn(() => ({ fitContent: jest.fn() })),
    priceScale: jest.fn(() => ({ applyOptions: jest.fn() })),
    applyOptions: jest.fn(),
    remove: jest.fn(),
  })),
  BaselineSeries: "BaselineSeries",
}), { virtual: true });

// Mock ResizeObserver (not available in jsdom)
global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

const mockPerformance = {
  total_trades: 5,
  closed_trades: 4,
  open_trades: 1,
  win_rate: 75.0,
  total_pnl: 850000,
  total_pnl_percent: 8.5,
  avg_win: 4.2,
  avg_loss: -2.1,
  profit_factor: 2.0,
  avg_slippage_bps: 3.5,
  equity_curve: [
    { date: "2026-01-15", value: 200000 },
    { date: "2026-01-20", value: 500000 },
    { date: "2026-02-01", value: 850000 },
  ],
  trades: [
    {
      id: "t1",
      stock_code: "005930",
      side: "buy",
      entry_price: 72000,
      exit_price: 75600,
      quantity: 20,
      pnl: 72000,
      pnl_percent: 5.0,
      entry_at: "2026-01-10T09:00:00Z",
      exit_at: "2026-01-15T14:30:00Z",
    },
    {
      id: "t2",
      stock_code: "000660",
      side: "sell",
      entry_price: 120000,
      exit_price: 115000,
      quantity: 10,
      pnl: -50000,
      pnl_percent: -4.2,
      entry_at: "2026-01-12T10:00:00Z",
      exit_at: "2026-01-18T15:00:00Z",
    },
  ],
  trades_total: 5,
};

describe("PerformancePanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedApi.get.mockResolvedValue({ data: mockPerformance });
  });

  it("renders empty state when no recipeId", async () => {
    mockedApi.get.mockResolvedValue({
      data: { ...mockPerformance, total_trades: 0, trades: [], equity_curve: [] },
    });

    await act(async () => {
      render(<PerformancePanel recipeId={null} />);
    });

    // fetchPerformance skips when recipeId is null — should show no data message
    await waitFor(() => {
      expect(
        screen.getByText("아직 거래 성과 데이터가 없습니다")
      ).toBeInTheDocument();
    });
  });

  it("renders empty state when no trades", async () => {
    mockedApi.get.mockResolvedValue({
      data: {
        total_trades: 0,
        closed_trades: 0,
        open_trades: 0,
        win_rate: null,
        total_pnl: 0,
        total_pnl_percent: null,
        avg_win: null,
        avg_loss: null,
        profit_factor: null,
        avg_slippage_bps: null,
        equity_curve: [],
        trades: [],
        trades_total: 0,
      },
    });

    await act(async () => {
      render(<PerformancePanel recipeId="r1" />);
    });

    await waitFor(() => {
      expect(
        screen.getByText("아직 거래 성과 데이터가 없습니다")
      ).toBeInTheDocument();
    });
  });

  it("renders summary metric cards", async () => {
    await act(async () => {
      render(<PerformancePanel recipeId="r1" />);
    });

    await waitFor(() => {
      expect(screen.getByText("총 손익")).toBeInTheDocument();
    });

    expect(screen.getByText("승률")).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByText("거래 수")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("수익률 팩터")).toBeInTheDocument();
    expect(screen.getByText("2x")).toBeInTheDocument();
  });

  it("renders trade history table", async () => {
    await act(async () => {
      render(<PerformancePanel recipeId="r1" />);
    });

    await waitFor(() => {
      expect(screen.getByText("005930")).toBeInTheDocument();
    });

    expect(screen.getByText("000660")).toBeInTheDocument();
    expect(screen.getByText("매수")).toBeInTheDocument();
    expect(screen.getByText("매도")).toBeInTheDocument();
    expect(screen.getByText("수익")).toBeInTheDocument();
    expect(screen.getByText("손실")).toBeInTheDocument();
  });

  it("handles API error gracefully", async () => {
    mockedApi.get.mockRejectedValue(new Error("Network error"));

    await act(async () => {
      render(<PerformancePanel recipeId="r1" />);
    });

    await waitFor(() => {
      expect(
        screen.getByText("성과 데이터를 불러오지 못했습니다")
      ).toBeInTheDocument();
    });
  });

  it("calls correct API endpoint", async () => {
    await act(async () => {
      render(<PerformancePanel recipeId="r1" />);
    });

    await waitFor(() => {
      expect(mockedApi.get).toHaveBeenCalledWith("/recipes/r1/performance");
    });
  });
});
