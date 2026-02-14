import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import PortfolioPage from "@/app/dashboard/portfolio/page";
import api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

const mockAnalytics = {
  portfolio_value: 50000000,
  total_invested: 40000000,
  unrealized_pnl: 5000000,
  realized_pnl: 5000000,
  total_pnl: 10000000,
  total_pnl_pct: 25.0,
  position_count: 3,
  allocation: [
    {
      stock_code: "005930",
      stock_name: "Samsung",
      quantity: 100,
      value: 7500000,
      weight: 15.0,
      unrealized_pnl: 500000,
      pnl_pct: 7.1,
    },
  ],
  trade_stats: {
    total_trades: 20,
    win_rate: 65.0,
    avg_win: 300000,
    avg_loss: -150000,
    profit_factor: 2.6,
    winning_trades: 13,
    losing_trades: 7,
  },
};

describe("PortfolioPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/trading/portfolio/analytics")
        return Promise.resolve({ data: mockAnalytics });
      if (url.startsWith("/trading/trades"))
        return Promise.resolve({ data: [] });
      if (url === "/trading/portfolio/strategies")
        return Promise.resolve({ data: null });
      if (url === "/trading/portfolio/attribution")
        return Promise.resolve({ data: null });
      if (url.startsWith("/trading/portfolio/risk"))
        return Promise.resolve({ data: null });
      return Promise.reject(new Error("Unknown"));
    });
  });

  it("shows loading state", () => {
    mockedApi.get.mockImplementation(() => new Promise(() => {})); // never resolves
    render(<PortfolioPage />);
    expect(screen.getByText("Loading...")).toBeTruthy();
  });

  it("renders page title after load", async () => {
    render(<PortfolioPage />);
    await waitFor(() => {
      expect(screen.getByText("Portfolio Analytics")).toBeTruthy();
    });
  });

  it("renders summary cards", async () => {
    render(<PortfolioPage />);
    await waitFor(() => {
      expect(screen.getByText("Portfolio Value")).toBeTruthy();
    });
    expect(screen.getByText("Total Invested")).toBeTruthy();
    expect(screen.getByText("Total P&L")).toBeTruthy();
    expect(screen.getByText("Positions")).toBeTruthy();
  });

  it("renders tab buttons", async () => {
    render(<PortfolioPage />);
    await waitFor(() => {
      expect(screen.getByText("Overview")).toBeTruthy();
    });
    expect(screen.getByText("By Strategy")).toBeTruthy();
    expect(screen.getByText("Trade History")).toBeTruthy();
    expect(screen.getByText("Risk Analysis")).toBeTruthy();
  });

  it("shows allocation in overview", async () => {
    render(<PortfolioPage />);
    await waitFor(() => {
      expect(screen.getByText("Allocation")).toBeTruthy();
    });
    expect(screen.getByText("Samsung")).toBeTruthy();
  });

  it("shows trade statistics", async () => {
    render(<PortfolioPage />);
    await waitFor(() => {
      expect(screen.getByText("Trade Statistics")).toBeTruthy();
    });
    expect(screen.getByText("Total Trades")).toBeTruthy();
    expect(screen.getByText("20")).toBeTruthy();
    expect(screen.getByText("Win Rate")).toBeTruthy();
    expect(screen.getByText("65%")).toBeTruthy();
    expect(screen.getByText("Avg Win")).toBeTruthy();
    expect(screen.getByText("Avg Loss")).toBeTruthy();
    expect(screen.getByText("Profit Factor")).toBeTruthy();
    expect(screen.getByText("2.60")).toBeTruthy();
    expect(screen.getByText("W/L")).toBeTruthy();
    expect(screen.getByText("13 / 7")).toBeTruthy();
  });

  it("shows P&L breakdown", async () => {
    render(<PortfolioPage />);
    await waitFor(() => {
      expect(screen.getByText("P&L Breakdown")).toBeTruthy();
    });
    expect(screen.getByText("Unrealized")).toBeTruthy();
    expect(screen.getByText("Realized")).toBeTruthy();
    // "Total" appears both in summary card label "Total P&L" and in the P&L breakdown
    expect(screen.getAllByText("Total").length).toBeGreaterThanOrEqual(1);
  });

  it("shows no trade history message", async () => {
    render(<PortfolioPage />);
    await waitFor(() => {
      expect(screen.getByText("Trade History")).toBeTruthy();
    });
    fireEvent.click(screen.getByText("Trade History"));
    await waitFor(() => {
      expect(screen.getByText("No trade history yet.")).toBeTruthy();
    });
  });
});
