import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MarketPage from "@/app/dashboard/market/page";
import api from "@/lib/api";
import { useRealtimePrice } from "@/lib/useRealtimePrice";

jest.mock("@/lib/api");
jest.mock("@/lib/useRealtimePrice", () => ({
  useRealtimePrice: jest.fn(() => ({ tick: null, isConnected: false })),
}));

const mockedApi = api as jest.Mocked<typeof api>;
const mockedUseRealtimePrice = useRealtimePrice as jest.Mock;

describe("MarketPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseRealtimePrice.mockReturnValue({ tick: null, isConnected: false });
  });

  it("renders page title", () => {
    render(<MarketPage />);

    expect(screen.getByText("Market Data")).toBeInTheDocument();
  });

  it("renders search input and button", () => {
    render(<MarketPage />);

    expect(
      screen.getByPlaceholderText("Search stocks (e.g. 005930)"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Search" })).toBeInTheDocument();
  });

  it("fetches and displays price data on search", async () => {
    const user = userEvent.setup();

    mockedApi.get.mockImplementation((url: string) => {
      if (url.startsWith("/market/price/")) {
        return Promise.resolve({
          data: {
            stock_code: "005930",
            current_price: 75000,
            change: 1500,
            change_percent: 2.04,
            volume: 12345678,
            high: 76000,
            low: 73000,
          },
        });
      }
      if (url.startsWith("/market/ohlcv/")) {
        return Promise.resolve({ data: { data: [] } });
      }
      return Promise.reject(new Error("Unknown endpoint"));
    });

    render(<MarketPage />);

    const input = screen.getByPlaceholderText("Search stocks (e.g. 005930)");
    await user.type(input, "005930");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText("005930")).toBeInTheDocument();
    });

    expect(screen.getByText("Change")).toBeInTheDocument();
    expect(screen.getByText("Volume")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText("Low")).toBeInTheDocument();
  });

  it("shows LIVE badge when connected", async () => {
    const user = userEvent.setup();

    mockedUseRealtimePrice.mockReturnValue({ tick: null, isConnected: true });

    mockedApi.get.mockImplementation((url: string) => {
      if (url.startsWith("/market/price/")) {
        return Promise.resolve({
          data: {
            stock_code: "005930",
            current_price: 75000,
            change: 1500,
            change_percent: 2.04,
            volume: 12345678,
            high: 76000,
            low: 73000,
          },
        });
      }
      if (url.startsWith("/market/ohlcv/")) {
        return Promise.resolve({ data: { data: [] } });
      }
      return Promise.reject(new Error("Unknown endpoint"));
    });

    render(<MarketPage />);

    const input = screen.getByPlaceholderText("Search stocks (e.g. 005930)");
    await user.type(input, "005930");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText("LIVE")).toBeInTheDocument();
    });
  });

  it("shows chart section", () => {
    render(<MarketPage />);

    expect(screen.getByText("Price Chart")).toBeInTheDocument();
  });
});
