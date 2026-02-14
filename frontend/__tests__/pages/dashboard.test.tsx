import { render, screen, waitFor } from "@testing-library/react";
import DashboardPage from "@/app/dashboard/page";
import { useAuthStore } from "@/store/auth";
import { useTradingStore } from "@/store/trading";
import api from "@/lib/api";

jest.mock("@/lib/api");
jest.mock("@/store/auth");
jest.mock("@/store/trading");

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
    };

    mockedUseAuthStore.mockImplementation((selector?: (s: unknown) => unknown) =>
      selector ? selector(authState) : authState,
    );

    mockedUseTradingStore.mockImplementation((selector?: (s: unknown) => unknown) =>
      selector ? selector(tradingState) : tradingState,
    );
  }

  beforeEach(() => {
    jest.clearAllMocks();

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
        return Promise.resolve({ data: { status: "active" } });
      }
      return Promise.reject(new Error("Unknown endpoint"));
    });

    setupMocks();
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
      expect(screen.getByText("삼성전자")).toBeInTheDocument();
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
});
