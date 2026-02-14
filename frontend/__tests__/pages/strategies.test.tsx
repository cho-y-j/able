import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import StrategiesPage from "@/app/dashboard/strategies/page";
import api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

describe("StrategiesPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Default: /strategies returns empty array
    mockedApi.get.mockResolvedValue({ data: [] });
    mockedApi.post.mockResolvedValue({ data: {} });

    window.alert = jest.fn();
  });

  it("renders page title", async () => {
    render(<StrategiesPage />);

    await waitFor(() => {
      expect(screen.getByText("Trading Strategies")).toBeInTheDocument();
    });
  });

  it("renders AI search section", async () => {
    render(<StrategiesPage />);

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("Stock code (e.g., 005930 for Samsung)")
      ).toBeInTheDocument();
      expect(screen.getByText("Search Strategy")).toBeInTheDocument();
    });
  });

  it("shows empty strategies message", async () => {
    render(<StrategiesPage />);

    await waitFor(() => {
      expect(
        screen.getByText(
          "No strategies yet. Use AI Strategy Search above to find optimal strategies."
        )
      ).toBeInTheDocument();
    });
  });

  it("fetches and displays strategies", async () => {
    mockedApi.get.mockResolvedValue({
      data: [
        {
          id: "s1",
          name: "MACD Crossover",
          stock_code: "005930",
          stock_name: "Samsung",
          strategy_type: "momentum",
          composite_score: 85.5,
          status: "active",
          is_auto_trading: true,
          created_at: "2025-01-01T00:00:00Z",
        },
        {
          id: "s2",
          name: "RSI Mean Reversion",
          stock_code: "035720",
          stock_name: "Kakao",
          strategy_type: "mean_reversion",
          composite_score: 62.3,
          status: "validated",
          is_auto_trading: false,
          created_at: "2025-01-02T00:00:00Z",
        },
      ],
    });

    render(<StrategiesPage />);

    await waitFor(() => {
      expect(screen.getByText("My Strategies (2)")).toBeInTheDocument();
      expect(screen.getByText("MACD Crossover")).toBeInTheDocument();
      expect(screen.getByText("RSI Mean Reversion")).toBeInTheDocument();
      expect(screen.getByText("active")).toBeInTheDocument();
      expect(screen.getByText("validated")).toBeInTheDocument();
      expect(screen.getByText(/85\.5/)).toBeInTheDocument();
      expect(screen.getByText(/62\.3/)).toBeInTheDocument();
    });
  });

  it("starts strategy search", async () => {
    const user = userEvent.setup();

    render(<StrategiesPage />);

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("Stock code (e.g., 005930 for Samsung)")
      ).toBeInTheDocument();
    });

    await user.type(
      screen.getByPlaceholderText("Stock code (e.g., 005930 for Samsung)"),
      "005930"
    );
    await user.click(screen.getByText("Search Strategy"));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith("/strategies/search", {
        stock_code: "005930",
        date_range_start: "2024-01-01",
        date_range_end: "2025-12-31",
        optimization_method: "grid",
      });
    });
  });

  it("shows search started alert", async () => {
    const user = userEvent.setup();

    render(<StrategiesPage />);

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("Stock code (e.g., 005930 for Samsung)")
      ).toBeInTheDocument();
    });

    await user.type(
      screen.getByPlaceholderText("Stock code (e.g., 005930 for Samsung)"),
      "005930"
    );
    await user.click(screen.getByText("Search Strategy"));

    await waitFor(() => {
      expect(window.alert).toHaveBeenCalledWith(
        "Strategy search started for 005930"
      );
    });
  });

  it("toggles auto trading", async () => {
    const user = userEvent.setup();

    mockedApi.get.mockResolvedValue({
      data: [
        {
          id: "s1",
          name: "MACD Crossover",
          stock_code: "005930",
          stock_name: "Samsung",
          strategy_type: "momentum",
          composite_score: 75.0,
          status: "active",
          is_auto_trading: false,
          created_at: "2025-01-01T00:00:00Z",
        },
      ],
    });

    render(<StrategiesPage />);

    await waitFor(() => {
      expect(screen.getByText("Activate")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Activate"));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith("/strategies/s1/activate");
    });
  });
});
