"use client";

import { useState, useCallback } from "react";
import api from "@/lib/api";
import { useI18n } from "@/i18n";
import { StockAutocomplete } from "@/components/StockAutocomplete";

interface IntradayFactor {
  [key: string]: number;
}

interface IntradaySignal {
  name: string;
  direction: "bullish" | "bearish" | "neutral";
  strength: number;
  detail: string;
}

interface IntradaySummary {
  sentiment: number;
  sentiment_label: string;
  bullish_count: number;
  bearish_count: number;
  recommendation: string;
}

interface CandleData {
  time: string;
  date?: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface IntradayResult {
  stock_code: string;
  interval: number;
  candle_count: number;
  factors: IntradayFactor;
  signals: IntradaySignal[];
  summary: IntradaySummary;
  candles: CandleData[];
  market_date: string | null;
}

const INTERVALS = [1, 3, 5, 10, 15, 30, 60];

const FACTOR_LABELS: Record<string, string> = {
  rsi_9m: "RSI (9)",
  macd_hist_m: "MACD Histogram",
  macd_cross_m: "MACD Cross",
  bb_position_m: "BB Position",
  stoch_k_m: "Stochastic %K",
  rvol_m: "Relative Volume",
  vol_spike_m: "Volume Spike",
  roc_5m: "ROC (5)",
  vwap: "VWAP",
  vwap_spread_m: "VWAP Spread %",
  atr_pct_m: "ATR %",
  session_position: "Session Position",
};

export default function IntradayPage() {
  const { t } = useI18n();
  const [stockCode, setStockCode] = useState("");
  const [stockName, setStockName] = useState("");
  const [interval, setInterval] = useState(5);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<IntradayResult | null>(null);
  const [error, setError] = useState("");

  const analyze = useCallback(async () => {
    if (!stockCode) return;
    setLoading(true);
    setError("");
    try {
      const resp = await api.get(`/market/intraday/${stockCode}?interval=${interval}`);
      setResult(resp.data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "분석 실패";
      setError(message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [stockCode, interval]);

  const sentimentColor = (s: number) => {
    if (s > 0.3) return "text-red-400";
    if (s < -0.3) return "text-blue-400";
    return "text-gray-400";
  };

  const directionBadge = (dir: string) => {
    if (dir === "bullish") return "bg-red-500/20 text-red-400 border-red-500/30";
    if (dir === "bearish") return "bg-blue-500/20 text-blue-400 border-blue-500/30";
    return "bg-gray-500/20 text-gray-400 border-gray-500/30";
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">{t.intraday.title}</h1>
        <p className="text-sm text-gray-400 mt-1">{t.intraday.description}</p>
      </div>

      {/* Controls */}
      <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[200px]">
            <label className="text-xs text-gray-400 mb-1 block">{t.intraday.selectStock}</label>
            <StockAutocomplete
              onSelect={(code, name) => {
                setStockCode(code);
                setStockName(name || code);
              }}
            />
          </div>

          <div>
            <label className="text-xs text-gray-400 mb-1 block">{t.intraday.interval}</label>
            <div className="flex gap-1">
              {INTERVALS.map((iv) => (
                <button
                  key={iv}
                  onClick={() => setInterval(iv)}
                  className={`px-3 py-2 text-sm rounded-lg border transition-colors ${
                    interval === iv
                      ? "bg-indigo-600 border-indigo-500 text-white"
                      : "bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600"
                  }`}
                >
                  {iv}m
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={analyze}
            disabled={!stockCode || loading}
            className="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 rounded-lg text-sm font-medium transition-colors"
          >
            {loading ? "..." : t.intraday.analyze}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-500/30 text-red-400 p-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Summary Card */}
          <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold">
                  {stockName} <span className="text-gray-500 text-sm">{stockCode}</span>
                </h2>
                <p className="text-xs text-gray-500">
                  {result.candle_count} {t.intraday.candleCount} | {result.interval}m
                </p>
              </div>
              <div className="text-right">
                <div className={`text-2xl font-bold ${sentimentColor(result.summary.sentiment)}`}>
                  {result.summary.sentiment_label}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {t.intraday.recommendation}: {result.summary.recommendation}
                </div>
              </div>
            </div>

            {/* Signal Summary Bar */}
            <div className="flex gap-4 text-sm">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-red-500" />
                <span className="text-gray-400">{t.intraday.bullish}: {result.summary.bullish_count}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-blue-500" />
                <span className="text-gray-400">{t.intraday.bearish}: {result.summary.bearish_count}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-gray-500">{t.intraday.sentiment}:</span>
                <span className={sentimentColor(result.summary.sentiment)}>
                  {result.summary.sentiment > 0 ? "+" : ""}
                  {(result.summary.sentiment * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Signals */}
            <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
              <h3 className="text-sm font-semibold text-gray-300 mb-3">{t.intraday.signals}</h3>
              {result.signals.length === 0 ? (
                <p className="text-sm text-gray-500">현재 활성 시그널 없음</p>
              ) : (
                <div className="space-y-2">
                  {result.signals.map((sig, i) => (
                    <div key={i} className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg">
                      <div className="flex items-center gap-3">
                        <span className={`px-2 py-0.5 text-xs rounded border ${directionBadge(sig.direction)}`}>
                          {sig.direction === "bullish" ? "BUY" : "SELL"}
                        </span>
                        <div>
                          <div className="text-sm font-medium">{sig.name}</div>
                          <div className="text-xs text-gray-500">{sig.detail}</div>
                        </div>
                      </div>
                      {/* Strength bar */}
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              sig.direction === "bullish" ? "bg-red-500" : "bg-blue-500"
                            }`}
                            style={{ width: `${sig.strength * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-500 w-8">{(sig.strength * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Factors */}
            <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
              <h3 className="text-sm font-semibold text-gray-300 mb-3">{t.intraday.factors}</h3>
              <div className="space-y-2">
                {Object.entries(result.factors).map(([key, val]) => (
                  <div key={key} className="flex items-center justify-between py-1.5 border-b border-gray-800/50">
                    <span className="text-sm text-gray-400">{FACTOR_LABELS[key] || key}</span>
                    <span className="text-sm font-mono">
                      {typeof val === "number" ? val.toFixed(2) : val}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Candle Data Table (최근 20개만) */}
          <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-300">{t.intraday.recentCandles}</h3>
              {result.market_date && (
                <span className="text-xs text-gray-500">{result.market_date}</span>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 border-b border-gray-800">
                    <th className="text-left py-2 pr-4">{t.intraday.time}</th>
                    <th className="text-right py-2 pr-4">{t.intraday.open}</th>
                    <th className="text-right py-2 pr-4">{t.intraday.high}</th>
                    <th className="text-right py-2 pr-4">{t.intraday.low}</th>
                    <th className="text-right py-2 pr-4">{t.intraday.close}</th>
                    <th className="text-right py-2">{t.intraday.volume}</th>
                  </tr>
                </thead>
                <tbody>
                  {result.candles.slice(-20).reverse().map((c, i) => {
                    const timeStr = c.time?.length >= 6
                      ? `${c.time.slice(0, 2)}:${c.time.slice(2, 4)}:${c.time.slice(4, 6)}`
                      : c.time?.length >= 4
                        ? `${c.time.slice(0, 2)}:${c.time.slice(2, 4)}`
                        : c.time;
                    const isUp = c.close >= c.open;
                    return (
                      <tr key={i} className="border-b border-gray-800/30">
                        <td className="py-1.5 pr-4 text-gray-400 font-mono">{timeStr}</td>
                        <td className="text-right pr-4 font-mono">{c.open.toLocaleString()}</td>
                        <td className="text-right pr-4 font-mono text-red-400">{c.high.toLocaleString()}</td>
                        <td className="text-right pr-4 font-mono text-blue-400">{c.low.toLocaleString()}</td>
                        <td className={`text-right pr-4 font-mono ${isUp ? "text-red-400" : "text-blue-400"}`}>
                          {c.close.toLocaleString()}
                        </td>
                        <td className="text-right font-mono text-gray-500">{c.volume.toLocaleString()}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!result && !loading && !error && (
        <div className="text-center py-20 text-gray-500">
          <div className="text-4xl mb-4">W</div>
          <p>{t.intraday.selectStock}</p>
        </div>
      )}
    </div>
  );
}
