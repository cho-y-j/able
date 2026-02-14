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

const SAMPLE_REPORT = {
  id: "test-id",
  report_date: "2026-02-15",
  status: "completed",
  market_data: {
    "S&P 500": { ticker: "^GSPC", close: 5200.5, change: 52.3, change_pct: 1.02, volume: 3500000000 },
    "나스닥": { ticker: "^IXIC", close: 16500.0, change: 250.0, change_pct: 1.54, volume: 2800000000 },
    "코스피": { ticker: "^KS11", close: 2680.5, change: 15.3, change_pct: 0.57, volume: 450000000 },
    "코스닥": { ticker: "^KQ11", close: 870.2, change: -5.1, change_pct: -0.58, volume: 320000000 },
    "VIX": { ticker: "^VIX", close: 18.5, change: -1.2, change_pct: -6.09, volume: 0 },
    "USD/KRW": { ticker: "KRW=X", close: 1345.5, change: 5.0, change_pct: 0.37, volume: 0 },
    "WTI 원유": { ticker: "CL=F", close: 78.5, change: 2.1, change_pct: 2.75, volume: 800000 },
    "금": { ticker: "GC=F", close: 2350.0, change: 15.0, change_pct: 0.64, volume: 200000 },
    "미국10Y금리": { ticker: "^TNX", close: 4.35, change: 0.05, change_pct: 1.16, volume: 0 },
  },
  themes: [
    {
      name: "AI/반도체",
      relevance_score: 5,
      signals: ["나스닥 +1.5% 강세"],
      leader_stocks: [{ code: "005930", name: "삼성전자" }, { code: "000660", name: "SK하이닉스" }],
      follower_stocks: [{ code: "042700", name: "한미반도체" }],
    },
  ],
  ai_summary: {
    headline: "나스닥 강세에 반도체 주목",
    market_sentiment: "탐욕",
    kospi_direction: "상승",
    key_issues: ["나스닥 1.5% 상승", "유가 강세"],
    risks: ["금리 인상 우려"],
    strategy: "반도체 대장주 중심 매수 유효",
  },
  created_at: "2026-02-15T06:30:00+09:00",
};

describe("MarketPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseRealtimePrice.mockReturnValue({ tick: null, isConnected: false });

    // Default: daily report loads successfully
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/market/daily-report") {
        return Promise.resolve({ data: SAMPLE_REPORT });
      }
      return Promise.reject(new Error("Unknown endpoint"));
    });
  });

  // ─── Daily Briefing Tab ──────────────────────────────────────

  it("renders page title and tab buttons", async () => {
    render(<MarketPage />);

    // Title uses t.market.title which is "Market Data" in test (English locale)
    expect(screen.getByText("Market Data")).toBeInTheDocument();
    expect(screen.getByText(/데일리 브리핑/)).toBeInTheDocument();
    expect(screen.getByText(/종목 검색/)).toBeInTheDocument();
  });

  it("shows daily briefing headline on load", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("나스닥 강세에 반도체 주목")).toBeInTheDocument();
    });
  });

  it("shows market sentiment badge", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText(/탐욕/)).toBeInTheDocument();
    });
  });

  it("shows kospi direction forecast", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText(/코스피 전망/)).toBeInTheDocument();
    });
  });

  it("shows global market cards", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("글로벌 마켓")).toBeInTheDocument();
    });

    expect(screen.getByText("S&P 500")).toBeInTheDocument();
  });

  it("shows AI strategy section", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("오늘의 투자 전략")).toBeInTheDocument();
    });

    expect(screen.getByText("반도체 대장주 중심 매수 유효")).toBeInTheDocument();
  });

  it("shows key issues", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("핵심 이슈")).toBeInTheDocument();
    });

    expect(screen.getByText(/나스닥 1.5% 상승/)).toBeInTheDocument();
  });

  it("shows risk factors", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("리스크 요인")).toBeInTheDocument();
    });

    expect(screen.getByText(/금리 인상 우려/)).toBeInTheDocument();
  });

  it("shows active themes with leader stocks", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("AI/반도체")).toBeInTheDocument();
    });

    expect(screen.getByText("삼성전자")).toBeInTheDocument();
    expect(screen.getByText("SK하이닉스")).toBeInTheDocument();
  });

  it("shows VIX value in header", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      // VIX appears in both hero header and bonds section
      const vixElements = screen.getAllByText(/VIX/);
      expect(vixElements.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows generate button when no report exists", async () => {
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/market/daily-report") {
        return Promise.reject({ response: { status: 404 } });
      }
      return Promise.reject(new Error("Unknown"));
    });

    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("데일리 마켓 인텔리전스")).toBeInTheDocument();
    });

    expect(screen.getByText("지금 리포트 생성")).toBeInTheDocument();
  });

  it("shows loading skeleton while fetching report", () => {
    mockedApi.get.mockImplementation(() => new Promise(() => {})); // Never resolves

    render(<MarketPage />);

    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  // ─── Stock Search Tab ─────────────────────────────────────────

  it("switches to stock search tab", async () => {
    const user = userEvent.setup();
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText(/데일리 브리핑/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/종목 검색/));

    expect(screen.getByText("Stock Lookup")).toBeInTheDocument();
  });

  it("fetches and displays price data on search", async () => {
    const user = userEvent.setup();

    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/market/daily-report") {
        return Promise.resolve({ data: SAMPLE_REPORT });
      }
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

    // Wait for load, switch to search tab
    await waitFor(() => {
      expect(screen.getByText(/종목 검색/)).toBeInTheDocument();
    });
    await user.click(screen.getByText(/종목 검색/));

    // English locale: placeholder is "Search stocks (e.g. 005930)", button is "Search"
    const input = screen.getByPlaceholderText(/005930/);
    await user.type(input, "005930");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(screen.getByText("005930")).toBeInTheDocument();
    });
  });

  it("shows report date badge", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("2026-02-15")).toBeInTheDocument();
    });
  });

  it("shows commodities section", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("원자재")).toBeInTheDocument();
    });
  });

  it("shows FX section", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("환율")).toBeInTheDocument();
    });
  });

  it("shows bonds and futures section", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText(/금리 & 선물/)).toBeInTheDocument();
    });
  });
});
