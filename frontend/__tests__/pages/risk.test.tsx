import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import RiskPage from "@/app/dashboard/risk/page";

// Mock next/navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
  usePathname: () => "/dashboard/risk",
}));

// Mock API
const mockGet = jest.fn();
jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: { get: (...args: unknown[]) => mockGet(...args) },
}));

const mockRiskData = {
  portfolio_value: 10_000_000,
  confidence: 0.95,
  horizon_days: 1,
  var: {
    historical: { var: 500_000, var_pct: 5.0, cvar: 750_000, cvar_pct: 7.5 },
    parametric: { var: 480_000, var_pct: 4.8, cvar: 720_000, cvar_pct: 7.2 },
    monte_carlo: { var: 520_000, var_pct: 5.2, cvar: 780_000, cvar_pct: 7.8 },
  },
  stress_tests: [
    {
      scenario: "market_crash",
      description: "Broad market crash (-15%)",
      impact: -1_500_000,
      impact_pct: -15.0,
      positions: [
        { stock_code: "005930", current_value: 5_000_000, shock_pct: -15, impact: -750_000 },
        { stock_code: "000660", current_value: 5_000_000, shock_pct: -15, impact: -750_000 },
      ],
    },
    {
      scenario: "flash_crash",
      description: "Flash crash (-7%)",
      impact: -700_000,
      impact_pct: -7.0,
      positions: [
        { stock_code: "005930", current_value: 5_000_000, shock_pct: -7, impact: -350_000 },
      ],
    },
  ],
};

describe("RiskPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows loading state initially", () => {
    mockGet.mockReturnValue(new Promise(() => {})); // never resolves
    render(<RiskPage />);
    expect(screen.getByText("Loading risk analysis...")).toBeTruthy();
  });

  it("renders risk data after loading", async () => {
    mockGet.mockResolvedValue({ data: mockRiskData });
    render(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByText("Risk Analysis")).toBeTruthy();
    });

    // VaR method labels
    expect(screen.getByText("Historical")).toBeTruthy();
    expect(screen.getByText("Parametric")).toBeTruthy();
    expect(screen.getByText("Monte Carlo")).toBeTruthy();
  });

  it("shows stress test scenarios", async () => {
    mockGet.mockResolvedValue({ data: mockRiskData });
    render(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByText("Stress Test Scenarios")).toBeTruthy();
    });

    expect(screen.getAllByText("market crash").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("flash crash").length).toBeGreaterThanOrEqual(1);
  });

  it("expands stress test to show positions", async () => {
    mockGet.mockResolvedValue({ data: mockRiskData });
    render(<RiskPage />);

    await waitFor(() => {
      expect(screen.getAllByText("market crash").length).toBeGreaterThanOrEqual(1);
    });

    // Click to expand — find the button via the description text (unique)
    const desc = screen.getByText("Broad market crash (-15%)");
    const btn = desc.closest("button");
    expect(btn).toBeTruthy();
    fireEvent.click(btn!);

    await waitFor(() => {
      expect(screen.getByText("005930")).toBeTruthy();
      expect(screen.getByText("000660")).toBeTruthy();
    });
  });

  it("shows empty state when no positions", async () => {
    mockGet.mockResolvedValue({
      data: {
        portfolio_value: 0,
        confidence: 0.95,
        horizon_days: 1,
        var: {},
        stress_tests: [],
        message: "No open positions for risk analysis",
      },
    });
    render(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByText("No open positions for risk analysis")).toBeTruthy();
    });
  });

  it("renders confidence and horizon selectors", async () => {
    mockGet.mockResolvedValue({ data: mockRiskData });
    render(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByText("Risk Analysis")).toBeTruthy();
    });

    expect(screen.getByText("Confidence")).toBeTruthy();
    expect(screen.getByText("Horizon")).toBeTruthy();
  });

  it("calls API with correct parameters", async () => {
    mockGet.mockResolvedValue({ data: mockRiskData });
    render(<RiskPage />);

    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith(
        "/trading/portfolio/risk?confidence=0.95&horizon_days=1"
      );
    });
  });

  it("displays VaR comparison section with progress bars", async () => {
    mockGet.mockResolvedValue({ data: mockRiskData });
    render(<RiskPage />);

    await waitFor(() => {
      expect(screen.getByText("Value at Risk Comparison")).toBeTruthy();
    });

    // Check VaR labels exist
    const varLabels = screen.getAllByText("VaR");
    expect(varLabels.length).toBeGreaterThanOrEqual(3);

    const cvarLabels = screen.getAllByText("CVaR");
    expect(cvarLabels.length).toBeGreaterThanOrEqual(3);
  });
});
