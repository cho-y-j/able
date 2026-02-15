import { render, screen, waitFor } from "@testing-library/react";
import DashboardPage from "@/app/dashboard/page";
import { useAuthStore } from "@/store/auth";
import { useTradingStore } from "@/store/trading";
import api from "@/lib/api";

jest.mock("@/lib/api");
jest.mock("@/store/auth");
jest.mock("@/store/trading");
jest.mock("@/app/dashboard/portfolio/_components/Treemap", () => {
  return function MockTreemap({ items }: { items: unknown[] }) {
    return <div data-testid="treemap">{items.length} items</div>;
  };
});

const mockedApi = api as jest.Mocked<typeof api>;
const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;
const mockedUseTradingStore = useTradingStore as unknown as jest.Mock;

describe("DashboardPage", () => {
  const mockFetchUser = jest.fn();
  const mockFetchPositions = jest.fn();

  function setupMocks(overrides?: {
    user?: Record<string, unknown> | null;
    positions?: Array<Record<string, unknown>>;
  }) {
    const authState = {
      user: overrides?.user ?? { id: "u1", email: "test@example.com", display_name: "Trader Kim" },
      fetchUser: mockFetchUser,
    };

    const tradingState = {
      positions: overrides?.positions ?? [],
      fetchPositions: mockFetchPositions,
      updatePositionPrice: jest.fn(),
    };

    mockedUseAuthStore.mockImplementation((selector?: (s: unknown) => unknown) =>
      selector ? selector(authState) : authState,
    );

    mockedUseTradingStore.mockImplementation((selector?: (s: unknown) => unknown) =>
      selector ? selector(tradingState) : tradingState,
    );
  }

  function setupApiMocks(overrides?: Record<string, unknown>) {
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/market/balance") {
        return Promise.resolve({
          data: { total_balance: 10_000_000, available_cash: 5_000_000, invested_amount: 5_000_000, total_pnl: 200_000 },
        });
      }
      if (url === "/strategies") {
        return Promise.resolve({ data: [{ id: "s1" }, { id: "s2" }] });
      }
      if (url === "/agents/status") {
        return Promise.resolve({
          data: overrides?.agentStatus ?? {
            status: "active",
            recent_actions: [
              { agent: "analyst", action: "market_analysis", timestamp: new Date().toISOString() },
              { agent: "executor", action: "order_placed", timestamp: new Date().toISOString() },
            ],
          },
        });
      }
      if (url === "/recipes") {
        return Promise.resolve({
          data: overrides?.recipes ?? [
            {
              id: "r1", name: "Momentum Recipe", is_active: true,
              stock_codes: ["005930"], signal_config: { signals: [], combinator: "AND" },
              custom_filters: {}, risk_config: {}, is_template: false,
              created_at: "2026-01-01", updated_at: "2026-01-01",
            },
            {
              id: "r2", name: "Mean Reversion", is_active: false,
              stock_codes: [], signal_config: { signals: [], combinator: "AND" },
              custom_filters: {}, risk_config: {}, is_template: false,
              created_at: "2026-01-01", updated_at: "2026-01-01",
            },
          ],
        });
      }
      if (url === "/trading/portfolio/analytics") {
        return Promise.resolve({
          data: overrides?.analytics ?? {
            portfolio_value: 10000000,
            allocation: [
              { stock_code: "005930", stock_name: "삼성전자", value: 7000000, weight: 70, pnl_pct: 2.5 },
              { stock_code: "035420", stock_name: "NAVER", value: 3000000, weight: 30, pnl_pct: -1.0 },
            ],
            trade_stats: { total_trades: 5, win_rate: 60, profit_factor: 1.5, winning_trades: 3, losing_trades: 2 },
          },
        });
      }
      return Promise.reject(new Error("Unknown endpoint"));
    });
  }

  beforeEach(() => {
    jest.clearAllMocks();
    setupMocks();
    setupApiMocks();
  });

  it("renders welcome message with user name", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Welcome back, Trader Kim")).toBeInTheDocument();
    });
  });

  it("shows default name when display_name is null", async () => {
    setupMocks({ user: { id: "u1", email: "test@example.com", display_name: null } });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Welcome back, Trader")).toBeInTheDocument();
    });
  });

  it("renders summary cards", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Total Balance")).toBeInTheDocument();
      expect(screen.getByText("Today P&L")).toBeInTheDocument();
      expect(screen.getByText("Active Strategies")).toBeInTheDocument();
      expect(screen.getByText("AI Agent Status")).toBeInTheDocument();
    });
  });

  it("shows empty positions message", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      const matches = screen.getAllByText(
        "No open positions. Configure your API keys in Settings to start trading.",
      );
      expect(matches.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("renders quick start actions", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("1. Setup API Keys")).toBeInTheDocument();
      expect(screen.getByText("2. Search Strategies")).toBeInTheDocument();
      expect(screen.getByText("3. Start AI Agent")).toBeInTheDocument();
    });
  });

  it("fetches user and positions on mount", () => {
    render(<DashboardPage />);

    expect(mockFetchUser).toHaveBeenCalled();
    expect(mockFetchPositions).toHaveBeenCalled();
  });

  it("renders positions table when positions exist", async () => {
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
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText("삼성전자").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Open Positions")).toBeInTheDocument();
    });
  });

  it("quick action links point to correct routes", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      const settingsLink = screen.getByText("1. Setup API Keys").closest("a");
      expect(settingsLink).toHaveAttribute("href", "/dashboard/settings");

      const strategiesLink = screen.getByText("2. Search Strategies").closest("a");
      expect(strategiesLink).toHaveAttribute("href", "/dashboard/strategies");

      const agentsLink = screen.getByText("3. Start AI Agent").closest("a");
      expect(agentsLink).toHaveAttribute("href", "/dashboard/agents");
    });
  });

  // New tests for Insights Row

  it("renders portfolio overview widget with treemap", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Portfolio Overview")).toBeInTheDocument();
      expect(screen.getByTestId("treemap")).toBeInTheDocument();
      expect(screen.getByTestId("treemap")).toHaveTextContent("2 items");
    });
  });

  it("shows empty state for treemap when no positions", async () => {
    setupApiMocks({ analytics: { portfolio_value: 0, allocation: [], trade_stats: {} } });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("No positions to display.")).toBeInTheDocument();
    });
  });

  it("renders active recipes widget", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getAllByText("Active Recipes").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Momentum Recipe")).toBeInTheDocument();
    });
  });

  it("shows active recipe count", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("1")).toBeInTheDocument();
      expect(screen.getByText(/2 recipes/)).toBeInTheDocument();
    });
  });

  it("renders recent activity feed", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Recent Activity")).toBeInTheDocument();
      expect(screen.getByText(/analyst:/)).toBeInTheDocument();
      expect(screen.getByText(/market_analysis/)).toBeInTheDocument();
    });
  });

  it("shows empty state for activity when no actions", async () => {
    setupApiMocks({ agentStatus: { status: "idle", recent_actions: [] } });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("No recent agent activity.")).toBeInTheDocument();
    });
  });
});
