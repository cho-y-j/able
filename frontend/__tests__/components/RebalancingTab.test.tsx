import { render, screen, waitFor } from "@testing-library/react";
import RebalancingTab from "@/app/dashboard/portfolio/_components/RebalancingTab";
import api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

const mockAllocations = {
  total_capital: 50000000,
  available_cash: 10000000,
  allocated_capital: 40000000,
  unallocated_pct: 20.0,
  recipes: [
    {
      recipe_id: "r1",
      recipe_name: "MACD Strategy",
      is_active: true,
      target_weight_pct: 20.0,
      actual_weight_pct: 16.0,
      actual_value: 8000000,
      target_value: 10000000,
      drift_pct: -4.0,
      stock_codes: ["005930", "000660"],
      positions: [
        { stock_code: "005930", quantity: 80, value: 5600000, weight_pct: 11.2 },
        { stock_code: "000660", quantity: 20, value: 2400000, weight_pct: 4.8 },
      ],
    },
  ],
  warnings: [],
};

const mockConflicts = {
  conflicts: [
    {
      stock_code: "005930",
      recipes: [
        { recipe_id: "r1", recipe_name: "MACD Strategy", position_size_pct: 10 },
        { recipe_id: "r2", recipe_name: "RSI Reversal", position_size_pct: 15 },
      ],
      combined_target_pct: 25,
      current_position_value: 5600000,
      risk_level: "high",
    },
  ],
  total_overlapping_stocks: 1,
  risk_warnings: ["005930: combined target exceeds limit"],
};

const mockSuggestions = {
  suggestions: [
    {
      recipe_id: "r1",
      recipe_name: "MACD Strategy",
      stock_code: "005930",
      action: "buy",
      current_quantity: 80,
      target_quantity: 100,
      delta_quantity: 20,
      estimated_value: 1400000,
      current_price: 70000,
      reason: "Under-allocated",
    },
  ],
  summary: {
    total_buys: 1,
    total_sells: 0,
    total_buy_value: 1400000,
    total_sell_value: 0,
    net_cash_required: 1400000,
    available_cash: 10000000,
    feasible: true,
  },
  warnings: [],
};

const emptyConflicts = { conflicts: [], total_overlapping_stocks: 0, risk_warnings: [] };
const emptySuggestions = {
  suggestions: [],
  summary: { total_buys: 0, total_sells: 0, total_buy_value: 0, total_sell_value: 0, net_cash_required: 0, available_cash: 0, feasible: true },
  warnings: [],
};

function setupMocks(alloc: any, conflicts: any, suggestions: any) {
  mockedApi.get.mockImplementation((url: string) => {
    if (url.includes("recipe-allocations")) return Promise.resolve({ data: alloc });
    if (url.includes("recipe-conflicts")) return Promise.resolve({ data: conflicts });
    return Promise.resolve({ data: suggestions });
  });
}

describe("RebalancingTab", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows loading state initially", () => {
    mockedApi.get.mockReturnValue(new Promise(() => {}));
    render(<RebalancingTab />);
    const pulseElements = document.querySelectorAll(".animate-pulse");
    expect(pulseElements.length).toBeGreaterThan(0);
  });

  it("shows empty state when no active recipes", async () => {
    setupMocks({ ...mockAllocations, recipes: [] }, emptyConflicts, emptySuggestions);
    render(<RebalancingTab />);

    await waitFor(() => {
      // English text from jest.setup.ts i18n mock
      expect(screen.getByText(/No active recipes/)).toBeInTheDocument();
    });
  });

  it("renders recipe allocation cards with drift", async () => {
    setupMocks(mockAllocations, emptyConflicts, mockSuggestions);
    render(<RebalancingTab />);

    await waitFor(() => {
      expect(screen.getByText("MACD Strategy")).toBeInTheDocument();
    });

    // Drift badge
    expect(screen.getByText("-4.0%")).toBeInTheDocument();
    // Stock codes in allocation card
    expect(screen.getAllByText("005930").length).toBeGreaterThan(0);
    expect(screen.getByText("000660")).toBeInTheDocument();
  });

  it("shows conflict alerts", async () => {
    setupMocks(mockAllocations, mockConflicts, mockSuggestions);
    render(<RebalancingTab />);

    await waitFor(() => {
      expect(screen.getByText("HIGH")).toBeInTheDocument();
    });

    // Combined target text
    expect(screen.getByText(/Combined Target: 25%/)).toBeInTheDocument();
  });

  it("shows no conflicts message", async () => {
    setupMocks(mockAllocations, emptyConflicts, mockSuggestions);
    render(<RebalancingTab />);

    await waitFor(() => {
      // English i18n key: "No stock conflicts detected."
      expect(screen.getByText("No stock conflicts detected.")).toBeInTheDocument();
    });
  });

  it("renders rebalancing suggestions table with buy action", async () => {
    setupMocks(mockAllocations, emptyConflicts, mockSuggestions);
    render(<RebalancingTab />);

    await waitFor(() => {
      // "매수" is hardcoded Korean in the component
      expect(screen.getByText("매수")).toBeInTheDocument();
    });

    expect(screen.getByText("+20")).toBeInTheDocument();
  });

  it("shows feasibility indicator as not feasible", async () => {
    setupMocks(mockAllocations, emptyConflicts, {
      ...mockSuggestions,
      summary: { ...mockSuggestions.summary, feasible: false },
      warnings: ["Insufficient cash"],
    });
    render(<RebalancingTab />);

    await waitFor(() => {
      // English i18n key: "Insufficient Cash"
      expect(screen.getByText("Insufficient Cash")).toBeInTheDocument();
    });
  });
});
