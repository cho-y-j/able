"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";
import { useI18n } from "@/i18n";
import AiAnalysisTab from "@/app/dashboard/strategies/[id]/_components/AiAnalysisTab";

interface DailyReport {
  id: string;
  report_date: string;
  report_type: string;
  status: string;
  ai_summary: {
    headline?: string;
    market_sentiment?: string;
    kospi_direction?: string;
    us_market_analysis?: string;
    key_issues?: string[];
    watchlist?: { code?: string; name?: string; reason?: string }[];
    risks?: string[];
    strategy?: string;
  } | null;
  themes: { name: string; relevance_score: number; signals: string[] }[] | null;
  created_at: string | null;
}

const SENTIMENT_STYLES: Record<string, string> = {
  "탐욕": "bg-green-900/50 text-green-400",
  "중립": "bg-gray-700 text-gray-300",
  "공포": "bg-red-900/50 text-red-400",
  greed: "bg-green-900/50 text-green-400",
  neutral: "bg-gray-700 text-gray-300",
  fear: "bg-red-900/50 text-red-400",
};

const DIRECTION_STYLES: Record<string, string> = {
  "상승": "bg-green-900/50 text-green-400",
  "보합": "bg-gray-700 text-gray-300",
  "하락": "bg-red-900/50 text-red-400",
  up: "bg-green-900/50 text-green-400",
  flat: "bg-gray-700 text-gray-300",
  down: "bg-red-900/50 text-red-400",
};

export default function AnalysisPage() {
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState<"stock" | "briefing">("stock");

  // Stock analysis state
  const [stockCode, setStockCode] = useState("");
  const [activeStock, setActiveStock] = useState<string | null>(null);

  // Briefing state
  const [briefingType, setBriefingType] = useState<"morning" | "closing">("morning");
  const [report, setReport] = useState<DailyReport | null>(null);
  const [briefingLoading, setBriefingLoading] = useState(false);

  const handleAnalyze = () => {
    const code = stockCode.trim();
    if (!code) return;
    setActiveStock(code);
  };

  useEffect(() => {
    if (activeTab === "briefing") fetchBriefing();
  }, [activeTab, briefingType]);

  const fetchBriefing = async () => {
    setBriefingLoading(true);
    try {
      const { data } = await api.get("/market/daily-report", {
        params: { report_type: briefingType },
      });
      setReport(data);
    } catch {
      setReport(null);
    } finally {
      setBriefingLoading(false);
    }
  };

  const summary = report?.ai_summary;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">{t.analysis.title}</h2>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {(["stock", "briefing"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab
                ? "bg-purple-600 text-white"
                : "bg-gray-800 text-gray-400 hover:text-white"
            }`}
          >
            {tab === "stock" ? t.analysis.stockAnalysis : t.analysis.marketBriefing}
          </button>
        ))}
      </div>

      {/* Stock Analysis Tab */}
      {activeTab === "stock" && (
        <div>
          {/* Stock code input */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
            <div className="flex gap-3">
              <input
                type="text"
                value={stockCode}
                onChange={(e) => setStockCode(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
                placeholder={t.analysis.enterStockCode}
                className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-purple-500"
              />
              <button
                onClick={handleAnalyze}
                disabled={!stockCode.trim()}
                className="px-6 py-3 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg text-sm font-medium transition-colors"
              >
                {t.analysis.analyze}
              </button>
            </div>
          </div>

          {/* AI Analysis Component */}
          {activeStock && (
            <AiAnalysisTab
              key={activeStock}
              stockCode={activeStock}
              stockName={null}
              dateRangeStart="2024-01-01"
              dateRangeEnd="2025-12-31"
            />
          )}
        </div>
      )}

      {/* Market Briefing Tab */}
      {activeTab === "briefing" && (
        <div>
          {/* Morning / Closing toggle */}
          <div className="flex gap-2 mb-6">
            {(["morning", "closing"] as const).map((type) => (
              <button
                key={type}
                onClick={() => setBriefingType(type)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  briefingType === type
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:text-white"
                }`}
              >
                {type === "morning" ? t.analysis.morning : t.analysis.closing}
              </button>
            ))}
            {report?.report_date && (
              <span className="ml-auto text-xs text-gray-500 self-center">
                {report.report_date}
              </span>
            )}
          </div>

          {briefingLoading ? (
            <div className="text-center py-20 text-gray-500">{t.common.loading}</div>
          ) : !report || !summary ? (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-12 text-center">
              <p className="text-gray-500">{t.analysis.noReport}</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Headline + Badges */}
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                {summary.headline && (
                  <h3 className="text-lg font-semibold mb-4">{summary.headline}</h3>
                )}
                <div className="flex flex-wrap gap-3">
                  {summary.market_sentiment && (
                    <span className={`px-3 py-1.5 rounded-full text-xs font-medium ${
                      SENTIMENT_STYLES[summary.market_sentiment] || "bg-gray-700 text-gray-300"
                    }`}>
                      {t.analysis.sentiment}: {summary.market_sentiment}
                    </span>
                  )}
                  {summary.kospi_direction && (
                    <span className={`px-3 py-1.5 rounded-full text-xs font-medium ${
                      DIRECTION_STYLES[summary.kospi_direction] || "bg-gray-700 text-gray-300"
                    }`}>
                      {t.analysis.direction}: {summary.kospi_direction}
                    </span>
                  )}
                </div>
              </div>

              {/* Key Issues */}
              {summary.key_issues && summary.key_issues.length > 0 && (
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                  <h4 className="text-sm font-semibold text-gray-400 mb-3">
                    {t.analysis.keyIssues}
                  </h4>
                  <ul className="space-y-2">
                    {summary.key_issues.map((issue, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                        <span className="text-blue-400 mt-0.5">&#x2022;</span>
                        <span>{typeof issue === "string" ? issue : JSON.stringify(issue)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Watchlist */}
              {summary.watchlist && summary.watchlist.length > 0 && (
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                  <h4 className="text-sm font-semibold text-gray-400 mb-3">
                    {t.analysis.watchlist}
                  </h4>
                  <div className="space-y-2">
                    {summary.watchlist.map((item, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-3 p-3 bg-gray-800 rounded-lg"
                      >
                        <span className="text-xs text-gray-500 w-6">#{i + 1}</span>
                        {item.code && (
                          <span className="text-sm font-mono text-blue-400 w-16">
                            {item.code}
                          </span>
                        )}
                        {item.name && (
                          <span className="text-sm text-gray-200 w-24">{item.name}</span>
                        )}
                        {item.reason && (
                          <span className="text-xs text-gray-500 flex-1">{item.reason}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Risks */}
              {summary.risks && summary.risks.length > 0 && (
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                  <h4 className="text-sm font-semibold text-gray-400 mb-3">
                    {t.analysis.risks}
                  </h4>
                  <ul className="space-y-2">
                    {summary.risks.map((risk, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                        <span className="text-red-400 mt-0.5">&#x26A0;</span>
                        <span>{typeof risk === "string" ? risk : JSON.stringify(risk)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Strategy */}
              {summary.strategy && (
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                  <h4 className="text-sm font-semibold text-gray-400 mb-3">
                    {t.analysis.investStrategy}
                  </h4>
                  <p className="text-sm text-gray-300 whitespace-pre-wrap">
                    {summary.strategy}
                  </p>
                </div>
              )}

              {/* Active Themes */}
              {report.themes && report.themes.length > 0 && (
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                  <h4 className="text-sm font-semibold text-gray-400 mb-3">
                    Active Themes
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {report.themes.map((theme, i) => (
                      <span
                        key={i}
                        className="px-3 py-1.5 bg-purple-900/30 border border-purple-700/50 rounded-full text-xs text-purple-300"
                      >
                        {theme.name}
                        <span className="ml-1 text-purple-500">
                          ({theme.relevance_score.toFixed(0)})
                        </span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
