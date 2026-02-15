import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RecipeMonitorPage from "@/app/dashboard/recipes/monitor/page";
import api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
    back: jest.fn(),
    prefetch: jest.fn(),
  }),
  usePathname: () => "/dashboard/recipes/monitor",
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
}));

jest.mock("@/lib/useTradingWebSocket", () => ({
  useTradingWebSocket: jest.fn(),
}));

const mockRecipes = [
  {
    id: "r1",
    name: "Momentum Recipe",
    description: "Momentum strategy",
    signal_config: { combinator: "AND", signals: [] },
    custom_filters: {},
    stock_codes: ["005930", "000660"],
    risk_config: {},
    is_active: true,
    is_template: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "r2",
    name: "RSI Recipe",
    description: "RSI-based",
    signal_config: { combinator: "OR", signals: [] },
    custom_filters: {},
    stock_codes: ["035420"],
    risk_config: {},
    is_active: true,
    is_template: false,
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
  {
    id: "r3",
    name: "Inactive Recipe",
    description: "Not active",
    signal_config: { combinator: "AND", signals: [] },
    custom_filters: {},
    stock_codes: ["005380"],
    risk_config: {},
    is_active: false,
    is_template: false,
    created_at: "2026-01-03T00:00:00Z",
    updated_at: "2026-01-03T00:00:00Z",
  },
];

const mockOrders = [
  {
    id: "o1",
    stock_code: "005930",
    side: "buy",
    quantity: 10,
    avg_fill_price: 72000,
    status: "filled",
    created_at: "2026-02-15T10:00:00Z",
  },
  {
    id: "o2",
    stock_code: "000660",
    side: "sell",
    quantity: 5,
    avg_fill_price: null,
    status: "failed",
    created_at: "2026-02-15T10:30:00Z",
  },
];

describe("RecipeMonitorPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders active recipe cards (filters out inactive)", async () => {
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/recipes") return Promise.resolve({ data: mockRecipes });
      if (url.includes("/orders")) return Promise.resolve({ data: [] });
      return Promise.resolve({ data: [] });
    });

    await act(async () => {
      render(<RecipeMonitorPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Momentum Recipe")).toBeInTheDocument();
      expect(screen.getByText("RSI Recipe")).toBeInTheDocument();
    });

    // Inactive recipe should NOT be shown
    expect(screen.queryByText("Inactive Recipe")).not.toBeInTheDocument();
  });

  it("shows empty state when no active recipes", async () => {
    const allInactive = mockRecipes.map((r) => ({ ...r, is_active: false }));
    mockedApi.get.mockResolvedValueOnce({ data: allInactive });

    await act(async () => {
      render(<RecipeMonitorPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("No active recipes")).toBeInTheDocument();
    });

    expect(screen.getAllByText("Go to Recipes").length).toBeGreaterThanOrEqual(1);
  });

  it("displays order statistics for a recipe", async () => {
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/recipes")
        return Promise.resolve({ data: [mockRecipes[0]] }); // only first active
      if (url.includes("/orders"))
        return Promise.resolve({ data: mockOrders });
      return Promise.resolve({ data: [] });
    });

    await act(async () => {
      render(<RecipeMonitorPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Momentum Recipe")).toBeInTheDocument();
    });

    // Order count = 2
    await waitFor(() => {
      expect(screen.getByText("2")).toBeInTheDocument();
    });

    // Stock codes visible (may appear in both badge and orders)
    expect(screen.getAllByText("005930").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("000660").length).toBeGreaterThanOrEqual(1);
  });

  it("navigates to recipe detail on view detail click", async () => {
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/recipes")
        return Promise.resolve({ data: [mockRecipes[0]] });
      if (url.includes("/orders")) return Promise.resolve({ data: [] });
      return Promise.resolve({ data: [] });
    });

    await act(async () => {
      render(<RecipeMonitorPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("Momentum Recipe")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByText("View Detail"));

    expect(mockPush).toHaveBeenCalledWith("/dashboard/recipes/r1");
  });

  it("shows active recipes count badge", async () => {
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/recipes") return Promise.resolve({ data: mockRecipes });
      if (url.includes("/orders")) return Promise.resolve({ data: [] });
      return Promise.resolve({ data: [] });
    });

    await act(async () => {
      render(<RecipeMonitorPage />);
    });

    await waitFor(() => {
      expect(screen.getByText(/2 Active Recipes/)).toBeInTheDocument();
    });
  });

  it("displays recent orders in card", async () => {
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/recipes")
        return Promise.resolve({ data: [mockRecipes[0]] });
      if (url.includes("/orders"))
        return Promise.resolve({ data: mockOrders });
      return Promise.resolve({ data: [] });
    });

    await act(async () => {
      render(<RecipeMonitorPage />);
    });

    await waitFor(() => {
      expect(screen.getByText("filled")).toBeInTheDocument();
      expect(screen.getByText("failed")).toBeInTheDocument();
    });
  });
});
