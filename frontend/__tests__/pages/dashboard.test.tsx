import { render, screen, waitFor, fireEvent } from "@testing-library/react";
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
      if (url.startsWith("/rankings/trending")) {
        return Promise.resolve({
          data: overrides?.trending ?? [
            { rank: 1, stock_name: "삼성전자", stock_code: "005930", search_ratio: 12.5, price: 78000, change_pct: 2.63 },
            { rank: 2, stock_name: "SK하이닉스", stock_code: "000660", search_ratio: 8.3, price: 195000, change_pct: -1.2 },
          ],
        });
      }
      if (url === "/factors/global") {
        return Promise.resolve({
          data: overrides?.globalFactors ?? [
            { factor_name: "kospi_change_pct", value: 1.25 },
            { factor_name: "nasdaq_change_pct", value: -0.8 },
            { factor_name: "kospi_value", value: 2650 },
          ],
        });
      }
      return Promise.reject(new Error("Unknown endpoint"));
    });
  }

  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
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

  // Insights Row

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
      expect(screen.getByText(/2 recipes/)).toBeInTheDocument();
      expect(screen.getByText("Momentum Recipe")).toBeInTheDocument();
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

  // Widget customization tests

  it("renders customize button", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId("customize-btn")).toBeInTheDocument();
      expect(screen.getByTestId("customize-btn")).toHaveTextContent("Customize");
    });
  });

  it("opens customize panel on button click", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId("customize-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("customize-btn"));

    expect(screen.getByTestId("customize-panel")).toBeInTheDocument();
    expect(screen.getByText("Customize Widgets")).toBeInTheDocument();
    expect(screen.getByTestId("customize-btn")).toHaveTextContent("Done");
  });

  it("shows all widget toggles in customize panel", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId("customize-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("customize-btn"));

    expect(screen.getByTestId("toggle-summary")).toBeInTheDocument();
    expect(screen.getByTestId("toggle-portfolio")).toBeInTheDocument();
    expect(screen.getByTestId("toggle-recipes")).toBeInTheDocument();
    expect(screen.getByTestId("toggle-activity")).toBeInTheDocument();
    expect(screen.getByTestId("toggle-positions")).toBeInTheDocument();
    expect(screen.getByTestId("toggle-quickstart")).toBeInTheDocument();
    expect(screen.getByTestId("toggle-trending")).toBeInTheDocument();
    expect(screen.getByTestId("toggle-indices")).toBeInTheDocument();
  });

  it("hides widget when toggled off", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("1. Setup API Keys")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("customize-btn"));
    fireEvent.click(screen.getByTestId("toggle-quickstart"));

    // The quick start widget content should disappear (labels in panel remain)
    expect(screen.queryByText("1. Setup API Keys")).not.toBeInTheDocument();
  });

  it("persists widget config to localStorage", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId("customize-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("customize-btn"));
    fireEvent.click(screen.getByTestId("toggle-quickstart"));

    const saved = JSON.parse(localStorage.getItem("dashboard-widgets") || "[]");
    const quickstart = saved.find((w: { id: string }) => w.id === "quickstart");
    expect(quickstart.visible).toBe(false);
  });

  it("resets to default on reset button click", async () => {
    // Pre-set a custom config
    localStorage.setItem(
      "dashboard-widgets",
      JSON.stringify([
        { id: "summary", visible: false },
        { id: "portfolio", visible: true },
        { id: "recipes", visible: true },
        { id: "activity", visible: true },
        { id: "positions", visible: true },
        { id: "quickstart", visible: true },
        { id: "trending", visible: true },
        { id: "indices", visible: true },
      ]),
    );

    render(<DashboardPage />);

    // Summary should be hidden initially
    await waitFor(() => {
      expect(screen.queryByText("Total Balance")).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("customize-btn"));
    fireEvent.click(screen.getByTestId("reset-btn"));

    // After reset, summary should be visible again
    await waitFor(() => {
      expect(screen.getByText("Total Balance")).toBeInTheDocument();
    });
  });

  it("has move up/down buttons for widget reordering", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId("customize-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("customize-btn"));

    expect(screen.getByTestId("move-up-summary")).toBeInTheDocument();
    expect(screen.getByTestId("move-down-summary")).toBeInTheDocument();
    expect(screen.getByTestId("move-up-summary")).toBeDisabled();
  });

  it("moves widget down when down arrow clicked", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId("customize-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("customize-btn"));
    fireEvent.click(screen.getByTestId("move-down-summary"));

    const saved = JSON.parse(localStorage.getItem("dashboard-widgets") || "[]");
    expect(saved[0].id).toBe("portfolio");
    expect(saved[1].id).toBe("summary");
  });

  // Trending and Indices widgets

  it("renders trending stocks widget", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Trending Stocks")).toBeInTheDocument();
      expect(screen.getAllByText("삼성전자").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("SK하이닉스")).toBeInTheDocument();
    });
  });

  it("renders market indices widget", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Market Indices")).toBeInTheDocument();
      expect(screen.getByText("KOSPI")).toBeInTheDocument();
      expect(screen.getByText("NASDAQ")).toBeInTheDocument();
    });
  });

  it("shows empty trending when no data", async () => {
    setupApiMocks({ trending: [] });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("No trending data")).toBeInTheDocument();
    });
  });

  it("shows empty indices when no data", async () => {
    setupApiMocks({ globalFactors: [] });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("No index data")).toBeInTheDocument();
    });
  });

  it("loads widget config from localStorage on mount", async () => {
    localStorage.setItem(
      "dashboard-widgets",
      JSON.stringify([
        { id: "summary", visible: true },
        { id: "portfolio", visible: false },
        { id: "recipes", visible: true },
        { id: "activity", visible: true },
        { id: "positions", visible: true },
        { id: "quickstart", visible: true },
        { id: "trending", visible: true },
        { id: "indices", visible: true },
      ]),
    );

    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Total Balance")).toBeInTheDocument();
    });

    // Portfolio should be hidden
    expect(screen.queryByText("Portfolio Overview")).not.toBeInTheDocument();
  });

  it("fetches trending and global factor data", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(mockedApi.get).toHaveBeenCalledWith("/rankings/trending?limit=5");
      expect(mockedApi.get).toHaveBeenCalledWith("/factors/global");
    });
  });

  it("closes customize panel when Done clicked", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByTestId("customize-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("customize-btn"));
    expect(screen.getByTestId("customize-panel")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("customize-btn"));
    expect(screen.queryByTestId("customize-panel")).not.toBeInTheDocument();
  });
});
