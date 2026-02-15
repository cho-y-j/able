"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import api from "@/lib/api";
import { useI18n } from "@/i18n";
import {
  CHART_COLORS,
  DEFAULT_CHART_OPTIONS,
  formatPct,
  metricColor,
} from "@/lib/charts";
import type { Recipe } from "../types";

interface BacktestResult {
  recipeId: string;
  recipeName: string;
  composite_score: number | null;
  grade: string | null;
  metrics: Record<string, number>;
  equity_curve: { date: string; value: number }[];
}

const LINE_COLORS = [
  CHART_COLORS.blue,
  CHART_COLORS.up,
  CHART_COLORS.yellow,
  CHART_COLORS.purple,
  "#EC4899",
  "#F97316",
  "#06B6D4",
  "#84CC16",
];

export default function RecipeComparePage() {
  const { t } = useI18n();
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [stockCode, setStockCode] = useState("");
  const [results, setResults] = useState<BacktestResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [listLoading, setListLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"equity" | "metrics">("equity");

  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchRecipes();
  }, []);

  const fetchRecipes = async () => {
    try {
      const { data } = await api.get("/recipes");
      setRecipes(data);
    } catch {
      setRecipes([]);
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

  const runComparison = async () => {
    if (selected.size < 2 || !stockCode.trim()) return;
    setLoading(true);
    setError("");
    setResults([]);

    try {
      const promises = Array.from(selected).map(async (id) => {
        const recipe = recipes.find((r) => r.id === id);
        const { data } = await api.post(`/recipes/${id}/backtest`, {
          stock_code: stockCode.trim(),
        });
        return {
          recipeId: id,
          recipeName: recipe?.name || id,
          composite_score: data.composite_score,
          grade: data.grade,
          metrics: data.metrics,
          equity_curve: data.equity_curve,
        } as BacktestResult;
      });

      const all = await Promise.all(promises);
      // Sort by composite_score descending
      all.sort(
        (a, b) => (b.composite_score ?? -Infinity) - (a.composite_score ?? -Infinity)
      );
      setResults(all);
      setActiveTab("equity");
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Comparison failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  // Equity curve overlay chart
  const renderChart = useCallback(async () => {
    if (!chartRef.current || results.length === 0) return;

    const withCurves = results.filter((r) => r.equity_curve?.length > 0);
    if (withCurves.length === 0) return;

    try {
      const { createChart, LineSeries } = await import("lightweight-charts");

      chartRef.current.innerHTML = "";

      const chart = createChart(chartRef.current, {
        width: chartRef.current.clientWidth,
        height: 400,
        ...DEFAULT_CHART_OPTIONS,
      });

      withCurves.forEach((r, idx) => {
        const color = LINE_COLORS[idx % LINE_COLORS.length];
        const series = chart.addSeries(LineSeries, {
          color,
          lineWidth: 2,
          title: r.recipeName,
        });

        const data = r.equity_curve.map((p) => ({
          time: p.date.split("T")[0],
          value: p.value,
        }));

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
  }, [results]);

  useEffect(() => {
    if (activeTab === "equity" && results.length > 0) renderChart();
  }, [activeTab, results, renderChart]);

  const canRun = selected.size >= 2 && stockCode.trim().length > 0;

  const metrics = [
    { key: "total_return", label: t.strategies.totalReturn, fmt: formatPct },
    { key: "annual_return", label: t.backtests.annualReturn, fmt: formatPct },
    {
      key: "sharpe_ratio",
      label: t.backtests.sharpeRatio,
      fmt: (v: number) => v?.toFixed(2) ?? "-",
    },
    { key: "max_drawdown", label: t.backtests.maxDrawdown, fmt: formatPct },
    {
      key: "win_rate",
      label: t.backtests.winRate,
      fmt: (v: number) => `${v?.toFixed(1)}%`,
    },
    {
      key: "profit_factor",
      label: t.backtests.profitFactor,
      fmt: (v: number) => v?.toFixed(2) ?? "-",
    },
    {
      key: "calmar_ratio",
      label: "Calmar Ratio",
      fmt: (v: number) => v?.toFixed(2) ?? "-",
    },
  ];

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <Link
          href="/dashboard/recipes"
          className="text-gray-400 hover:text-white text-sm"
        >
          &larr; {t.nav.recipes}
        </Link>
        <h2 className="text-2xl font-bold">{t.recipes.compare}</h2>
      </div>

      {/* Selection Panel */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <label className="text-sm text-gray-400">
            {t.recipes.selectRecipes}
          </label>
          <span className="text-xs text-gray-500">
            {selected.size} {t.backtests.selected}
          </span>
        </div>

        {listLoading ? (
          <div className="text-center py-8 text-gray-500">
            {t.common.loading}
          </div>
        ) : recipes.length === 0 ? (
          <div className="text-center py-8 text-gray-600">
            {t.recipes.noRecipes}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 max-h-[300px] overflow-y-auto mb-4">
            {recipes.map((r) => (
              <label
                key={r.id}
                className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                  selected.has(r.id)
                    ? "border-blue-500/50 bg-blue-500/10"
                    : "border-gray-800 bg-gray-800/30 hover:bg-gray-800/50"
                }`}
              >
                <input
                  type="checkbox"
                  checked={selected.has(r.id)}
                  onChange={() => toggleSelect(r.id)}
                  className="accent-blue-500"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-200 truncate">{r.name}</div>
                  <div className="text-xs text-gray-500">
                    {r.signal_config?.signals?.length || 0} signals &middot;{" "}
                    {r.signal_config?.combinator || "AND"}
                  </div>
                </div>
              </label>
            ))}
          </div>
        )}

        {/* Stock Code + Run */}
        <div className="flex gap-3">
          <input
            type="text"
            value={stockCode}
            onChange={(e) => setStockCode(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && canRun && runComparison()}
            placeholder={t.recipes.enterStockCode}
            className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={runComparison}
            disabled={loading || !canRun}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg text-sm font-medium transition-colors whitespace-nowrap"
          >
            {loading ? "..." : t.recipes.runCompare}
          </button>
        </div>

        {error && <p className="text-red-400 text-sm mt-3">{error}</p>}
      </div>

      {/* Results */}
      {results.length > 0 && (
        <>
          {/* Ranking */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
            <h3 className="text-lg font-semibold mb-4">{t.recipes.ranking}</h3>
            <div className="flex gap-4 overflow-x-auto">
              {results.map((r, i) => (
                <div
                  key={r.recipeId}
                  className={`flex-1 min-w-[140px] rounded-lg p-4 border ${
                    i === 0
                      ? "border-yellow-500/30 bg-yellow-500/5"
                      : "border-gray-800 bg-gray-800/50"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className={`text-2xl font-bold ${
                        i === 0
                          ? "text-yellow-400"
                          : i === 1
                            ? "text-gray-300"
                            : "text-gray-500"
                      }`}
                    >
                      #{i + 1}
                    </span>
                    {r.grade && (
                      <span className="text-sm font-medium text-blue-400">
                        {r.grade}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-300 truncate">
                    {r.recipeName}
                  </p>
                  <p className="text-xs text-gray-500">
                    {r.composite_score?.toFixed(1) ?? "-"} pts
                  </p>
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
                  {results
                    .filter((r) => r.equity_curve?.length > 0)
                    .map((r, idx) => (
                      <div
                        key={r.recipeId}
                        className="flex items-center gap-2 text-sm"
                      >
                        <span
                          className="w-3 h-3 rounded-full"
                          style={{
                            backgroundColor:
                              LINE_COLORS[idx % LINE_COLORS.length],
                          }}
                        />
                        <span className="text-gray-300">{r.recipeName}</span>
                      </div>
                    ))}
                </div>
                <div
                  ref={chartRef}
                  className="w-full"
                  style={{ minHeight: 400 }}
                >
                  {!results.some((r) => r.equity_curve?.length > 0) && (
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
                    {results.map((r) => (
                      <th key={r.recipeId} className="text-right p-4">
                        <div className="text-gray-300">{r.recipeName}</div>
                        <div className="text-xs text-gray-500">
                          {r.grade ?? "-"}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {metrics.map(({ key, label, fmt }) => {
                    const values = results.map((r) => r.metrics[key]);
                    const nums = values.filter(
                      (v): v is number => v != null
                    );
                    const best =
                      nums.length > 0 ? Math.max(...nums) : null;

                    return (
                      <tr key={key} className="border-b border-gray-800/50">
                        <td className="p-4 text-gray-400">{label}</td>
                        {results.map((r, i) => {
                          const val = values[i];
                          const isBest = val === best && val != null;
                          return (
                            <td
                              key={r.recipeId}
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
