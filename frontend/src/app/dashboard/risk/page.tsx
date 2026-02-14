"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";
import { formatKRW, formatPct, metricColor } from "@/lib/charts";
import { useI18n } from "@/i18n";

interface VarMethod {
  var: number;
  var_pct: number;
  cvar: number;
  cvar_pct: number;
}

interface StressPosition {
  stock_code: string;
  current_value: number;
  shock_pct: number;
  impact: number;
}

interface StressTest {
  scenario: string;
  description: string;
  impact: number;
  impact_pct: number;
  positions: StressPosition[];
}

interface RiskData {
  portfolio_value: number;
  confidence: number;
  horizon_days: number;
  var: {
    historical?: VarMethod;
    parametric?: VarMethod;
    monte_carlo?: VarMethod;
  };
  stress_tests: StressTest[];
  message?: string;
}

const METHOD_KEYS: Record<string, "historical" | "parametric" | "monteCarlo"> = {
  historical: "historical",
  parametric: "parametric",
  monte_carlo: "monteCarlo",
};

const SCENARIO_ICONS: Record<string, string> = {
  market_crash: "📉",
  sector_rotation: "🔄",
  flash_crash: "⚡",
  rate_hike: "📈",
  won_depreciation: "💱",
  black_swan: "🦢",
};

export default function RiskPage() {
  const [data, setData] = useState<RiskData | null>(null);
  const [loading, setLoading] = useState(true);
  const [confidence, setConfidence] = useState(0.95);
  const [horizon, setHorizon] = useState(1);
  const [expandedScenario, setExpandedScenario] = useState<string | null>(null);
  const { t } = useI18n();

  const fetchRisk = async () => {
    setLoading(true);
    try {
      const { data: res } = await api.get(
        `/trading/portfolio/risk?confidence=${confidence}&horizon_days=${horizon}`
      );
      setData(res);
    } catch {
      // handle error
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRisk();
  }, [confidence, horizon]);

  if (loading) {
    return <div className="text-center py-20 text-gray-500">{t.risk.loading}</div>;
  }

  if (!data || data.message) {
    return (
      <div>
        <h2 className="text-2xl font-bold mb-6">{t.risk.title}</h2>
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-12 text-center">
          <p className="text-gray-500">{data?.message || t.risk.noPositions}</p>
          <p className="text-sm text-gray-600 mt-2">{t.risk.requiresPositions}</p>
        </div>
      </div>
    );
  }

  const varMethods = data.var;
  const maxVar = Math.max(
    ...Object.values(varMethods).map((m) => m?.var || 0),
    1
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">{t.risk.title}</h2>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500">{t.risk.confidence}</label>
            <select
              value={confidence}
              onChange={(e) => setConfidence(Number(e.target.value))}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-300"
            >
              <option value={0.9}>90%</option>
              <option value={0.95}>95%</option>
              <option value={0.99}>99%</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500">{t.risk.horizon}</label>
            <select
              value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value))}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-300"
            >
              <option value={1}>{t.risk.day1}</option>
              <option value={5}>{t.risk.day5}</option>
              <option value={10}>{t.risk.day10}</option>
              <option value={21}>{t.risk.day21}</option>
            </select>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <SummaryCard label={t.risk.portfolioValue} value={formatKRW(data.portfolio_value)} />
        <SummaryCard
          label={`${t.risk.var} (${(data.confidence * 100).toFixed(0)}%)`}
          value={formatKRW(varMethods.historical?.var || 0)}
          sub={formatPct(varMethods.historical?.var_pct ? -varMethods.historical.var_pct : 0)}
          color="text-red-400"
        />
        <SummaryCard
          label={t.risk.expectedShortfall}
          value={formatKRW(varMethods.historical?.cvar || 0)}
          sub={formatPct(varMethods.historical?.cvar_pct ? -varMethods.historical.cvar_pct : 0)}
          color="text-red-400"
        />
        <SummaryCard
          label={t.risk.worstScenario}
          value={
            data.stress_tests.length > 0
              ? formatKRW(
                  Math.min(...data.stress_tests.map((s) => s.impact))
                )
              : "-"
          }
          sub={
            data.stress_tests.length > 0
              ? data.stress_tests.reduce((worst, s) =>
                  s.impact < worst.impact ? s : worst
                ).scenario.replace(/_/g, " ")
              : ""
          }
          color="text-red-400"
        />
      </div>

      {/* VaR Methods Comparison */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <h3 className="text-lg font-semibold mb-4">{t.risk.varComparison}</h3>
        <p className="text-xs text-gray-500 mb-4">
          {data.horizon_days}{t.risk.varComparisonDesc} {(data.confidence * 100).toFixed(0)}% {t.risk.confidenceLevel}
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {(["historical", "parametric", "monte_carlo"] as const).map((method) => {
            const m = varMethods[method];
            if (!m) return null;
            return (
              <div key={method} className="bg-gray-800 rounded-lg p-4">
                <h4 className="text-sm font-medium text-gray-400 mb-3">
                  {t.risk[METHOD_KEYS[method]]}
                </h4>
                <div className="space-y-3">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-gray-500">{t.risk.var}</span>
                      <span className="text-sm font-mono text-red-400">{formatKRW(m.var)}</span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-2">
                      <div
                        className="bg-red-500 h-2 rounded-full transition-all"
                        style={{ width: `${Math.min((m.var / maxVar) * 100, 100)}%` }}
                      />
                    </div>
                    <p className="text-xs text-gray-500 mt-1">{formatPct(-m.var_pct)} {t.risk.ofPortfolio}</p>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-gray-500">{t.risk.cvar}</span>
                      <span className="text-sm font-mono text-red-400">{formatKRW(m.cvar)}</span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-2">
                      <div
                        className="bg-red-700 h-2 rounded-full transition-all"
                        style={{ width: `${Math.min((m.cvar / maxVar) * 100, 100)}%` }}
                      />
                    </div>
                    <p className="text-xs text-gray-500 mt-1">{formatPct(-m.cvar_pct)} {t.risk.ofPortfolio}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Stress Tests */}
      {data.stress_tests.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="text-lg font-semibold mb-4">{t.risk.stressTests}</h3>
          <div className="space-y-3">
            {data.stress_tests.map((s) => {
              const isExpanded = expandedScenario === s.scenario;
              const impactRatio = Math.abs(s.impact_pct) / 30; // normalize to ~30% max
              return (
                <div key={s.scenario} className="bg-gray-800 rounded-lg overflow-hidden">
                  <button
                    onClick={() =>
                      setExpandedScenario(isExpanded ? null : s.scenario)
                    }
                    className="w-full p-4 flex items-center gap-3 hover:bg-gray-750 transition-colors text-left"
                  >
                    <span className="text-lg">
                      {SCENARIO_ICONS[s.scenario] || "🔍"}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-gray-300 capitalize">
                          {s.scenario.replace(/_/g, " ")}
                        </span>
                        <span className="text-sm font-mono text-red-400">
                          {formatKRW(s.impact)} ({formatPct(s.impact_pct)})
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 truncate">{s.description}</p>
                      <div className="w-full bg-gray-700 rounded-full h-1.5 mt-2">
                        <div
                          className="bg-red-500 h-1.5 rounded-full transition-all"
                          style={{
                            width: `${Math.min(impactRatio * 100, 100)}%`,
                          }}
                        />
                      </div>
                    </div>
                    <svg
                      className={`w-4 h-4 text-gray-500 transition-transform ${
                        isExpanded ? "rotate-180" : ""
                      }`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 9l-7 7-7-7"
                      />
                    </svg>
                  </button>

                  {isExpanded && s.positions.length > 0 && (
                    <div className="border-t border-gray-700 p-4">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-gray-500 text-xs">
                            <th className="text-left pb-2">{t.common.stock}</th>
                            <th className="text-right pb-2">{t.risk.currentValue}</th>
                            <th className="text-right pb-2">{t.risk.shock}</th>
                            <th className="text-right pb-2">{t.risk.impact}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {s.positions.map((p) => (
                            <tr
                              key={p.stock_code}
                              className="border-t border-gray-700/50"
                            >
                              <td className="py-2 text-gray-300">{p.stock_code}</td>
                              <td className="py-2 text-right text-gray-400 font-mono">
                                {formatKRW(p.current_value)}
                              </td>
                              <td className={`py-2 text-right font-mono ${metricColor(p.shock_pct)}`}>
                                {formatPct(p.shock_pct)}
                              </td>
                              <td className="py-2 text-right font-mono text-red-400">
                                {formatKRW(p.impact)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryCard({
  label,
  value,
  sub,
  color = "text-white",
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  );
}
