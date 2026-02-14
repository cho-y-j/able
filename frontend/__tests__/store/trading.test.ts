import { useTradingStore, type Position } from "@/store/trading";
import api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

const mockPositions: Position[] = [
  {
    id: "p1",
    stock_code: "005930",
    stock_name: "삼성전자",
    quantity: 10,
    avg_cost_price: 70000,
    current_price: 75000,
    unrealized_pnl: 50000,
    realized_pnl: 0,
  },
  {
    id: "p2",
    stock_code: "000660",
    stock_name: "SK하이닉스",
    quantity: 5,
    avg_cost_price: 150000,
    current_price: 145000,
    unrealized_pnl: -25000,
    realized_pnl: 10000,
  },
];

describe("useTradingStore", () => {
  beforeEach(() => {
    useTradingStore.setState({
      positions: [],
      orders: [],
      portfolioStats: null,
      selectedStock: null,
      isLoading: false,
      lastUpdated: null,
    });
    jest.clearAllMocks();
  });

  describe("initial state", () => {
    it("starts empty", () => {
      const state = useTradingStore.getState();
      expect(state.positions).toEqual([]);
      expect(state.orders).toEqual([]);
      expect(state.portfolioStats).toBeNull();
      expect(state.selectedStock).toBeNull();
      expect(state.isLoading).toBe(false);
    });
  });

  describe("fetchPositions", () => {
    it("fetches and stores positions", async () => {
      mockedApi.get.mockResolvedValueOnce({ data: mockPositions });

      await useTradingStore.getState().fetchPositions();

      const state = useTradingStore.getState();
      expect(state.positions).toHaveLength(2);
      expect(state.positions[0].stock_code).toBe("005930");
      expect(state.isLoading).toBe(false);
      expect(state.lastUpdated).not.toBeNull();
    });

    it("calls correct API endpoint", async () => {
      mockedApi.get.mockResolvedValueOnce({ data: [] });

      await useTradingStore.getState().fetchPositions();

      expect(mockedApi.get).toHaveBeenCalledWith("/trading/positions");
    });

    it("sets isLoading during fetch", async () => {
      let resolvePromise: (value: unknown) => void;
      mockedApi.get.mockReturnValueOnce(
        new Promise((resolve) => {
          resolvePromise = resolve;
        }) as never,
      );

      const fetchPromise = useTradingStore.getState().fetchPositions();
      expect(useTradingStore.getState().isLoading).toBe(true);

      resolvePromise!({ data: [] });
      await fetchPromise;
      expect(useTradingStore.getState().isLoading).toBe(false);
    });
  });

  describe("fetchOrders", () => {
    it("fetches and stores orders", async () => {
      const mockOrders = [
        {
          id: "o1", stock_code: "005930", stock_name: "삼성전자",
          side: "BUY", order_type: "MARKET", quantity: 10,
          limit_price: null, filled_quantity: 10, avg_fill_price: 70000,
          status: "FILLED", submitted_at: "2026-01-01", filled_at: "2026-01-01",
          created_at: "2026-01-01",
        },
      ];
      mockedApi.get.mockResolvedValueOnce({ data: mockOrders });

      await useTradingStore.getState().fetchOrders();

      expect(useTradingStore.getState().orders).toHaveLength(1);
      expect(mockedApi.get).toHaveBeenCalledWith("/trading/orders");
    });

    it("handles API error silently", async () => {
      mockedApi.get.mockRejectedValueOnce(new Error("Network error"));

      await useTradingStore.getState().fetchOrders();

      expect(useTradingStore.getState().orders).toEqual([]);
    });
  });

  describe("fetchPortfolioStats", () => {
    it("fetches and stores portfolio stats", async () => {
      const mockStats = {
        portfolio_value: 10_000_000,
        total_invested: 9_500_000,
        unrealized_pnl: 500_000,
        realized_pnl: 100_000,
        total_pnl: 600_000,
        total_pnl_pct: 6.32,
        position_count: 3,
        trade_stats: {
          total_trades: 15,
          win_rate: 0.6,
          profit_factor: 1.8,
          winning_trades: 9,
          losing_trades: 6,
        },
      };
      mockedApi.get.mockResolvedValueOnce({ data: mockStats });

      await useTradingStore.getState().fetchPortfolioStats();

      const state = useTradingStore.getState();
      expect(state.portfolioStats?.portfolio_value).toBe(10_000_000);
      expect(state.portfolioStats?.trade_stats.win_rate).toBe(0.6);
      expect(mockedApi.get).toHaveBeenCalledWith("/trading/portfolio/analytics");
    });
  });

  describe("setSelectedStock", () => {
    it("updates selected stock", () => {
      useTradingStore.getState().setSelectedStock("005930");
      expect(useTradingStore.getState().selectedStock).toBe("005930");
    });

    it("clears selected stock with null", () => {
      useTradingStore.getState().setSelectedStock("005930");
      useTradingStore.getState().setSelectedStock(null);
      expect(useTradingStore.getState().selectedStock).toBeNull();
    });
  });

  describe("updatePositionPrice", () => {
    it("updates price and recalculates unrealized P&L", () => {
      useTradingStore.setState({ positions: mockPositions });

      useTradingStore.getState().updatePositionPrice("005930", 80000);

      const position = useTradingStore.getState().positions.find((p) => p.stock_code === "005930");
      expect(position?.current_price).toBe(80000);
      expect(position?.unrealized_pnl).toBe(100000); // (80000 - 70000) * 10
    });

    it("does not affect other positions", () => {
      useTradingStore.setState({ positions: mockPositions });

      useTradingStore.getState().updatePositionPrice("005930", 80000);

      const sk = useTradingStore.getState().positions.find((p) => p.stock_code === "000660");
      expect(sk?.current_price).toBe(145000); // unchanged
    });

    it("updates lastUpdated timestamp", () => {
      useTradingStore.setState({ positions: mockPositions, lastUpdated: null });

      useTradingStore.getState().updatePositionPrice("005930", 80000);

      expect(useTradingStore.getState().lastUpdated).not.toBeNull();
    });

    it("handles non-existent stock code gracefully", () => {
      useTradingStore.setState({ positions: mockPositions });

      useTradingStore.getState().updatePositionPrice("999999", 50000);

      // Positions unchanged
      expect(useTradingStore.getState().positions).toHaveLength(2);
    });
  });
});
