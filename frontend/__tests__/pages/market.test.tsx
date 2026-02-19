import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MarketPage from "@/app/dashboard/market/page";
import api from "@/lib/api";
import { useRealtimePrice } from "@/lib/useRealtimePrice";

jest.mock("@/lib/api");
jest.mock("@/lib/useRealtimePrice", () => ({
  useRealtimePrice: jest.fn(() => ({ tick: null, isConnected: false })),
}));
jest.mock("@/lib/useStockSearch", () => ({
  useStockSearch: () => ({ results: [], loading: false }),
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
    // US stock data
    us_stocks: {
      NVDA: { ticker: "NVDA", name: "NVIDIA", close: 140, change: 5.4, change_pct: 4.01, volume: 50000000 },
      AMD: { ticker: "AMD", name: "AMD", close: 170, change: 3.4, change_pct: 2.04, volume: 30000000 },
    },
    us_sectors: {
      SOXX: { ticker: "SOXX", name: "Semiconductor", kr_name: "반도체", close: 230, change_pct: 2.5 },
      XLK: { ticker: "XLK", name: "Technology", kr_name: "기술", close: 200, change_pct: 1.2 },
      XLE: { ticker: "XLE", name: "Energy", kr_name: "에너지", close: 90, change_pct: -0.5 },
    },
    us_rankings: {
      gainers: [
        { ticker: "NVDA", name: "NVIDIA", close: 140, change_pct: 4.01, themes: ["AI/반도체"] },
        { ticker: "AMD", name: "AMD", close: 170, change_pct: 2.04, themes: ["AI/반도체"] },
      ],
      losers: [
        { ticker: "TSLA", name: "Tesla", close: 250, change_pct: -1.96, themes: ["2차전지/배터리"] },
      ],
    },
  },
  themes: [
    {
      name: "AI/반도체",
      relevance_score: 8,
      signals: ["NVIDIA(NVDA) +4.0% 상승"],
      us_movers: [
        { ticker: "NVDA", name: "NVIDIA", change_pct: 4.01 },
        { ticker: "AMD", name: "AMD", change_pct: 2.04 },
      ],
      leader_stocks: [{ code: "005930", name: "삼성전자" }, { code: "000660", name: "SK하이닉스" }],
      follower_stocks: [{ code: "042700", name: "한미반도체" }],
    },
  ],
  ai_summary: {
    headline: "NVDA 급등에 반도체 랠리",
    market_sentiment: "탐욕",
    kospi_direction: "상승",
    us_market_analysis: "NVDA +4.01% 급등으로 AI 반도체 강세",
    key_issues: ["NVDA +4% 상승", "유가 강세"],
    watchlist: ["삼성전자(005930) — AI/반도체 — NVDA 수혜"],
    watchlist_data: [
      {
        code: "005930",
        name: "삼성전자",
        theme: "AI/반도체",
        role: "대장주",
        relevance: 8,
        us_drivers: ["NVIDIA +4.0%", "AMD +2.0%"],
        reason: "AI/반도체 테마 — NVIDIA +4.0%, AMD +2.0%",
      },
      {
        code: "000660",
        name: "SK하이닉스",
        theme: "AI/반도체",
        role: "대장주",
        relevance: 8,
        us_drivers: ["NVIDIA +4.0%"],
        reason: "AI/반도체 테마 — NVIDIA +4.0%",
      },
    ],
    risks: ["금리 인상 우려"],
    strategy: "반도체 대장주 중심 매수 유효",
  },
  created_at: "2026-02-15T06:30:00+09:00",
};

describe("MarketPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseRealtimePrice.mockReturnValue({ tick: null, isConnected: false });

    // Default: daily report + history loads successfully
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/market/daily-report" || url.startsWith("/market/daily-report?")) {
        return Promise.resolve({ data: SAMPLE_REPORT });
      }
      if (url.startsWith("/market/daily-reports")) {
        return Promise.resolve({ data: [
          { id: "r1", report_date: "2026-02-15", headline: "NVDA 급등에 반도체 랠리", market_sentiment: "탐욕", kospi_direction: "상승" },
          { id: "r2", report_date: "2026-02-14", headline: "기술주 반등 시작", market_sentiment: "중립", kospi_direction: "보합" },
        ] });
      }
      return Promise.reject(new Error("Unknown endpoint"));
    });
  });

  // ─── Daily Briefing Tab ──────────────────────────────────────

  it("renders page title and tab buttons", async () => {
    render(<MarketPage />);

    expect(screen.getByText("Market Data")).toBeInTheDocument();
    expect(screen.getByText(/데일리 브리핑/)).toBeInTheDocument();
    expect(screen.getByText(/종목 검색/)).toBeInTheDocument();
  });

  it("shows daily briefing headline on load", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      const headlineEls = screen.getAllByText("NVDA 급등에 반도체 랠리");
      expect(headlineEls.length).toBeGreaterThanOrEqual(1);
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

    expect(screen.getByText(/NVDA \+4% 상승/)).toBeInTheDocument();
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
      const themeEls = screen.getAllByText("AI/반도체");
      expect(themeEls.length).toBeGreaterThanOrEqual(1);
    });

    const samsung = screen.getAllByText("삼성전자");
    expect(samsung.length).toBeGreaterThanOrEqual(1);
    const hynix = screen.getAllByText("SK하이닉스");
    expect(hynix.length).toBeGreaterThanOrEqual(1);
  });

  it("shows VIX value in header", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      const vixElements = screen.getAllByText(/VIX/);
      expect(vixElements.length).toBeGreaterThanOrEqual(1);
    });
  });

  // ─── NEW: US Stock Rankings ─────────────────────────────────

  it("shows US stock gainers section", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("미국 상승 주도주")).toBeInTheDocument();
    });

    expect(screen.getByText("NVIDIA")).toBeInTheDocument();
    expect(screen.getByText("NVDA")).toBeInTheDocument();
  });

  it("shows US stock losers section", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("미국 하락 주도주")).toBeInTheDocument();
    });

    expect(screen.getByText("Tesla")).toBeInTheDocument();
  });

  it("shows US sector ETF performance", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("미국 섹터 성과")).toBeInTheDocument();
    });

    expect(screen.getByText("반도체")).toBeInTheDocument();
    expect(screen.getByText("SOXX")).toBeInTheDocument();
  });

  // ─── NEW: Korean Watchlist ──────────────────────────────────

  it("shows Korean watchlist section", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("오늘의 관심종목")).toBeInTheDocument();
    });

    expect(screen.getByText("005930")).toBeInTheDocument();
    expect(screen.getByText("000660")).toBeInTheDocument();
  });

  it("shows watchlist items with role badges", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      const badges = screen.getAllByText("대장주");
      expect(badges.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows US drivers in watchlist", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      const driverEls = screen.getAllByText(/NVIDIA \+4\.0%/);
      expect(driverEls.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows AI watchlist recommendations", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("AI 추천 관심종목")).toBeInTheDocument();
    });
  });

  // ─── NEW: US Market Analysis ────────────────────────────────

  it("shows US market analysis section", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("미국 시장 분석")).toBeInTheDocument();
    });

    expect(screen.getByText(/NVDA \+4\.01%/)).toBeInTheDocument();
  });

  // ─── NEW: Theme US Movers ───────────────────────────────────

  it("shows US movers in theme cards", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      // Theme card and watchlist both show NVIDIA as a US mover
      const moverEls = screen.getAllByText(/NVIDIA \+4\.0%/);
      expect(moverEls.length).toBeGreaterThanOrEqual(2);
    });
  });

  // ─── Existing tests ─────────────────────────────────────────

  it("shows generate button when no report exists", async () => {
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/market/daily-report" || url.startsWith("/market/daily-report?")) {
        return Promise.reject({ response: { status: 404 } });
      }
      if (url.startsWith("/market/daily-reports")) {
        return Promise.resolve({ data: [] });
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
      if (url === "/market/daily-report" || url.startsWith("/market/daily-report?")) {
        return Promise.resolve({ data: SAMPLE_REPORT });
      }
      if (url.startsWith("/market/daily-reports")) {
        return Promise.resolve({ data: [] });
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
      const dateEls = screen.getAllByText("2026-02-15");
      expect(dateEls.length).toBeGreaterThanOrEqual(1);
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

  // ─── Closing Report Tab ────────────────────────────────────

  it("shows closing report tab button", async () => {
    render(<MarketPage />);

    expect(screen.getByText(/장마감 리포트/)).toBeInTheDocument();
  });

  it("switches to closing report tab and shows generate button", async () => {
    const user = userEvent.setup();

    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/market/daily-report" || (url.startsWith("/market/daily-report?") && !url.includes("report_type=closing"))) {
        return Promise.resolve({ data: SAMPLE_REPORT });
      }
      if (url.startsWith("/market/daily-reports")) {
        return Promise.resolve({ data: [] });
      }
      if (url.includes("report_type=closing")) {
        return Promise.reject({ response: { status: 404 } });
      }
      return Promise.reject(new Error("Unknown"));
    });

    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText(/장마감 리포트/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/장마감 리포트/));

    await waitFor(() => {
      expect(screen.getByText("장마감 리포트 생성")).toBeInTheDocument();
    });
  });

  it("shows closing report data when available", async () => {
    const user = userEvent.setup();

    const closingReport = {
      ...SAMPLE_REPORT,
      report_type: "closing",
      market_data: {
        "코스피": { ticker: "^KS11", close: 2680.5, change: 15.3, change_pct: 0.57, volume: 450000000 },
        "코스닥": { ticker: "^KQ11", close: 870.2, change: -5.1, change_pct: -0.58, volume: 320000000 },
        kr_rankings: {
          gainers: [
            { code: "005930", name: "삼성전자", theme: "AI/반도체", close: 75000, change: 1500, change_pct: 2.04, volume: 12000000 },
          ],
          losers: [
            { code: "373220", name: "LG에너지솔루션", theme: "2차전지/배터리", close: 350000, change: -8000, change_pct: -2.23, volume: 500000 },
          ],
        },
      },
      ai_summary: {
        headline: "반도체 강세 속 배터리 약세",
        market_sentiment: "중립",
        key_issues: ["삼성전자 외국인 순매수"],
        risks: ["환율 불안"],
        strategy: "반도체 비중 확대",
      },
    };

    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/market/daily-report" || (url.startsWith("/market/daily-report?") && !url.includes("report_type=closing"))) {
        return Promise.resolve({ data: SAMPLE_REPORT });
      }
      if (url.startsWith("/market/daily-reports")) {
        return Promise.resolve({ data: [] });
      }
      if (url.includes("report_type=closing")) {
        return Promise.resolve({ data: closingReport });
      }
      return Promise.reject(new Error("Unknown"));
    });

    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText(/장마감 리포트/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/장마감 리포트/));

    await waitFor(() => {
      expect(screen.getByText("반도체 강세 속 배터리 약세")).toBeInTheDocument();
    });

    expect(screen.getByText("오늘의 상승 주도주")).toBeInTheDocument();
    expect(screen.getByText("오늘의 하락 주도주")).toBeInTheDocument();
  });

  // ─── News Display ──────────────────────────────────────────

  it("shows news section when news data is present", async () => {
    const reportWithNews = {
      ...SAMPLE_REPORT,
      ai_summary: {
        ...SAMPLE_REPORT.ai_summary,
        news: {
          us_news: [
            { title: "NVIDIA beats earnings expectations", summary: "Strong AI demand", source: "Reuters", ticker: "NVDA" },
          ],
          kr_news: [
            { title: "삼성전자 HBM 수출 급증", source: "매일경제 증시" },
          ],
        },
      },
    };

    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/market/daily-report" || url.startsWith("/market/daily-report?")) {
        return Promise.resolve({ data: reportWithNews });
      }
      if (url.startsWith("/market/daily-reports")) {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error("Unknown"));
    });

    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("미국 시장 뉴스")).toBeInTheDocument();
    });

    expect(screen.getByText("NVIDIA beats earnings expectations")).toBeInTheDocument();
    expect(screen.getByText("한국 시장 뉴스")).toBeInTheDocument();
    expect(screen.getByText("삼성전자 HBM 수출 급증")).toBeInTheDocument();
  });

  // ─── Archive Tab ──────────────────────────────────────────

  it("shows archive tab button", async () => {
    render(<MarketPage />);

    expect(screen.getByText(/리포트 보관함/)).toBeInTheDocument();
  });

  it("switches to archive tab and shows report list", async () => {
    const user = userEvent.setup();

    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/market/daily-report" || url.startsWith("/market/daily-report?")) {
        return Promise.resolve({ data: SAMPLE_REPORT });
      }
      if (url.includes("report_type=morning")) {
        return Promise.resolve({ data: [
          { id: "m1", report_date: "2026-02-15", report_type: "morning", headline: "NVDA 급등", market_sentiment: "탐욕", kospi_direction: "상승" },
          { id: "m2", report_date: "2026-02-14", report_type: "morning", headline: "기술주 반등", market_sentiment: "중립", kospi_direction: "보합" },
        ] });
      }
      if (url.includes("report_type=closing")) {
        return Promise.resolve({ data: [
          { id: "c1", report_date: "2026-02-15", report_type: "closing", headline: "반도체 강세 마감", market_sentiment: "탐욕", kospi_direction: "상승" },
        ] });
      }
      if (url.startsWith("/market/daily-reports")) {
        return Promise.resolve({ data: [
          { id: "r1", report_date: "2026-02-15", headline: "NVDA 급등", market_sentiment: "탐욕", kospi_direction: "상승" },
        ] });
      }
      return Promise.reject(new Error("Unknown"));
    });

    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText(/리포트 보관함/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/리포트 보관함/));

    await waitFor(() => {
      expect(screen.getByText("리포트 보관함")).toBeInTheDocument();
      expect(screen.getByText("NVDA 급등")).toBeInTheDocument();
    });

    expect(screen.getByText("반도체 강세 마감")).toBeInTheDocument();
  });

  it("archive tab filter buttons work", async () => {
    const user = userEvent.setup();

    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/market/daily-report" || url.startsWith("/market/daily-report?")) {
        return Promise.resolve({ data: SAMPLE_REPORT });
      }
      if (url.includes("report_type=morning")) {
        return Promise.resolve({ data: [
          { id: "m1", report_date: "2026-02-15", report_type: "morning", headline: "오전 시황 리포트", market_sentiment: "탐욕", kospi_direction: "상승" },
        ] });
      }
      if (url.includes("report_type=closing")) {
        return Promise.resolve({ data: [
          { id: "c1", report_date: "2026-02-15", report_type: "closing", headline: "마감 정리 리포트", market_sentiment: "중립", kospi_direction: "보합" },
        ] });
      }
      if (url.startsWith("/market/daily-reports")) {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error("Unknown"));
    });

    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText(/리포트 보관함/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/리포트 보관함/));

    await waitFor(() => {
      expect(screen.getByText("오전 시황 리포트")).toBeInTheDocument();
      expect(screen.getByText("마감 정리 리포트")).toBeInTheDocument();
    });

    // Both should be visible in "전체" filter (default)
    expect(screen.getByText("2건")).toBeInTheDocument();

    // Click "전체" filter — should show both (already selected, but verifying)
    await user.click(screen.getByText("전체"));
    expect(screen.getByText("오전 시황 리포트")).toBeInTheDocument();
    expect(screen.getByText("마감 정리 리포트")).toBeInTheDocument();
  });

  it("archive tab shows empty state when no reports", async () => {
    const user = userEvent.setup();

    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/market/daily-report" || url.startsWith("/market/daily-report?")) {
        return Promise.resolve({ data: SAMPLE_REPORT });
      }
      if (url.startsWith("/market/daily-reports")) {
        return Promise.resolve({ data: [] });
      }
      return Promise.reject(new Error("Unknown"));
    });

    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText(/리포트 보관함/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/리포트 보관함/));

    await waitFor(() => {
      expect(screen.getByText("저장된 리포트가 없습니다.")).toBeInTheDocument();
    });
  });

  // ─── Report History ────────────────────────────────────────

  it("shows past report date buttons", async () => {
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("과거 리포트:")).toBeInTheDocument();
    });

    expect(screen.getByText("2026-02-14")).toBeInTheDocument();
  });

  it("loads specific date report on click", async () => {
    const user = userEvent.setup();
    render(<MarketPage />);

    await waitFor(() => {
      expect(screen.getByText("2026-02-14")).toBeInTheDocument();
    });

    await user.click(screen.getByText("2026-02-14"));

    await waitFor(() => {
      expect(mockedApi.get).toHaveBeenCalledWith("/market/daily-report?report_date=2026-02-14");
    });
  });
});
