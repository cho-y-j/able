"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";
import { formatKRW, formatPct, metricColor } from "@/lib/charts";

interface PortfolioData {
  portfolio_value: number;
  total_invested: number;
  unrealized_pnl: number;
  realized_pnl: number;
  total_pnl: number;
  total_pnl_pct: number;
  position_count: number;
  allocation: {
    stock_code: string;
    stock_name: string | null;
    quantity: number;
    value: number;
    weight: number;
    unrealized_pnl: number;
    pnl_pct: number;
  }[];
  trade_stats: {
    total_trades: number;
    win_rate: number;
    avg_win: number;
    avg_loss: number;
    profit_factor: number;
    winning_trades: number;
    losing_trades: number;
  };
}

interface TradeRow {
  id: string;
  stock_code: string;
  side: string;
  quantity: number;
  entry_price: number;
  exit_price: number | null;
  pnl: number | null;
  pnl_percent: number | null;
  entry_at: string | null;
  exit_at: string | null;
}

interface StrategyPortfolio {
  total_exposure: number;
  net_exposure: number;
  long_exposure: number;
  short_exposure: number;
  hhi: number;
  stock_exposures: Record<string, number>;
  strategy_exposures: Record<string, { value: number; name: string }>;
  conflicts: { stock_code: string; long_strategies: string[]; short_strategies: string[] }[];
  warnings: string[];
}

interface AttributionEntry {
  key: string;
  name: string;
  pnl: number;
  pnl_pct: number;
  trade_count: number;
  win_count: number;
  loss_count: number;
  avg_pnl_per_trade: number;
}

interface AttributionData {
  total_pnl: number;
  by_strategy: AttributionEntry[];
  by_stock: AttributionEntry[];
  best_strategy: AttributionEntry | null;
  worst_strategy: AttributionEntry | null;
}

export default function PortfolioPage() {
  const [data, setData] = useState<PortfolioData | null>(null);
  const [trades, setTrades] = useState<TradeRow[]>([]);
  const [stratData, setStratData] = useState<StrategyPortfolio | null>(null);
  const [attribution, setAttribution] = useState<AttributionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"overview" | "strategies" | "trades" | "risk">("overview");

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [analyticsRes, tradesRes, stratRes, attrRes] = await Promise.all([
        api.get("/trading/portfolio/analytics"),
        api.get("/trading/trades?limit=50"),
        api.get("/trading/portfolio/strategies").catch(() => ({ data: null })),
        api.get("/trading/portfolio/attribution").catch(() => ({ data: null })),
      ]);
      setData(analyticsRes.data);
      setTrades(tradesRes.data);
      setStratData(stratRes.data);
      setAttribution(attrRes.data);
    } catch {
      // handle error
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="text-center py-20 text-gray-500">Loading portfolio...</div>;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Portfolio Analytics</h2>

      {/* Summary Cards */}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <SummaryCard label="Portfolio Value" value={formatKRW(data.portfolio_value)} />
          <SummaryCard label="Total Invested" value={formatKRW(data.total_invested)} />
          <SummaryCard
            label="Total P&L"
            value={`${formatKRW(data.total_pnl)} (${formatPct(data.total_pnl_pct)})`}
            color={metricColor(data.total_pnl)}
          />
          <SummaryCard label="Positions" value={String(data.position_count)} />
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 mb-4">
        {(["overview", "strategies", "trades", "risk"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab
                ? "bg-blue-600 text-white"
                : "bg-gray-800 text-gray-400 hover:text-white"
            }`}
          >
            {tab === "overview" ? "Overview" : tab === "strategies" ? "By Strategy" : tab === "trades" ? "Trade History" : "Risk Analysis"}
          </button>
        ))}
      </div>

      {activeTab === "overview" && data && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Allocation */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h3 className="text-lg font-semibold mb-4">Allocation</h3>
            {data.allocation.length > 0 ? (
              <div className="space-y-3">
                {data.allocation.map((a) => (
                  <div key={a.stock_code}>
                    <div className="flex items-center justify-between mb-1">
                      <div>
                        <span className="text-sm font-medium text-gray-300">{a.stock_code}</span>
                        {a.stock_name && (
                          <span className="text-xs text-gray-500 ml-2">{a.stock_name}</span>
                        )}
                      </div>
                      <div className="text-right">
                        <span className="text-sm text-gray-300">{formatKRW(a.value)}</span>
                        <span className={`text-xs ml-2 ${metricColor(a.pnl_pct)}`}>
                          {formatPct(a.pnl_pct)}
                        </span>
                      </div>
                    </div>
                    <div className="w-full bg-gray-800 rounded-full h-2">
                      <div
                        className="bg-blue-500 h-2 rounded-full"
                        style={{ width: `${Math.min(a.weight, 100)}%` }}
                      />
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      {a.quantity}주 · {a.weight.toFixed(1)}%
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-600">No positions.</p>
            )}
          </div>

          {/* Trade Stats */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h3 className="text-lg font-semibold mb-4">Trade Statistics</h3>
            <div className="grid grid-cols-2 gap-3">
              <StatItem label="Total Trades" value={String(data.trade_stats.total_trades)} />
              <StatItem label="Win Rate" value={`${data.trade_stats.win_rate}%`} color={metricColor(data.trade_stats.win_rate - 50)} />
              <StatItem label="Avg Win" value={formatKRW(data.trade_stats.avg_win)} color="text-green-400" />
              <StatItem label="Avg Loss" value={formatKRW(data.trade_stats.avg_loss)} color="text-red-400" />
              <StatItem label="Profit Factor" value={data.trade_stats.profit_factor.toFixed(2)} color={metricColor(data.trade_stats.profit_factor - 1)} />
              <StatItem label="W/L" value={`${data.trade_stats.winning_trades} / ${data.trade_stats.losing_trades}`} />
            </div>

            {/* P&L Breakdown */}
            <div className="mt-6 pt-4 border-t border-gray-800">
              <h4 className="text-sm text-gray-400 mb-3">P&L Breakdown</h4>
              <div className="space-y-2">
                <PnlRow label="Unrealized" value={data.unrealized_pnl} />
                <PnlRow label="Realized" value={data.realized_pnl} />
                <div className="border-t border-gray-700 pt-2">
                  <PnlRow label="Total" value={data.total_pnl} bold />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === "strategies" && (
        <div className="space-y-6">
          {/* Exposure Summary */}
          {stratData && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <SummaryCard label="Total Exposure" value={formatKRW(stratData.total_exposure)} />
              <SummaryCard label="Net Exposure" value={formatKRW(stratData.net_exposure)} />
              <SummaryCard label="Long" value={formatKRW(stratData.long_exposure)} color="text-green-400" />
              <SummaryCard label="HHI" value={String(stratData.hhi)} color={stratData.hhi > 2500 ? "text-red-400" : "text-green-400"} />
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Strategy Exposures */}
            {stratData && Object.keys(stratData.strategy_exposures).length > 0 && (
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                <h3 className="text-lg font-semibold mb-4">Strategy Exposures</h3>
                <div className="space-y-3">
                  {Object.entries(stratData.strategy_exposures).map(([id, s]) => (
                    <div key={id} className="flex items-center justify-between py-2 border-b border-gray-800/50">
                      <span className="text-sm text-gray-300">{s.name}</span>
                      <span className="text-sm font-mono text-gray-200">{formatKRW(s.value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Attribution */}
            {attribution && attribution.by_strategy.length > 0 && (
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                <h3 className="text-lg font-semibold mb-4">P&L Attribution</h3>
                <div className="space-y-3">
                  {attribution.by_strategy.map((s) => (
                    <div key={s.key} className="py-2 border-b border-gray-800/50">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-300">{s.name}</span>
                        <span className={`text-sm font-mono ${metricColor(s.pnl)}`}>
                          {formatKRW(s.pnl)} ({formatPct(s.pnl_pct)})
                        </span>
                      </div>
                      <div className="flex gap-3 mt-1">
                        <span className="text-xs text-gray-500">{s.trade_count} trades</span>
                        <span className="text-xs text-green-500">{s.win_count}W</span>
                        <span className="text-xs text-red-500">{s.loss_count}L</span>
                        <span className="text-xs text-gray-500">avg {formatKRW(s.avg_pnl_per_trade)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Warnings & Conflicts */}
          {stratData && stratData.warnings.length > 0 && (
            <div className="bg-yellow-900/20 border border-yellow-700/30 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-yellow-400 mb-2">Warnings</h3>
              <ul className="space-y-1">
                {stratData.warnings.map((w, i) => (
                  <li key={i} className="text-sm text-yellow-300/80">{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {activeTab === "risk" && <RiskTab />}

      {activeTab === "trades" && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
          {trades.length > 0 ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400">
                  <th className="text-left p-4">Stock</th>
                  <th className="text-center p-4">Side</th>
                  <th className="text-right p-4">Qty</th>
                  <th className="text-right p-4">Entry</th>
                  <th className="text-right p-4">Exit</th>
                  <th className="text-right p-4">P&L</th>
                  <th className="text-right p-4">P&L %</th>
                  <th className="text-right p-4">Date</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => (
                  <tr key={t.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="p-4 text-gray-300">{t.stock_code}</td>
                    <td className="p-4 text-center">
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        t.side === "buy" ? "bg-green-900/30 text-green-400" : "bg-red-900/30 text-red-400"
                      }`}>
                        {t.side.toUpperCase()}
                      </span>
                    </td>
                    <td className="p-4 text-right text-gray-400">{t.quantity}</td>
                    <td className="p-4 text-right font-mono text-gray-300">
                      {t.entry_price?.toLocaleString()}
                    </td>
                    <td className="p-4 text-right font-mono text-gray-300">
                      {t.exit_price?.toLocaleString() || "-"}
                    </td>
                    <td className={`p-4 text-right font-mono ${metricColor(t.pnl)}`}>
                      {t.pnl != null ? formatKRW(t.pnl) : "-"}
                    </td>
                    <td className={`p-4 text-right font-mono ${metricColor(t.pnl_percent)}`}>
                      {t.pnl_percent != null ? formatPct(t.pnl_percent) : "-"}
                    </td>
                    <td className="p-4 text-right text-gray-500 text-xs">
                      {t.entry_at ? new Date(t.entry_at).toLocaleDateString() : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-12 text-center text-gray-600">No trade history yet.</div>
          )}
        </div>
      )}
    </div>
  );
}

function SummaryCard({ label, value, color = "text-white" }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-xl font-bold ${color}`}>{value}</p>
    </div>
  );
}

function StatItem({ label, value, color = "text-gray-300" }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-gray-800 rounded-lg p-3">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-lg font-semibold mt-1 ${color}`}>{value}</p>
    </div>
  );
}

function PnlRow({ label, value, bold = false }: { label: string; value: number; bold?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className={`text-sm ${bold ? "text-gray-200 font-medium" : "text-gray-400"}`}>{label}</span>
      <span className={`font-mono ${bold ? "text-base font-bold" : "text-sm"} ${metricColor(value)}`}>
        {formatKRW(value)}
      </span>
    </div>
  );
}

function RiskTab() {
  const [riskData, setRiskData] = useState<{
    portfolio_value: number;
    confidence: number;
    horizon_days: number;
    var: Record<string, { var: number; var_pct: number; cvar: number; cvar_pct: number }>;
    stress_tests: { scenario: string; description: string; impact: number; impact_pct: number }[];
    message?: string;
  } | null>(null);
  const [riskLoading, setRiskLoading] = useState(true);

  useEffect(() => {
    api
      .get("/trading/portfolio/risk?confidence=0.95&horizon_days=1")
      .then(({ data }) => setRiskData(data))
      .catch(() => {})
      .finally(() => setRiskLoading(false));
  }, []);

  if (riskLoading) return <div className="text-center py-12 text-gray-500">Loading risk data...</div>;

  if (!riskData || riskData.message) {
    return (
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-12 text-center">
        <p className="text-gray-500">{riskData?.message || "No risk data available."}</p>
        <p className="text-sm text-gray-600 mt-2">Open positions are required for risk analysis.</p>
        <a href="/dashboard/risk" className="inline-block mt-4 text-sm text-blue-400 hover:text-blue-300">
          Go to full Risk Analysis page &rarr;
        </a>
      </div>
    );
  }

  const methods = ["historical", "parametric", "monte_carlo"] as const;
  const labels: Record<string, string> = { historical: "Historical", parametric: "Parametric", monte_carlo: "Monte Carlo" };

  return (
    <div className="space-y-6">
      {/* VaR Summary */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Value at Risk (95%, 1-Day)</h3>
          <a href="/dashboard/risk" className="text-sm text-blue-400 hover:text-blue-300">
            Full Analysis &rarr;
          </a>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {methods.map((m) => {
            const d = riskData.var[m];
            if (!d) return null;
            return (
              <div key={m} className="bg-gray-800 rounded-lg p-4">
                <p className="text-xs text-gray-500 mb-1">{labels[m]}</p>
                <p className="text-lg font-bold text-red-400">{formatKRW(d.var)}</p>
                <p className="text-xs text-gray-500">CVaR: {formatKRW(d.cvar)}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Stress Tests Summary */}
      {riskData.stress_tests.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="text-lg font-semibold mb-4">Stress Test Scenarios</h3>
          <div className="space-y-2">
            {riskData.stress_tests.map((s) => (
              <div key={s.scenario} className="flex items-center justify-between py-2 border-b border-gray-800/50">
                <div>
                  <span className="text-sm text-gray-300 capitalize">{s.scenario.replace(/_/g, " ")}</span>
                  <p className="text-xs text-gray-500">{s.description}</p>
                </div>
                <span className="text-sm font-mono text-red-400">
                  {formatKRW(s.impact)} ({formatPct(s.impact_pct)})
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
