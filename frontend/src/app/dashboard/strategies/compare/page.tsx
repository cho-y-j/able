"use client";

import { useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import { formatPct, scoreColor, gradeFromScore, metricColor } from "@/lib/charts";

interface StrategyCompare {
  strategy_id: string;
  name: string;
  stock_code: string;
  strategy_type: string;
  composite_score: number | null;
  status: string;
  backtest?: {
    total_return: number;
    annual_return: number;
    sharpe_ratio: number;
    sortino_ratio: number;
    max_drawdown: number;
    win_rate: number;
    profit_factor: number;
    calmar_ratio: number;
    wfa_score: number;
    mc_score: number;
    oos_score: number;
  };
}

interface CompareResult {
  strategies: StrategyCompare[];
  ranking: { rank: number; strategy_id: string; name: string; score: number | null }[];
}

export default function StrategyComparePage() {
  const [strategyIds, setStrategyIds] = useState("");
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const compare = async () => {
    if (!strategyIds.trim()) return;
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get(`/backtests/compare?strategy_ids=${strategyIds.trim()}`);
      setResult(data);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Comparison failed";
      setError(msg);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const metrics = [
    { key: "total_return", label: "Total Return", fmt: formatPct },
    { key: "annual_return", label: "Annual Return", fmt: formatPct },
    { key: "sharpe_ratio", label: "Sharpe Ratio", fmt: (v: number) => v?.toFixed(2) ?? "-" },
    { key: "sortino_ratio", label: "Sortino Ratio", fmt: (v: number) => v?.toFixed(2) ?? "-" },
    { key: "max_drawdown", label: "Max Drawdown", fmt: formatPct },
    { key: "win_rate", label: "Win Rate", fmt: (v: number) => `${v?.toFixed(1)}%` },
    { key: "profit_factor", label: "Profit Factor", fmt: (v: number) => v?.toFixed(2) ?? "-" },
    { key: "calmar_ratio", label: "Calmar Ratio", fmt: (v: number) => v?.toFixed(2) ?? "-" },
    { key: "wfa_score", label: "WFA Score", fmt: (v: number) => v?.toFixed(0) ?? "-" },
    { key: "mc_score", label: "MC Score", fmt: (v: number) => v?.toFixed(0) ?? "-" },
    { key: "oos_score", label: "OOS Score", fmt: (v: number) => v?.toFixed(0) ?? "-" },
  ];

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <Link href="/dashboard/strategies" className="text-gray-400 hover:text-white text-sm">
          ← Strategies
        </Link>
        <h2 className="text-2xl font-bold">Strategy Comparison</h2>
      </div>

      {/* Input */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <label className="block text-sm text-gray-400 mb-2">
          Enter strategy IDs (comma-separated)
        </label>
        <div className="flex gap-3">
          <input
            type="text"
            value={strategyIds}
            onChange={(e) => setStrategyIds(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && compare()}
            placeholder="abc-123, def-456, ghi-789"
            className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={compare}
            disabled={loading}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 rounded-lg text-sm font-medium transition-colors"
          >
            {loading ? "Comparing..." : "Compare"}
          </button>
        </div>
        {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
      </div>

      {/* Ranking */}
      {result && (
        <>
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
            <h3 className="text-lg font-semibold mb-4">Ranking</h3>
            <div className="flex gap-4">
              {result.ranking.map((r) => (
                <div
                  key={r.strategy_id}
                  className={`flex-1 rounded-lg p-4 border ${
                    r.rank === 1 ? "border-yellow-500/30 bg-yellow-500/5" : "border-gray-800 bg-gray-800/50"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-2xl font-bold ${
                      r.rank === 1 ? "text-yellow-400" : r.rank === 2 ? "text-gray-300" : "text-gray-500"
                    }`}>
                      #{r.rank}
                    </span>
                    <span className={`text-sm font-medium ${scoreColor(r.score)}`}>
                      {gradeFromScore(r.score)}
                    </span>
                  </div>
                  <p className="text-sm text-gray-300 truncate">{r.name}</p>
                  <p className="text-xs text-gray-500">{r.score?.toFixed(1) ?? "-"} pts</p>
                </div>
              ))}
            </div>
          </div>

          {/* Comparison Table */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400">
                  <th className="text-left p-4">Metric</th>
                  {result.strategies.map((s) => (
                    <th key={s.strategy_id} className="text-right p-4">
                      <div className="text-gray-300">{s.name}</div>
                      <div className="text-xs text-gray-500">{s.stock_code}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {metrics.map(({ key, label, fmt }) => {
                  const values = result.strategies.map(
                    (s) => s.backtest?.[key as keyof typeof s.backtest] as number | undefined
                  );
                  const best = Math.max(...values.filter((v): v is number => v != null));

                  return (
                    <tr key={key} className="border-b border-gray-800/50">
                      <td className="p-4 text-gray-400">{label}</td>
                      {result.strategies.map((s, i) => {
                        const val = values[i];
                        const isBest = val === best && val != null;
                        return (
                          <td
                            key={s.strategy_id}
                            className={`p-4 text-right font-mono ${
                              isBest ? "text-yellow-400 font-bold" : metricColor(val ?? null)
                            }`}
                          >
                            {val != null ? fmt(val) : "-"}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
