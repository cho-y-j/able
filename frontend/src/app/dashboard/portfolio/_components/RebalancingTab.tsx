"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";
import { formatKRW, metricColor } from "@/lib/charts";
import { useI18n } from "@/i18n";

// ─── Types ──────────────────────────────────────────────────

interface PositionSlice {
  stock_code: string;
  quantity: number;
  value: number;
  weight_pct: number;
}

interface RecipeAllocation {
  recipe_id: string;
  recipe_name: string;
  is_active: boolean;
  target_weight_pct: number;
  actual_weight_pct: number;
  actual_value: number;
  target_value: number;
  drift_pct: number;
  stock_codes: string[];
  positions: PositionSlice[];
}

interface AllocationData {
  total_capital: number;
  available_cash: number;
  allocated_capital: number;
  unallocated_pct: number;
  recipes: RecipeAllocation[];
  warnings: string[];
}

interface ConflictEntry {
  stock_code: string;
  recipes: { recipe_id: string; recipe_name: string; position_size_pct: number }[];
  combined_target_pct: number;
  current_position_value: number;
  risk_level: "low" | "medium" | "high";
}

interface ConflictData {
  conflicts: ConflictEntry[];
  total_overlapping_stocks: number;
  risk_warnings: string[];
}

interface RebalancingSuggestion {
  recipe_id: string;
  recipe_name: string;
  stock_code: string;
  action: "buy" | "sell" | "hold";
  current_quantity: number;
  target_quantity: number;
  delta_quantity: number;
  estimated_value: number;
  current_price: number;
  reason: string;
}

interface RebalancingData {
  suggestions: RebalancingSuggestion[];
  summary: {
    total_buys: number;
    total_sells: number;
    total_buy_value: number;
    total_sell_value: number;
    net_cash_required: number;
    available_cash: number;
    feasible: boolean;
  };
  warnings: string[];
}

// ─── Component ──────────────────────────────────────────────

export default function RebalancingTab() {
  const { t } = useI18n();
  const [allocations, setAllocations] = useState<AllocationData | null>(null);
  const [conflicts, setConflicts] = useState<ConflictData | null>(null);
  const [suggestions, setSuggestions] = useState<RebalancingData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get("/trading/portfolio/recipe-allocations").catch(() => ({ data: null })),
      api.get("/trading/portfolio/recipe-conflicts").catch(() => ({ data: null })),
      api.get("/trading/portfolio/rebalancing").catch(() => ({ data: null })),
    ]).then(([a, c, s]) => {
      setAllocations(a.data);
      setConflicts(c.data);
      setSuggestions(s.data);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-20 bg-gray-800 rounded-xl" />
          ))}
        </div>
        <div className="h-48 bg-gray-800 rounded-xl" />
        <div className="h-48 bg-gray-800 rounded-xl" />
      </div>
    );
  }

  // Empty state
  if (!allocations?.recipes?.length) {
    return (
      <div className="text-center py-12 bg-gray-800/50 rounded-xl border border-gray-700 border-dashed">
        <p className="text-gray-400 text-lg mb-2">{t.portfolio.noActiveRecipes}</p>
        <a
          href="/dashboard/recipes"
          className="inline-block mt-3 text-sm text-blue-400 hover:text-blue-300"
        >
          {t.portfolio.goToRecipes} &rarr;
        </a>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <p className="text-xs text-gray-500 mb-1">{t.portfolio.totalCapital}</p>
          <p className="text-xl font-bold text-white">{formatKRW(allocations.total_capital)}</p>
        </div>
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <p className="text-xs text-gray-500 mb-1">{t.portfolio.availableCash}</p>
          <p className="text-xl font-bold text-white">{formatKRW(allocations.available_cash)}</p>
        </div>
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <p className="text-xs text-gray-500 mb-1">{t.portfolio.unallocated}</p>
          <p className="text-xl font-bold text-gray-400">{allocations.unallocated_pct.toFixed(1)}%</p>
        </div>
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <p className="text-xs text-gray-500 mb-1">{t.portfolio.conflicts}</p>
          <p className={`text-xl font-bold ${conflicts && conflicts.total_overlapping_stocks > 0 ? "text-yellow-400" : "text-green-400"}`}>
            {conflicts?.total_overlapping_stocks ?? 0}
          </p>
        </div>
      </div>

      {/* Warnings */}
      {allocations.warnings.length > 0 && (
        <div className="bg-yellow-900/20 border border-yellow-700/30 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-yellow-400 mb-2">{t.portfolio.warnings}</h3>
          <ul className="space-y-1">
            {allocations.warnings.map((w, i) => (
              <li key={i} className="text-sm text-yellow-300/80">{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Recipe Allocation Cards */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">{t.portfolio.recipeAllocations}</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {allocations.recipes.map((r) => (
            <div key={r.recipe_id} className="bg-gray-900 rounded-xl border border-gray-800 p-5">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-medium text-white">{r.recipe_name}</h4>
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded ${
                    r.drift_pct > 1
                      ? "bg-green-500/20 text-green-400"
                      : r.drift_pct < -1
                      ? "bg-red-500/20 text-red-400"
                      : "bg-gray-700 text-gray-400"
                  }`}
                >
                  {r.drift_pct > 0 ? "+" : ""}{r.drift_pct.toFixed(1)}%
                </span>
              </div>

              {/* Target vs Actual bars */}
              <div className="space-y-2 mb-3">
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-gray-500">{t.portfolio.targetWeight}</span>
                    <span className="text-blue-400">{r.target_weight_pct.toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-800 rounded-full h-2">
                    <div
                      className="bg-blue-500 h-2 rounded-full"
                      style={{ width: `${Math.min(r.target_weight_pct, 100)}%` }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-gray-500">{t.portfolio.actualWeight}</span>
                    <span className={metricColor(r.drift_pct)}>{r.actual_weight_pct.toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-800 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${r.drift_pct >= 0 ? "bg-green-500" : "bg-red-500"}`}
                      style={{ width: `${Math.min(r.actual_weight_pct, 100)}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Stock codes */}
              <div className="flex flex-wrap gap-1">
                {r.stock_codes.map((sc) => (
                  <span key={sc} className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">
                    {sc}
                  </span>
                ))}
              </div>

              {/* Value */}
              <p className="text-xs text-gray-500 mt-2">
                {formatKRW(r.actual_value)} / {formatKRW(r.target_value)}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Conflict Alerts */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">{t.portfolio.conflicts}</h3>
        {conflicts && conflicts.conflicts.length > 0 ? (
          <div className="bg-yellow-900/20 border border-yellow-700/30 rounded-xl p-4">
            <p className="text-sm text-yellow-300/80 mb-3">{t.portfolio.conflictsDesc}</p>
            <div className="space-y-3">
              {conflicts.conflicts.map((c) => (
                <div key={c.stock_code} className="flex items-center justify-between py-2 border-b border-yellow-700/20 last:border-0">
                  <div>
                    <span className="text-sm font-mono text-white">{c.stock_code}</span>
                    <div className="flex gap-1 mt-1">
                      {c.recipes.map((r) => (
                        <span key={r.recipe_id} className="text-xs bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded">
                          {r.recipe_name} ({r.position_size_pct}%)
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="text-right">
                    <span
                      className={`text-xs font-medium px-2 py-0.5 rounded ${
                        c.risk_level === "high"
                          ? "bg-red-500/20 text-red-400"
                          : c.risk_level === "medium"
                          ? "bg-yellow-500/20 text-yellow-400"
                          : "bg-green-500/20 text-green-400"
                      }`}
                    >
                      {c.risk_level.toUpperCase()}
                    </span>
                    <p className="text-xs text-gray-500 mt-1">
                      {t.portfolio.combinedTarget}: {c.combined_target_pct}%
                    </p>
                  </div>
                </div>
              ))}
            </div>
            {conflicts.risk_warnings.length > 0 && (
              <div className="mt-3 pt-3 border-t border-yellow-700/20">
                {conflicts.risk_warnings.map((w, i) => (
                  <p key={i} className="text-xs text-red-400">{w}</p>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 text-center">
            <p className="text-gray-500 text-sm">{t.portfolio.noConflicts}</p>
          </div>
        )}
      </div>

      {/* Rebalancing Suggestions */}
      {suggestions && (
        <div>
          <h3 className="text-lg font-semibold text-white mb-4">{t.portfolio.rebalancingSuggestions}</h3>

          {suggestions.suggestions.length > 0 ? (
            <>
              <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-800 text-gray-400">
                      <th className="text-left p-3">{t.common.stock}</th>
                      <th className="text-center p-3">{t.portfolio.action}</th>
                      <th className="text-right p-3">{t.portfolio.currentQty}</th>
                      <th className="text-right p-3">{t.portfolio.targetQty}</th>
                      <th className="text-right p-3">{t.portfolio.deltaQty}</th>
                      <th className="text-right p-3">{t.portfolio.estimatedValue}</th>
                      <th className="text-left p-3">{t.portfolio.reason}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {suggestions.suggestions
                      .filter((s) => s.action !== "hold")
                      .map((s, i) => (
                        <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                          <td className="p-3 text-white font-mono text-xs">{s.stock_code}</td>
                          <td className="p-3 text-center">
                            <span
                              className={`text-xs font-medium px-2 py-0.5 rounded ${
                                s.action === "buy"
                                  ? "bg-green-900/30 text-green-400"
                                  : "bg-red-900/30 text-red-400"
                              }`}
                            >
                              {s.action === "buy" ? "매수" : "매도"}
                            </span>
                          </td>
                          <td className="p-3 text-right font-mono text-gray-400">
                            {s.current_quantity.toLocaleString()}
                          </td>
                          <td className="p-3 text-right font-mono text-gray-300">
                            {s.target_quantity.toLocaleString()}
                          </td>
                          <td className={`p-3 text-right font-mono ${s.delta_quantity > 0 ? "text-green-400" : "text-red-400"}`}>
                            {s.delta_quantity > 0 ? "+" : ""}{s.delta_quantity.toLocaleString()}
                          </td>
                          <td className="p-3 text-right font-mono text-gray-300">
                            {formatKRW(s.estimated_value)}
                          </td>
                          <td className="p-3 text-gray-500 text-xs max-w-[200px] truncate">
                            {s.reason}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>

              {/* Summary */}
              <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-xs text-gray-500">{t.portfolio.totalBuys}</p>
                  <p className="text-lg font-semibold text-green-400">
                    {suggestions.summary.total_buys}건 · {formatKRW(suggestions.summary.total_buy_value)}
                  </p>
                </div>
                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-xs text-gray-500">{t.portfolio.totalSells}</p>
                  <p className="text-lg font-semibold text-red-400">
                    {suggestions.summary.total_sells}건 · {formatKRW(suggestions.summary.total_sell_value)}
                  </p>
                </div>
                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-xs text-gray-500">{t.portfolio.netCashRequired}</p>
                  <p className="text-lg font-semibold text-white">
                    {formatKRW(suggestions.summary.net_cash_required)}
                  </p>
                </div>
                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-xs text-gray-500">{t.common.status}</p>
                  <p className={`text-lg font-semibold ${suggestions.summary.feasible ? "text-green-400" : "text-red-400"}`}>
                    {suggestions.summary.feasible ? t.portfolio.feasible : t.portfolio.notFeasible}
                  </p>
                </div>
              </div>
            </>
          ) : (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 text-center">
              <p className="text-gray-500 text-sm">{t.portfolio.onTarget}</p>
            </div>
          )}

          {/* Rebalancing warnings */}
          {suggestions.warnings.length > 0 && (
            <div className="mt-4 bg-yellow-900/20 border border-yellow-700/30 rounded-xl p-4">
              <ul className="space-y-1">
                {suggestions.warnings.map((w, i) => (
                  <li key={i} className="text-sm text-yellow-300/80">{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
