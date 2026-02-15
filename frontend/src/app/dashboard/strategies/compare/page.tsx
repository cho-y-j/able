"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import api from "@/lib/api";
import { useI18n } from "@/i18n";
import {
  CHART_COLORS,
  DEFAULT_CHART_OPTIONS,
  formatPct,
  scoreColor,
  gradeFromScore,
  metricColor,
} from "@/lib/charts";

interface StrategySummary {
  id: string;
  name: string;
  stock_code: string;
  strategy_type: string;
  composite_score: number | null;
  status: string;
}

interface StrategyCompare {
  strategy_id: string;
  name: string;
  stock_code: string;
  strategy_type: string;
  composite_score: number | null;
  status: string;
  backtest?: {
    id: string;
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
    equity_curve?: number[];
    date_range_start?: string;
  };
}

interface CompareResult {
  strategies: StrategyCompare[];
  ranking: { rank: number; strategy_id: string; name: string; score: number | null }[];
}

const LINE_COLORS = [
  CHART_COLORS.blue,
  CHART_COLORS.up,
  CHART_COLORS.yellow,
  CHART_COLORS.purple,
  "#EC4899", // pink
  "#F97316", // orange
  "#06B6D4", // cyan
  "#84CC16", // lime
];

export default function StrategyComparePage() {
  const { t } = useI18n();
  const [strategies, setStrategies] = useState<StrategySummary[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [listLoading, setListLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"equity" | "metrics">("equity");

  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchStrategies();
  }, []);

  const fetchStrategies = async () => {
    try {
      const { data } = await api.get("/strategies");
      setStrategies(data);
    } catch {
      setStrategies([]);
    } finally {
      setListLoading(false);
    }
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const compare = async () => {
    if (selected.size < 2) return;
    setLoading(true);
    setError("");
    try {
      const ids = Array.from(selected).join(",");
      const { data } = await api.get(
        `/backtests/compare?strategy_ids=${ids}&include_curves=true`
      );
      setResult(data);
      setActiveTab("equity");
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Comparison failed";
      setError(msg);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  // Equity curve overlay chart
  const renderChart = useCallback(async () => {
    if (!chartRef.current || !result) return;

    const curvesData = result.strategies.filter(
      (s) => s.backtest?.equity_curve?.length
    );
    if (curvesData.length === 0) return;

    try {
      const { createChart, LineSeries } = await import("lightweight-charts");

      chartRef.current.innerHTML = "";

      const chart = createChart(chartRef.current, {
        width: chartRef.current.clientWidth,
        height: 400,
        ...DEFAULT_CHART_OPTIONS,
      });

      curvesData.forEach((s, idx) => {
        const curve = s.backtest!.equity_curve!;
        const startDate = new Date(s.backtest!.date_range_start || "2024-01-01");
        const color = LINE_COLORS[idx % LINE_COLORS.length];

        const series = chart.addSeries(LineSeries, {
          color,
          lineWidth: 2,
          title: s.name,
        });

        const data = curve.map((value, i) => {
          const d = new Date(startDate);
          d.setDate(d.getDate() + i);
          return { time: d.toISOString().split("T")[0], value };
        });

        series.setData(data as Parameters<typeof series.setData>[0]);
      });

      chart.timeScale().fitContent();

      const handleResize = () => {
        if (chartRef.current) {
          chart.applyOptions({ width: chartRef.current.clientWidth });
        }
      };
      window.addEventListener("resize", handleResize);
      return () => window.removeEventListener("resize", handleResize);
    } catch {
      // chart library not available
    }
  }, [result]);

  useEffect(() => {
    if (activeTab === "equity" && result) renderChart();
  }, [activeTab, result, renderChart]);

  const metrics = [
    { key: "total_return", label: t.strategies.totalReturn, fmt: formatPct },
    { key: "annual_return", label: t.backtests.annualReturn, fmt: formatPct },
    { key: "sharpe_ratio", label: t.backtests.sharpeRatio, fmt: (v: number) => v?.toFixed(2) ?? "-" },
    { key: "sortino_ratio", label: "Sortino Ratio", fmt: (v: number) => v?.toFixed(2) ?? "-" },
    { key: "max_drawdown", label: t.backtests.maxDrawdown, fmt: formatPct },
    { key: "win_rate", label: t.backtests.winRate, fmt: (v: number) => `${v?.toFixed(1)}%` },
    { key: "profit_factor", label: t.backtests.profitFactor, fmt: (v: number) => v?.toFixed(2) ?? "-" },
    { key: "calmar_ratio", label: "Calmar Ratio", fmt: (v: number) => v?.toFixed(2) ?? "-" },
    { key: "wfa_score", label: "WFA Score", fmt: (v: number) => v?.toFixed(0) ?? "-" },
    { key: "mc_score", label: "MC Score", fmt: (v: number) => v?.toFixed(0) ?? "-" },
    { key: "oos_score", label: "OOS Score", fmt: (v: number) => v?.toFixed(0) ?? "-" },
  ];

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <Link href="/dashboard/strategies" className="text-gray-400 hover:text-white text-sm">
          &larr; {t.strategies.title}
        </Link>
        <h2 className="text-2xl font-bold">{t.backtests.compare}</h2>
      </div>

      {/* Strategy Selection */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <label className="text-sm text-gray-400">
            {t.backtests.selectStrategies}
          </label>
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500">
              {selected.size} {t.backtests.selected}
            </span>
            <button
              onClick={compare}
              disabled={loading || selected.size < 2}
              className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg text-sm font-medium transition-colors"
            >
              {loading ? "..." : t.backtests.compare}
            </button>
          </div>
        </div>

        {listLoading ? (
          <div className="text-center py-8 text-gray-500">{t.common.loading}</div>
        ) : strategies.length === 0 ? (
          <div className="text-center py-8 text-gray-600">
            {t.strategies.noStrategies}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 max-h-[300px] overflow-y-auto">
            {strategies.map((s) => (
              <label
                key={s.id}
                className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                  selected.has(s.id)
                    ? "border-blue-500/50 bg-blue-500/10"
                    : "border-gray-800 bg-gray-800/30 hover:bg-gray-800/50"
                }`}
              >
                <input
                  type="checkbox"
                  checked={selected.has(s.id)}
                  onChange={() => toggleSelect(s.id)}
                  className="accent-blue-500"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-200 truncate">{s.name}</div>
                  <div className="text-xs text-gray-500">
                    {s.stock_code} &middot; {s.strategy_type}
                  </div>
                </div>
                {s.composite_score != null && (
                  <span className={`text-xs font-bold ${scoreColor(s.composite_score)}`}>
                    {gradeFromScore(s.composite_score)}
                  </span>
                )}
              </label>
            ))}
          </div>
        )}
        {error && <p className="text-red-400 text-sm mt-3">{error}</p>}
      </div>

      {/* Results */}
      {result && (
        <>
          {/* Ranking */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
            <h3 className="text-lg font-semibold mb-4">Ranking</h3>
            <div className="flex gap-4 overflow-x-auto">
              {result.ranking.map((r) => (
                <div
                  key={r.strategy_id}
                  className={`flex-1 min-w-[140px] rounded-lg p-4 border ${
                    r.rank === 1
                      ? "border-yellow-500/30 bg-yellow-500/5"
                      : "border-gray-800 bg-gray-800/50"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className={`text-2xl font-bold ${
                        r.rank === 1
                          ? "text-yellow-400"
                          : r.rank === 2
                            ? "text-gray-300"
                            : "text-gray-500"
                      }`}
                    >
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

          {/* Tabs */}
          <div className="flex gap-2 mb-4">
            {(["equity", "metrics"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === tab
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:text-white"
                }`}
              >
                {tab === "equity"
                  ? t.backtests.equityCurveOverlay
                  : t.backtests.metrics}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            {activeTab === "equity" && (
              <div className="p-6">
                {/* Legend */}
                <div className="flex flex-wrap gap-4 mb-4">
                  {result.strategies
                    .filter((s) => s.backtest?.equity_curve?.length)
                    .map((s, idx) => (
                      <div key={s.strategy_id} className="flex items-center gap-2 text-sm">
                        <span
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: LINE_COLORS[idx % LINE_COLORS.length] }}
                        />
                        <span className="text-gray-300">{s.name}</span>
                      </div>
                    ))}
                </div>
                <div ref={chartRef} className="w-full" style={{ minHeight: 400 }}>
                  {!result.strategies.some((s) => s.backtest?.equity_curve?.length) && (
                    <div className="h-96 flex items-center justify-center text-gray-600">
                      {t.backtests.noResults}
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === "metrics" && (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800 text-gray-400">
                    <th className="text-left p-4">{t.common.metric}</th>
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
                      (s) =>
                        s.backtest?.[key as keyof typeof s.backtest] as
                          | number
                          | undefined
                    );
                    const nums = values.filter((v): v is number => v != null);
                    const best = nums.length > 0 ? Math.max(...nums) : null;

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
                                isBest
                                  ? "text-yellow-400 font-bold"
                                  : metricColor(val ?? null)
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
            )}
          </div>
        </>
      )}
    </div>
  );
}
