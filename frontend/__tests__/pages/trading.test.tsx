import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TradingPage from "@/app/dashboard/trading/page";
import { useTradingStore } from "@/store/trading";
import { useAuthStore } from "@/store/auth";
import { createWSConnection } from "@/lib/ws";
import api from "@/lib/api";

jest.mock("@/lib/api");
jest.mock("@/store/trading");
jest.mock("@/store/auth");
jest.mock("@/lib/ws");
jest.mock("@/lib/charts", () => ({
  CHART_COLORS: { up: "#26a69a", down: "#ef5350", upAlpha: "rgba(38,166,154,0.3)", downAlpha: "rgba(239,83,80,0.3)" },
  DEFAULT_CHART_OPTIONS: {},
  formatKRW: (n: number) => `₩${n.toLocaleString()}`,
  formatPct: (n: number) => `${n.toFixed(1)}%`,
}));

const mockedApi = api as jest.Mocked<typeof api>;
const mockedUseTradingStore = useTradingStore as unknown as jest.Mock;
const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;

describe("TradingPage", () => {
  const mockFns = {
    fetchPositions: jest.fn(),
    fetchOrders: jest.fn(),
    fetchPortfolioStats: jest.fn(),
    setSelectedStock: jest.fn(),
    updatePositionPrice: jest.fn(),
  };

  function setupMocks(overrides?: {
    positions?: unknown[];
    orders?: unknown[];
    portfolioStats?: unknown;
    selectedStock?: string | null;
  }) {
    const state = {
      positions: overrides?.positions ?? [],
      orders: overrides?.orders ?? [],
      portfolioStats: overrides?.portfolioStats ?? null,
      selectedStock: overrides?.selectedStock ?? null,
      ...mockFns,
    };

    mockedUseTradingStore.mockImplementation((selector?: (s: unknown) => unknown) =>
      selector ? selector(state) : state,
    );

    mockedUseAuthStore.mockImplementation((selector?: (s: unknown) => unknown) => {
      const authState = { token: "test-token" };
      return selector ? selector(authState) : authState;
    });

    (createWSConnection as jest.Mock).mockReturnValue({
      connect: jest.fn(),
      on: jest.fn(() => jest.fn()),
      disconnect: jest.fn(),
    });

    mockedApi.get.mockResolvedValue({ data: { data: [] } });
    mockedApi.post.mockResolvedValue({ data: {} });
  }

  beforeEach(() => {
    jest.clearAllMocks();
    window.confirm = jest.fn(() => true);
    setupMocks();
  });

  it("renders page title", async () => {
    render(<TradingPage />);

    await waitFor(() => {
      expect(screen.getByText("Trading")).toBeInTheDocument();
    });
  });

  it("shows refresh button", async () => {
    render(<TradingPage />);

    await waitFor(() => {
      expect(screen.getByText("Refresh")).toBeInTheDocument();
    });
  });

  it("shows live indicator", async () => {
    render(<TradingPage />);

    await waitFor(() => {
      expect(screen.getByText("LIVE")).toBeInTheDocument();
    });
  });

  it("shows summary cards", async () => {
    render(<TradingPage />);

    await waitFor(() => {
      expect(screen.getByText("Portfolio Value")).toBeInTheDocument();
      expect(screen.getByText("Unrealized")).toBeInTheDocument();
      expect(screen.getAllByText(/Positions/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Win Rate")).toBeInTheDocument();
    });
  });

  it("shows empty positions message", async () => {
    render(<TradingPage />);

    await waitFor(() => {
      expect(screen.getAllByText("No open positions").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("renders quick order form", async () => {
    render(<TradingPage />);

    await waitFor(() => {
      expect(screen.getByText("Quick Order")).toBeInTheDocument();
      expect(screen.getByLabelText("Stock Code")).toBeInTheDocument();
      expect(screen.getByLabelText("Order Type")).toBeInTheDocument();
      expect(screen.getByLabelText("Quantity")).toBeInTheDocument();
      expect(screen.getByText("BUY")).toBeInTheDocument();
      expect(screen.getByText("SELL")).toBeInTheDocument();
    });
  });

  it("renders positions tab and orders tab", async () => {
    render(<TradingPage />);

    await waitFor(() => {
      expect(screen.getAllByText(/Positions/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/Open Orders/)).toBeInTheDocument();
    });
  });

  it("shows chart placeholder when no stock selected", async () => {
    render(<TradingPage />);

    await waitFor(() => {
      expect(screen.getByText("Select a position to view chart")).toBeInTheDocument();
    });
  });

  it("fetches data on mount", () => {
    render(<TradingPage />);

    expect(mockFns.fetchPositions).toHaveBeenCalled();
    expect(mockFns.fetchOrders).toHaveBeenCalled();
    expect(mockFns.fetchPortfolioStats).toHaveBeenCalled();
  });

  it("submits a quick order", async () => {
    const user = userEvent.setup();
    mockedApi.post.mockResolvedValue({ data: {} });

    render(<TradingPage />);

    await waitFor(() => {
      expect(screen.getByLabelText("Stock Code")).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText("Stock Code"), "005930");
    await user.type(screen.getByLabelText("Quantity"), "10");
    await user.click(screen.getByText("Submit Order"));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith("/trading/orders", {
        stock_code: "005930",
        side: "buy",
        order_type: "market",
        quantity: 10,
        limit_price: null,
      });
    });
  });

  it("shows success message after order", async () => {
    const user = userEvent.setup();
    mockedApi.post.mockResolvedValue({ data: {} });

    render(<TradingPage />);

    await waitFor(() => {
      expect(screen.getByLabelText("Stock Code")).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText("Stock Code"), "005930");
    await user.type(screen.getByLabelText("Quantity"), "10");
    await user.click(screen.getByText("Submit Order"));

    await waitFor(() => {
      expect(screen.getByText("Order placed successfully!")).toBeInTheDocument();
    });
  });

  it("shows positions when they exist", async () => {
    setupMocks({
      positions: [
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
      ],
      selectedStock: "005930",
    });

    render(<TradingPage />);

    await waitFor(() => {
      expect(screen.getAllByText("삼성전자").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("connects websocket on mount", () => {
    render(<TradingPage />);

    expect(createWSConnection).toHaveBeenCalledWith("trading");
  });
});
