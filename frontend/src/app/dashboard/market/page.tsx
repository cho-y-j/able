"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { useI18n } from "@/i18n";
import { useRealtimePrice } from "@/lib/useRealtimePrice";

interface OHLCVItem {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface MarketItem {
  ticker: string;
  close: number;
  change: number;
  change_pct: number;
  volume: number;
}

interface USStockItem {
  ticker: string;
  name: string;
  close: number;
  change: number;
  change_pct: number;
  volume: number;
}

interface USRankItem {
  ticker: string;
  name: string;
  close: number;
  change_pct: number;
  themes: string[];
}

interface USSectorItem {
  ticker: string;
  name: string;
  kr_name: string;
  close: number;
  change_pct: number;
}

interface WatchlistItem {
  code: string;
  name: string;
  theme: string;
  role: string;
  relevance: number;
  us_drivers: string[];
  reason: string;
}

interface ThemeItem {
  name: string;
  relevance_score: number;
  signals: string[];
  us_movers?: { ticker: string; name: string; change_pct: number }[];
  leader_stocks: { code: string; name: string }[];
  follower_stocks: { code: string; name: string }[];
}

interface NewsItem {
  title: string;
  summary?: string;
  source: string;
  ticker?: string;
  link?: string;
  published?: string;
}

interface KRStockItem {
  code: string;
  name: string;
  theme: string;
  close: number;
  change: number;
  change_pct: number;
  volume: number;
}

interface DailyReport {
  id: string;
  report_date: string;
  report_type?: string;
  status: string;
  market_data: Record<string, MarketItem> & {
    us_stocks?: Record<string, USStockItem>;
    us_sectors?: Record<string, USSectorItem>;
    us_rankings?: { gainers: USRankItem[]; losers: USRankItem[] };
    kr_stocks?: Record<string, KRStockItem>;
    kr_rankings?: { gainers: KRStockItem[]; losers: KRStockItem[] };
  };
  themes: ThemeItem[];
  ai_summary: {
    headline?: string;
    market_sentiment?: string;
    kospi_direction?: string;
    us_market_analysis?: string;
    key_issues?: string[];
    watchlist?: string[];
    watchlist_data?: WatchlistItem[];
    risks?: string[];
    strategy?: string;
    error?: string;
    news?: { us_news?: NewsItem[]; kr_news?: NewsItem[] };
  };
  created_at: string;
}

type TabKey = "briefing" | "closing" | "search";

interface ReportListItem {
  id: string;
  report_date: string;
  headline: string;
  market_sentiment: string;
  kospi_direction: string;
}

export default function MarketPage() {
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState<TabKey>("briefing");
  const [report, setReport] = useState<DailyReport | null>(null);
  const [reportLoading, setReportLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [reportHistory, setReportHistory] = useState<ReportListItem[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  // Closing report state
  const [closingReport, setClosingReport] = useState<DailyReport | null>(null);
  const [closingLoading, setClosingLoading] = useState(false);
  const [closingGenerating, setClosingGenerating] = useState(false);
  const [closingHistory, setClosingHistory] = useState<ReportListItem[]>([]);
  const [closingSelectedDate, setClosingSelectedDate] = useState<string | null>(null);

  // Stock search state (existing functionality)
  const [stockCode, setStockCode] = useState("");
  const [activeCode, setActiveCode] = useState<string | null>(null);
  const [priceData, setPriceData] = useState<Record<string, unknown> | null>(null);
  const [ohlcvData, setOhlcvData] = useState<OHLCVItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [period, setPeriod] = useState("1y");
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<unknown>(null);
  const { tick, isConnected } = useRealtimePrice(activeCode);

  // Load daily report + history on mount
  useEffect(() => {
    loadDailyReport();
    loadReportHistory();
  }, []);

  // Load closing report + history when tab is selected
  useEffect(() => {
    if (activeTab === "closing" && !closingReport && !closingLoading) {
      loadClosingReport();
      loadClosingHistory();
    }
  }, [activeTab]);

  const loadReportHistory = async () => {
    try {
      const res = await api.get("/market/daily-reports?limit=14");
      setReportHistory(res.data || []);
    } catch {
      setReportHistory([]);
    }
  };

  const loadDailyReport = async (date?: string) => {
    setReportLoading(true);
    try {
      const params = date ? `?report_date=${date}` : "";
      const res = await api.get(`/market/daily-report${params}`);
      setReport(res.data);
      if (res.data?.report_date) setSelectedDate(res.data.report_date);
    } catch {
      setReport(null);
    } finally {
      setReportLoading(false);
    }
  };

  const loadClosingHistory = async () => {
    try {
      const res = await api.get("/market/daily-reports?limit=14&report_type=closing");
      setClosingHistory(res.data || []);
    } catch {
      setClosingHistory([]);
    }
  };

  const loadClosingReport = async (date?: string) => {
    setClosingLoading(true);
    try {
      const params = new URLSearchParams({ report_type: "closing" });
      if (date) params.set("report_date", date);
      const res = await api.get(`/market/daily-report?${params}`);
      setClosingReport(res.data);
      if (res.data?.report_date) setClosingSelectedDate(res.data.report_date);
    } catch {
      setClosingReport(null);
    } finally {
      setClosingLoading(false);
    }
  };

  const generateReport = async () => {
    setGenerating(true);
    try {
      await api.post("/market/daily-report/generate?force=true");
      await loadDailyReport();
      await loadReportHistory();
    } catch {
      // Error handled by loading state
    } finally {
      setGenerating(false);
    }
  };

  const generateClosingReport = async () => {
    setClosingGenerating(true);
    try {
      await api.post("/market/closing-report/generate?force=true");
      await loadClosingReport();
      await loadClosingHistory();
    } catch {
      // Error handled by loading state
    } finally {
      setClosingGenerating(false);
    }
  };

  const handleClosingDateSelect = (date: string) => {
    setClosingSelectedDate(date);
    loadClosingReport(date);
  };

  const handleDateSelect = (date: string) => {
    setSelectedDate(date);
    loadDailyReport(date);
  };

  // Real-time price update
  useEffect(() => {
    if (!tick) return;
    setPriceData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        current_price: tick.current_price,
        change: tick.change,
        change_percent: tick.change_percent,
        volume: tick.volume,
        high: tick.high,
        low: tick.low,
      };
    });
  }, [tick]);

  const fetchPrice = async () => {
    if (!stockCode.trim()) return;
    setLoading(true);
    const code = stockCode.trim();
    try {
      const [priceRes, ohlcvRes] = await Promise.all([
        api.get(`/market/price/${code}`),
        api.get(`/market/ohlcv/${code}?period=${period}`),
      ]);
      setPriceData(priceRes.data);
      setOhlcvData(ohlcvRes.data.data || []);
      setActiveCode(code);
    } catch {
      setPriceData(null);
      setOhlcvData([]);
      setActiveCode(null);
    } finally {
      setLoading(false);
    }
  };

  const renderChart = useCallback(async () => {
    if (!chartContainerRef.current || ohlcvData.length === 0) return;
    try {
      const { createChart, CandlestickSeries, HistogramSeries } = await import("lightweight-charts");
      chartContainerRef.current.innerHTML = "";
      const chart = createChart(chartContainerRef.current, {
        width: chartContainerRef.current.clientWidth,
        height: 400,
        layout: { background: { color: "#111827" }, textColor: "#9CA3AF" },
        grid: { vertLines: { color: "#1F2937" }, horzLines: { color: "#1F2937" } },
        crosshair: { mode: 0 },
        timeScale: { borderColor: "#374151" },
      });
      const candlestickSeries = chart.addSeries(CandlestickSeries, {
        upColor: "#10B981", downColor: "#EF4444",
        borderDownColor: "#EF4444", borderUpColor: "#10B981",
        wickDownColor: "#EF4444", wickUpColor: "#10B981",
      });
      const volumeSeries = chart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" }, priceScaleId: "volume",
      });
      chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
      const candleData = ohlcvData.map((d) => ({
        time: d.date.replace(/(\d{4})(\d{2})(\d{2})/, "$1-$2-$3"),
        open: d.open, high: d.high, low: d.low, close: d.close,
      }));
      const volumeData = ohlcvData.map((d) => ({
        time: d.date.replace(/(\d{4})(\d{2})(\d{2})/, "$1-$2-$3"),
        value: d.volume,
        color: d.close >= d.open ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)",
      }));
      candlestickSeries.setData(candleData as Parameters<typeof candlestickSeries.setData>[0]);
      volumeSeries.setData(volumeData as Parameters<typeof volumeSeries.setData>[0]);
      chart.timeScale().fitContent();
      chartRef.current = chart;
      const handleResize = () => {
        if (chartContainerRef.current) chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      };
      window.addEventListener("resize", handleResize);
      return () => window.removeEventListener("resize", handleResize);
    } catch { /* lightweight-charts not available */ }
  }, [ohlcvData]);

  useEffect(() => { renderChart(); }, [renderChart]);

  const tabs: { key: TabKey; label: string; icon: string }[] = [
    { key: "briefing", label: "데일리 브리핑", icon: "📊" },
    { key: "closing", label: "장마감 리포트", icon: "📋" },
    { key: "search", label: "종목 검색", icon: "🔍" },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">{t.market.title}</h2>
        <div className="flex gap-1 bg-gray-900 rounded-lg p-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 text-sm rounded-md transition-colors ${
                activeTab === tab.key
                  ? "bg-blue-600 text-white"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              {tab.icon} {tab.label}
            </button>
          ))}
        </div>
      </div>

      {activeTab === "briefing" ? (
        <DailyBriefingTab
          report={report}
          loading={reportLoading}
          generating={generating}
          onGenerate={generateReport}
          onRefresh={() => loadDailyReport(selectedDate || undefined)}
          reportHistory={reportHistory}
          selectedDate={selectedDate}
          onDateSelect={handleDateSelect}
        />
      ) : activeTab === "closing" ? (
        <ClosingReportTab
          report={closingReport}
          loading={closingLoading}
          generating={closingGenerating}
          onGenerate={generateClosingReport}
          onRefresh={() => loadClosingReport(closingSelectedDate || undefined)}
          reportHistory={closingHistory}
          selectedDate={closingSelectedDate}
          onDateSelect={handleClosingDateSelect}
        />
      ) : (
        <StockSearchTab
          stockCode={stockCode}
          setStockCode={setStockCode}
          period={period}
          setPeriod={setPeriod}
          loading={loading}
          fetchPrice={fetchPrice}
          priceData={priceData}
          isConnected={isConnected}
          ohlcvData={ohlcvData}
          chartContainerRef={chartContainerRef}
          t={t}
        />
      )}
    </div>
  );
}

/* ─── Daily Briefing Tab ──────────────────────────────────────── */

function DailyBriefingTab({
  report,
  loading,
  generating,
  onGenerate,
  onRefresh,
  reportHistory,
  selectedDate,
  onDateSelect,
}: {
  report: DailyReport | null;
  loading: boolean;
  generating: boolean;
  onGenerate: () => void;
  onRefresh: () => void;
  reportHistory: ReportListItem[];
  selectedDate: string | null;
  onDateSelect: (date: string) => void;
}) {
  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-gray-900 rounded-xl border border-gray-800 p-6 animate-pulse">
            <div className="h-6 bg-gray-800 rounded w-1/3 mb-4" />
            <div className="h-4 bg-gray-800 rounded w-2/3 mb-2" />
            <div className="h-4 bg-gray-800 rounded w-1/2" />
          </div>
        ))}
      </div>
    );
  }

  if (!report) {
    return (
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-12 text-center">
        <div className="text-6xl mb-4">📈</div>
        <h3 className="text-xl font-semibold mb-2">데일리 마켓 인텔리전스</h3>
        <p className="text-gray-400 mb-6">
          매일 아침 6:30에 자동 생성됩니다. 지금 바로 생성할 수도 있습니다.
        </p>
        <button
          onClick={onGenerate}
          disabled={generating}
          className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 rounded-lg text-sm font-medium transition-colors"
        >
          {generating ? "생성 중... (1~2분 소요)" : "지금 리포트 생성"}
        </button>
      </div>
    );
  }

  const ai = report.ai_summary || {};
  const md = report.market_data || {};
  const themes = report.themes || [];
  const usRankings = md.us_rankings;
  const usSectors = md.us_sectors;
  const watchlistData = ai.watchlist_data || [];

  const sentimentColor =
    ai.market_sentiment === "탐욕" ? "text-green-400 bg-green-400/10" :
    ai.market_sentiment === "공포" ? "text-red-400 bg-red-400/10" :
    "text-yellow-400 bg-yellow-400/10";

  const directionColor =
    ai.kospi_direction === "상승" ? "text-green-400" :
    ai.kospi_direction === "하락" ? "text-red-400" :
    "text-yellow-400";

  const directionIcon =
    ai.kospi_direction === "상승" ? "▲" :
    ai.kospi_direction === "하락" ? "▼" : "━";

  return (
    <div className="space-y-6">
      {/* Report History Selector */}
      {reportHistory.length > 1 && (
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          <span className="text-xs text-gray-500 flex-shrink-0">과거 리포트:</span>
          {reportHistory.map((r) => (
            <button
              key={r.id}
              onClick={() => onDateSelect(r.report_date)}
              className={`flex-shrink-0 text-xs px-3 py-1.5 rounded-lg transition-colors ${
                selectedDate === r.report_date
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700"
              }`}
            >
              <span>{r.report_date}</span>
              {r.headline && (
                <span className="ml-1.5 text-gray-500 max-w-[120px] truncate inline-block align-middle">
                  {r.headline}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Hero: AI Headline */}
      <div className="bg-gradient-to-r from-blue-900/40 to-purple-900/40 rounded-xl border border-blue-800/50 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-xs bg-blue-600/30 text-blue-300 px-2 py-1 rounded">
              {report.report_date}
            </span>
            <span className={`text-xs px-2 py-1 rounded ${sentimentColor}`}>
              시장 심리: {ai.market_sentiment || "중립"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onRefresh} className="text-xs text-gray-400 hover:text-white transition-colors">
              새로고침
            </button>
            <button
              onClick={onGenerate}
              disabled={generating}
              className="text-xs bg-gray-800 hover:bg-gray-700 px-3 py-1 rounded transition-colors"
            >
              {generating ? "생성 중..." : "재생성"}
            </button>
          </div>
        </div>
        <h3 className="text-2xl font-bold mb-3">{ai.headline || "데일리 브리핑"}</h3>
        <div className="flex items-center gap-6 text-sm">
          <span className={`font-semibold ${directionColor}`}>
            코스피 전망: {directionIcon} {ai.kospi_direction || "보합"}
          </span>
          {md["VIX"] && (
            <span className={`${(md["VIX"] as MarketItem).close > 25 ? "text-red-400" : (md["VIX"] as MarketItem).close > 18 ? "text-yellow-400" : "text-green-400"}`}>
              VIX: {(md["VIX"] as MarketItem).close?.toFixed(1)} ({(md["VIX"] as MarketItem).change_pct > 0 ? "+" : ""}{(md["VIX"] as MarketItem).change_pct?.toFixed(1)}%)
            </span>
          )}
          {md["USD/KRW"] && (
            <span className="text-gray-300">
              원/달러: {(md["USD/KRW"] as MarketItem).close?.toLocaleString(undefined, { maximumFractionDigits: 1 })}
            </span>
          )}
        </div>
      </div>

      {/* Korean Watchlist — TOP PRIORITY */}
      {watchlistData.length > 0 && (
        <div className="bg-gradient-to-r from-green-900/30 to-emerald-900/30 rounded-xl border border-green-800/50 p-6">
          <h4 className="text-sm font-semibold text-green-400 mb-4">오늘의 관심종목</h4>
          <div className="space-y-3">
            {watchlistData.map((item, i) => (
              <div key={item.code} className="flex items-start gap-3 bg-gray-900/50 rounded-lg p-3">
                <span className="text-lg font-bold text-green-400 min-w-[28px]">{i + 1}</span>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-semibold text-white">{item.name}</span>
                    <span className="text-xs text-gray-500">{item.code}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      item.role === "대장주" ? "bg-blue-500/20 text-blue-300" : "bg-gray-700 text-gray-400"
                    }`}>
                      {item.role}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400">{item.reason}</p>
                  {item.us_drivers && item.us_drivers.length > 0 && (
                    <div className="flex gap-1.5 mt-1.5">
                      {item.us_drivers.map((driver, j) => (
                        <span key={j} className="text-xs bg-gray-800 text-gray-300 px-1.5 py-0.5 rounded">
                          {driver}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <span className="text-xs text-purple-300 bg-purple-500/20 px-2 py-0.5 rounded whitespace-nowrap">
                  {item.theme}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI Watchlist (from DeepSeek) */}
      {(ai.watchlist?.length ?? 0) > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h4 className="text-sm font-semibold text-green-400 mb-3">AI 추천 관심종목</h4>
          <ul className="space-y-2">
            {ai.watchlist!.map((item, i) => (
              <li key={i} className="flex gap-2 text-sm text-gray-300">
                <span className="text-green-500 flex-shrink-0 font-bold">{i + 1}.</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* US Market Analysis */}
      {ai.us_market_analysis && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h4 className="text-sm font-semibold text-blue-400 mb-3">미국 시장 분석</h4>
          <div className="text-sm text-gray-300 leading-relaxed whitespace-pre-line">
            {ai.us_market_analysis}
          </div>
        </div>
      )}

      {/* US Stock Rankings: Gainers + Losers */}
      {usRankings && ((usRankings.gainers?.length ?? 0) > 0 || (usRankings.losers?.length ?? 0) > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Gainers */}
          {(usRankings.gainers?.length ?? 0) > 0 && (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
              <h4 className="text-sm font-semibold text-green-400 mb-4">미국 상승 주도주</h4>
              <div className="space-y-2">
                {usRankings.gainers.map((stock, i) => (
                  <div key={stock.ticker} className="flex items-center justify-between py-1.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 w-5">{i + 1}</span>
                      <span className="text-xs font-medium text-white">{stock.name}</span>
                      <span className="text-xs text-gray-500">{stock.ticker}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-gray-400">${stock.close?.toLocaleString()}</span>
                      <span className="text-xs font-medium text-green-400 min-w-[60px] text-right">
                        +{stock.change_pct?.toFixed(2)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Losers */}
          {(usRankings.losers?.length ?? 0) > 0 && (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
              <h4 className="text-sm font-semibold text-red-400 mb-4">미국 하락 주도주</h4>
              <div className="space-y-2">
                {usRankings.losers.map((stock, i) => (
                  <div key={stock.ticker} className="flex items-center justify-between py-1.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 w-5">{i + 1}</span>
                      <span className="text-xs font-medium text-white">{stock.name}</span>
                      <span className="text-xs text-gray-500">{stock.ticker}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-gray-400">${stock.close?.toLocaleString()}</span>
                      <span className="text-xs font-medium text-red-400 min-w-[60px] text-right">
                        {stock.change_pct?.toFixed(2)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* US Sector ETF Performance */}
      {usSectors && Object.keys(usSectors).length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h4 className="text-sm font-semibold text-gray-400 mb-4">미국 섹터 성과</h4>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
            {Object.entries(usSectors)
              .sort(([, a], [, b]) => (b.change_pct ?? 0) - (a.change_pct ?? 0))
              .map(([ticker, sec]) => {
                const isPositive = sec.change_pct >= 0;
                return (
                  <div key={ticker} className={`rounded-lg p-3 ${isPositive ? "bg-green-900/20 border border-green-800/30" : "bg-red-900/20 border border-red-800/30"}`}>
                    <p className="text-xs text-gray-400">{sec.kr_name}</p>
                    <p className="text-xs text-gray-500">{ticker}</p>
                    <p className={`text-sm font-semibold mt-1 ${isPositive ? "text-green-400" : "text-red-400"}`}>
                      {isPositive ? "+" : ""}{sec.change_pct?.toFixed(2)}%
                    </p>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* AI Strategy */}
      {ai.strategy && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h4 className="text-sm font-semibold text-blue-400 mb-3">오늘의 투자 전략</h4>
          <p className="text-gray-200 leading-relaxed">{ai.strategy}</p>
        </div>
      )}

      {/* Key Issues + Risks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {(ai.key_issues?.length ?? 0) > 0 && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h4 className="text-sm font-semibold text-yellow-400 mb-3">핵심 이슈</h4>
            <ul className="space-y-2">
              {ai.key_issues!.map((issue, i) => (
                <li key={i} className="flex gap-2 text-sm text-gray-300">
                  <span className="text-yellow-500 flex-shrink-0">{i + 1}.</span>
                  {issue}
                </li>
              ))}
            </ul>
          </div>
        )}
        {(ai.risks?.length ?? 0) > 0 && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h4 className="text-sm font-semibold text-red-400 mb-3">리스크 요인</h4>
            <ul className="space-y-2">
              {ai.risks!.map((risk, i) => (
                <li key={i} className="flex gap-2 text-sm text-gray-300">
                  <span className="text-red-500 flex-shrink-0">!</span>
                  {risk}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Global Markets Grid */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <h4 className="text-sm font-semibold text-gray-400 mb-4">글로벌 마켓</h4>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {[
            "S&P 500", "나스닥", "다우존스",
            "코스피", "코스닥",
            "닛케이225", "항셍",
            "DAX", "FTSE100",
          ].map((name) => {
            const d = md[name] as MarketItem | undefined;
            if (!d || typeof d !== "object" || !("close" in d)) return null;
            return <MarketCard key={name} name={name} data={d} />;
          })}
        </div>
      </div>

      {/* Commodities & FX & Bonds */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h4 className="text-sm font-semibold text-gray-400 mb-4">원자재</h4>
          <div className="space-y-2">
            {["WTI 원유", "브렌트유", "금", "은", "구리", "천연가스"].map((name) => {
              const d = md[name] as MarketItem | undefined;
              if (!d || typeof d !== "object" || !("close" in d)) return null;
              return <MarketRow key={name} name={name} data={d} prefix="$" />;
            })}
          </div>
        </div>
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h4 className="text-sm font-semibold text-gray-400 mb-4">환율</h4>
          <div className="space-y-2">
            {["USD/KRW", "달러인덱스", "EUR/USD", "USD/JPY"].map((name) => {
              const d = md[name] as MarketItem | undefined;
              if (!d || typeof d !== "object" || !("close" in d)) return null;
              return <MarketRow key={name} name={name} data={d} />;
            })}
          </div>
        </div>
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h4 className="text-sm font-semibold text-gray-400 mb-4">금리 & 선물</h4>
          <div className="space-y-2">
            {["미국2Y금리", "미국10Y금리", "미국30Y금리", "S&P500선물", "나스닥선물", "VIX"].map((name) => {
              const d = md[name] as MarketItem | undefined;
              if (!d || typeof d !== "object" || !("close" in d)) return null;
              return <MarketRow key={name} name={name} data={d} />;
            })}
          </div>
        </div>
      </div>

      {/* Active Themes */}
      {themes.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h4 className="text-sm font-semibold text-purple-400 mb-4">
            주목 테마 & 대장주
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {themes.map((theme, i) => (
              <ThemeCard key={i} theme={theme} />
            ))}
          </div>
        </div>
      )}

      {/* News Section */}
      <NewsSection news={ai.news} />
    </div>
  );
}

function MarketCard({ name, data }: { name: string; data: MarketItem }) {
  const isPositive = data.change_pct >= 0;
  return (
    <div className="bg-gray-800/50 rounded-lg p-3">
      <p className="text-xs text-gray-500 truncate">{name}</p>
      <p className="text-sm font-semibold mt-1">{data.close?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</p>
      <p className={`text-xs font-medium ${isPositive ? "text-green-400" : "text-red-400"}`}>
        {isPositive ? "+" : ""}{data.change_pct?.toFixed(2)}%
      </p>
    </div>
  );
}

function MarketRow({ name, data, prefix }: { name: string; data: MarketItem; prefix?: string }) {
  const isPositive = data.change_pct >= 0;
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-xs text-gray-400">{name}</span>
      <div className="flex items-center gap-3">
        <span className="text-xs font-medium">
          {prefix || ""}{data.close?.toLocaleString(undefined, { maximumFractionDigits: 3 })}
        </span>
        <span className={`text-xs font-medium min-w-[60px] text-right ${isPositive ? "text-green-400" : "text-red-400"}`}>
          {isPositive ? "+" : ""}{data.change_pct?.toFixed(2)}%
        </span>
      </div>
    </div>
  );
}

function ThemeCard({ theme }: { theme: ThemeItem }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-gray-800/50 rounded-lg p-4">
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-white">{theme.name}</span>
          <span className="text-xs bg-purple-500/20 text-purple-300 px-1.5 py-0.5 rounded">
            관련도 {theme.relevance_score}
          </span>
        </div>
        <span className="text-gray-500 text-xs">{expanded ? "▲" : "▼"}</span>
      </div>

      {/* US Movers that triggered this theme */}
      {theme.us_movers && theme.us_movers.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {theme.us_movers.slice(0, 3).map((m) => (
            <span
              key={m.ticker}
              className={`text-xs px-1.5 py-0.5 rounded ${
                m.change_pct >= 0
                  ? "bg-green-500/20 text-green-300"
                  : "bg-red-500/20 text-red-300"
              }`}
            >
              {m.name} {m.change_pct >= 0 ? "+" : ""}{m.change_pct.toFixed(1)}%
            </span>
          ))}
        </div>
      )}

      {/* Signals */}
      <div className="mt-2 space-y-1">
        {theme.signals.slice(0, 2).map((sig, i) => (
          <p key={i} className="text-xs text-gray-400">• {sig}</p>
        ))}
      </div>

      {/* Leader Stocks */}
      <div className="mt-3 flex flex-wrap gap-1.5">
        {theme.leader_stocks.map((stock) => (
          <span key={stock.code} className="text-xs bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded">
            {stock.name}
          </span>
        ))}
      </div>

      {/* Expanded: Follower Stocks + More Signals */}
      {expanded && (
        <>
          {theme.follower_stocks.length > 0 && (
            <div className="mt-2">
              <p className="text-xs text-gray-500 mb-1">수혜주:</p>
              <div className="flex flex-wrap gap-1.5">
                {theme.follower_stocks.map((stock) => (
                  <span key={stock.code} className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">
                    {stock.name} ({stock.code})
                  </span>
                ))}
              </div>
            </div>
          )}
          {theme.signals.length > 2 && (
            <div className="mt-2 space-y-1">
              {theme.signals.slice(2).map((sig, i) => (
                <p key={i} className="text-xs text-gray-400">• {sig}</p>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ─── News Section (shared) ─────────────────────────────────── */

function NewsSection({ news }: { news?: { us_news?: NewsItem[]; kr_news?: NewsItem[] } }) {
  if (!news) return null;
  const usNews = news.us_news || [];
  const krNews = news.kr_news || [];
  if (usNews.length === 0 && krNews.length === 0) return null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {usNews.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h4 className="text-sm font-semibold text-blue-400 mb-4">미국 시장 뉴스</h4>
          <div className="space-y-3">
            {usNews.slice(0, 8).map((n, i) => (
              <div key={i} className="border-b border-gray-800 pb-2 last:border-0 last:pb-0">
                <div className="flex items-start gap-2">
                  {n.ticker && (
                    <span className="text-xs bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded flex-shrink-0">
                      {n.ticker}
                    </span>
                  )}
                  <p className="text-sm text-gray-200 leading-snug">{n.title}</p>
                </div>
                {n.summary && (
                  <p className="text-xs text-gray-500 mt-1 line-clamp-2">{n.summary}</p>
                )}
                <p className="text-xs text-gray-600 mt-1">{n.source}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {krNews.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h4 className="text-sm font-semibold text-orange-400 mb-4">한국 시장 뉴스</h4>
          <div className="space-y-3">
            {krNews.slice(0, 8).map((n, i) => (
              <div key={i} className="border-b border-gray-800 pb-2 last:border-0 last:pb-0">
                <p className="text-sm text-gray-200 leading-snug">{n.title}</p>
                <p className="text-xs text-gray-600 mt-1">{n.source}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Closing Report Tab (장마감 리포트) ───────────────────────── */

function ClosingReportTab({
  report,
  loading,
  generating,
  onGenerate,
  onRefresh,
  reportHistory,
  selectedDate,
  onDateSelect,
}: {
  report: DailyReport | null;
  loading: boolean;
  generating: boolean;
  onGenerate: () => void;
  onRefresh: () => void;
  reportHistory: ReportListItem[];
  selectedDate: string | null;
  onDateSelect: (date: string) => void;
}) {
  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-gray-900 rounded-xl border border-gray-800 p-6 animate-pulse">
            <div className="h-6 bg-gray-800 rounded w-1/3 mb-4" />
            <div className="h-4 bg-gray-800 rounded w-2/3 mb-2" />
            <div className="h-4 bg-gray-800 rounded w-1/2" />
          </div>
        ))}
      </div>
    );
  }

  if (!report) {
    return (
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-12 text-center">
        <div className="text-6xl mb-4">📋</div>
        <h3 className="text-xl font-semibold mb-2">장마감 리포트</h3>
        <p className="text-gray-400 mb-6">
          장 마감 후(16:00) 자동 생성됩니다. 지금 바로 생성할 수도 있습니다.
        </p>
        <button
          onClick={onGenerate}
          disabled={generating}
          className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 rounded-lg text-sm font-medium transition-colors"
        >
          {generating ? "생성 중... (1~2분 소요)" : "장마감 리포트 생성"}
        </button>
      </div>
    );
  }

  const ai = report.ai_summary || {};
  const md = report.market_data || {};
  const krRankings = md.kr_rankings;
  const krStocks = md.kr_stocks || {};

  const sentimentColor =
    ai.market_sentiment === "탐욕" ? "text-green-400 bg-green-400/10" :
    ai.market_sentiment === "공포" ? "text-red-400 bg-red-400/10" :
    "text-yellow-400 bg-yellow-400/10";

  return (
    <div className="space-y-6">
      {/* Report History Selector */}
      {reportHistory.length > 1 && (
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          <span className="text-xs text-gray-500 flex-shrink-0">과거 장마감:</span>
          {reportHistory.map((r) => (
            <button
              key={r.id}
              onClick={() => onDateSelect(r.report_date)}
              className={`flex-shrink-0 text-xs px-3 py-1.5 rounded-lg transition-colors ${
                selectedDate === r.report_date
                  ? "bg-orange-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700"
              }`}
            >
              <span>{r.report_date}</span>
              {r.headline && (
                <span className="ml-1.5 text-gray-500 max-w-[120px] truncate inline-block align-middle">
                  {r.headline}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Hero: AI Headline */}
      <div className="bg-gradient-to-r from-orange-900/40 to-red-900/40 rounded-xl border border-orange-800/50 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-xs bg-orange-600/30 text-orange-300 px-2 py-1 rounded">
              {report.report_date} 장마감
            </span>
            <span className={`text-xs px-2 py-1 rounded ${sentimentColor}`}>
              시장 심리: {ai.market_sentiment || "중립"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onRefresh} className="text-xs text-gray-400 hover:text-white transition-colors">
              새로고침
            </button>
            <button
              onClick={onGenerate}
              disabled={generating}
              className="text-xs bg-gray-800 hover:bg-gray-700 px-3 py-1 rounded transition-colors"
            >
              {generating ? "생성 중..." : "재생성"}
            </button>
          </div>
        </div>
        <h3 className="text-2xl font-bold mb-3">{ai.headline || "장마감 리포트"}</h3>
        <div className="flex items-center gap-6 text-sm">
          {md["코스피"] && (
            <span className={`font-semibold ${(md["코스피"] as MarketItem).change_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
              코스피: {(md["코스피"] as MarketItem).close?.toLocaleString(undefined, { maximumFractionDigits: 2 })} ({(md["코스피"] as MarketItem).change_pct >= 0 ? "+" : ""}{(md["코스피"] as MarketItem).change_pct?.toFixed(2)}%)
            </span>
          )}
          {md["코스닥"] && (
            <span className={`font-semibold ${(md["코스닥"] as MarketItem).change_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
              코스닥: {(md["코스닥"] as MarketItem).close?.toLocaleString(undefined, { maximumFractionDigits: 2 })} ({(md["코스닥"] as MarketItem).change_pct >= 0 ? "+" : ""}{(md["코스닥"] as MarketItem).change_pct?.toFixed(2)}%)
            </span>
          )}
        </div>
      </div>

      {/* Korean Stock Rankings: Gainers + Losers */}
      {krRankings && ((krRankings.gainers?.length ?? 0) > 0 || (krRankings.losers?.length ?? 0) > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {(krRankings.gainers?.length ?? 0) > 0 && (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
              <h4 className="text-sm font-semibold text-green-400 mb-4">오늘의 상승 주도주</h4>
              <div className="space-y-2">
                {krRankings.gainers.map((stock: KRStockItem, i: number) => (
                  <div key={stock.code} className="flex items-center justify-between py-1.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 w-5">{i + 1}</span>
                      <span className="text-xs font-medium text-white">{stock.name}</span>
                      <span className="text-xs text-gray-500">{stock.code}</span>
                      <span className="text-xs text-purple-300">{stock.theme}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-gray-400">{stock.close?.toLocaleString()}원</span>
                      <span className="text-xs font-medium text-green-400 min-w-[60px] text-right">
                        +{stock.change_pct?.toFixed(2)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {(krRankings.losers?.length ?? 0) > 0 && (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
              <h4 className="text-sm font-semibold text-red-400 mb-4">오늘의 하락 주도주</h4>
              <div className="space-y-2">
                {krRankings.losers.map((stock: KRStockItem, i: number) => (
                  <div key={stock.code} className="flex items-center justify-between py-1.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 w-5">{i + 1}</span>
                      <span className="text-xs font-medium text-white">{stock.name}</span>
                      <span className="text-xs text-gray-500">{stock.code}</span>
                      <span className="text-xs text-purple-300">{stock.theme}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-gray-400">{stock.close?.toLocaleString()}원</span>
                      <span className="text-xs font-medium text-red-400 min-w-[60px] text-right">
                        {stock.change_pct?.toFixed(2)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* AI Market Analysis */}
      {ai.us_market_analysis && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h4 className="text-sm font-semibold text-blue-400 mb-3">시장 분석</h4>
          <div className="text-sm text-gray-300 leading-relaxed whitespace-pre-line">
            {ai.us_market_analysis}
          </div>
        </div>
      )}

      {/* AI Strategy */}
      {ai.strategy && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h4 className="text-sm font-semibold text-blue-400 mb-3">내일 전망 + 투자 전략</h4>
          <p className="text-gray-200 leading-relaxed">{ai.strategy}</p>
        </div>
      )}

      {/* Key Issues + Risks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {(ai.key_issues?.length ?? 0) > 0 && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h4 className="text-sm font-semibold text-yellow-400 mb-3">핵심 이슈</h4>
            <ul className="space-y-2">
              {ai.key_issues!.map((issue: string, i: number) => (
                <li key={i} className="flex gap-2 text-sm text-gray-300">
                  <span className="text-yellow-500 flex-shrink-0">{i + 1}.</span>
                  {issue}
                </li>
              ))}
            </ul>
          </div>
        )}
        {(ai.risks?.length ?? 0) > 0 && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h4 className="text-sm font-semibold text-red-400 mb-3">리스크 요인</h4>
            <ul className="space-y-2">
              {ai.risks!.map((risk: string, i: number) => (
                <li key={i} className="flex gap-2 text-sm text-gray-300">
                  <span className="text-red-500 flex-shrink-0">!</span>
                  {risk}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* AI Watchlist (notable stocks) */}
      {(ai.watchlist?.length ?? 0) > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h4 className="text-sm font-semibold text-green-400 mb-3">주목 종목</h4>
          <ul className="space-y-2">
            {ai.watchlist!.map((item: string, i: number) => (
              <li key={i} className="flex gap-2 text-sm text-gray-300">
                <span className="text-green-500 flex-shrink-0 font-bold">{i + 1}.</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* News Section */}
      <NewsSection news={ai.news} />
    </div>
  );
}

/* ─── Stock Search Tab (existing functionality) ───────────────── */

function StockSearchTab({
  stockCode, setStockCode, period, setPeriod, loading, fetchPrice,
  priceData, isConnected, ohlcvData, chartContainerRef, t,
}: {
  stockCode: string;
  setStockCode: (v: string) => void;
  period: string;
  setPeriod: (v: string) => void;
  loading: boolean;
  fetchPrice: () => void;
  priceData: Record<string, unknown> | null;
  isConnected: boolean;
  ohlcvData: OHLCVItem[];
  chartContainerRef: React.RefObject<HTMLDivElement | null>;
  t: ReturnType<typeof useI18n>["t"];
}) {
  return (
    <>
      {/* Stock Search */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <h3 className="text-lg font-semibold mb-4">Stock Lookup</h3>
        <div className="flex gap-3">
          <input
            type="text"
            value={stockCode}
            onChange={(e) => setStockCode(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && fetchPrice()}
            placeholder={t.market.searchPlaceholder}
            className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
          />
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="px-3 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm"
          >
            <option value="1m">1M</option>
            <option value="3m">3M</option>
            <option value="6m">6M</option>
            <option value="1y">1Y</option>
            <option value="2y">2Y</option>
          </select>
          <button onClick={fetchPrice} disabled={loading}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 rounded-lg text-sm font-medium transition-colors">
            {loading ? t.common.loading : t.market.searchBtn}
          </button>
        </div>
      </div>

      {/* Price Display */}
      {priceData && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <h3 className="text-lg font-semibold">{String(priceData.stock_code)}</h3>
              {isConnected && (
                <span className="flex items-center gap-1 text-xs text-green-400">
                  <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                  {t.market.live}
                </span>
              )}
            </div>
            <span className={`text-2xl font-bold ${Number(priceData.change) >= 0 ? "text-green-400" : "text-red-400"}`}>
              ₩{Number(priceData.current_price).toLocaleString()}
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <PriceItem label={t.market.change} value={String(priceData.change)} color={Number(priceData.change) >= 0} />
            <PriceItem label={`${t.market.change} %`} value={`${priceData.change_percent}%`} color={Number(priceData.change_percent) >= 0} />
            <PriceItem label={t.market.volume} value={Number(priceData.volume).toLocaleString()} />
            <PriceItem label={t.market.high} value={Number(priceData.high || 0).toLocaleString()} />
            <PriceItem label={t.market.low} value={Number(priceData.low || 0).toLocaleString()} />
          </div>
          {typeof priceData.message === "string" && (
            <p className="text-sm text-yellow-400 mt-4">{priceData.message}</p>
          )}
        </div>
      )}

      {/* Chart */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <h3 className="text-lg font-semibold mb-4">
          {t.market.priceChart} {ohlcvData.length > 0 && `(${ohlcvData.length} candles)`}
        </h3>
        <div ref={chartContainerRef} className="w-full" style={{ minHeight: 400 }}>
          {ohlcvData.length === 0 && (
            <div className="h-96 flex items-center justify-center border border-gray-800 rounded-lg">
              <p className="text-gray-600">종목을 검색하세요.</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function PriceItem({ label, value, color }: { label: string; value: string; color?: boolean }) {
  const colorClass = color === undefined ? "" : color ? "text-green-400" : "text-red-400";
  return (
    <div className="bg-gray-800 rounded-lg p-3">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-lg font-semibold mt-1 ${colorClass}`}>{value}</p>
    </div>
  );
}
