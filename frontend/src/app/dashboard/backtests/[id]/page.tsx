"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import {
  CHART_COLORS,
  DEFAULT_CHART_OPTIONS,
  formatKRW,
  formatPct,
  metricColor,
  scoreColor,
  gradeFromScore,
} from "@/lib/charts";

interface BacktestDetail {
  id: string;
  strategy_id: string;
  status: string;
  date_range_start: string;
  date_range_end: string;
  metrics: Record<string, number>;
  validation: Record<string, number>;
  equity_curve: number[] | null;
  trade_log: TradeEntry[] | null;
  error_message: string | null;
}

interface TradeEntry {
  entry_date: string;
  exit_date: string;
  side: string;
  entry_price: number;
  exit_price: number;
  pnl_percent: number;
  pnl: number;
}

interface MCResult {
  mc_score: number;
  simulations_run: number;
  statistics: Record<string, number>;
  drawdown_stats: Record<string, number>;
  percentiles: Record<string, number>;
  confidence_bands: Record<string, number[]>;
}

export default function BacktestDetailPage() {
  const params = useParams();
  const backtestId = params.id as string;

  const [bt, setBt] = useState<BacktestDetail | null>(null);
  const [mc, setMc] = useState<MCResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [mcLoading, setMcLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"equity" | "trades" | "monte-carlo">("equity");

  const equityChartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchBacktest();
  }, [backtestId]);

  const fetchBacktest = async () => {
    try {
      const { data } = await api.get(`/backtests/${backtestId}`);
      setBt(data);
    } catch {
      setBt(null);
    } finally {
      setLoading(false);
    }
  };

  const runMonteCarlo = async () => {
    if (!bt) return;
    setMcLoading(true);
    try {
      const { data } = await api.post(`/backtests/${backtestId}/monte-carlo`, {
        n_simulations: 1000,
      });
      setMc(data);
      setActiveTab("monte-carlo");
    } catch {
      // handle error
    } finally {
      setMcLoading(false);
    }
  };

  // Equity Curve Chart
  const renderEquityChart = useCallback(async () => {
    if (!equityChartRef.current || !bt?.equity_curve?.length) return;

    try {
      const { createChart, LineSeries, BaselineSeries } = await import("lightweight-charts");

      equityChartRef.current.innerHTML = "";

      const chart = createChart(equityChartRef.current, {
        width: equityChartRef.current.clientWidth,
        height: 400,
        ...DEFAULT_CHART_OPTIONS,
      });

      const series = chart.addSeries(BaselineSeries, {
        baseValue: { type: "price" as const, price: bt.equity_curve[0] },
        topLineColor: CHART_COLORS.up,
        topFillColor1: "rgba(16, 185, 129, 0.2)",
        topFillColor2: "rgba(16, 185, 129, 0.02)",
        bottomLineColor: CHART_COLORS.down,
        bottomFillColor1: "rgba(239, 68, 68, 0.02)",
        bottomFillColor2: "rgba(239, 68, 68, 0.2)",
      });

      const startDate = new Date(bt.date_range_start);
      const data = bt.equity_curve.map((value, i) => {
        const d = new Date(startDate);
        d.setDate(d.getDate() + i);
        return {
          time: d.toISOString().split("T")[0],
          value,
        };
      });

      series.setData(data as Parameters<typeof series.setData>[0]);
      chart.timeScale().fitContent();

      const handleResize = () => {
        if (equityChartRef.current) {
          chart.applyOptions({ width: equityChartRef.current.clientWidth });
        }
      };
      window.addEventListener("resize", handleResize);
      return () => window.removeEventListener("resize", handleResize);
    } catch {
      // chart not available
    }
  }, [bt]);

  useEffect(() => {
    if (activeTab === "equity") renderEquityChart();
  }, [activeTab, renderEquityChart]);

  if (loading) return <div className="text-center py-20 text-gray-500">Loading...</div>;
  if (!bt) return <div className="text-center py-20 text-red-400">Backtest not found</div>;

  const m = bt.metrics;
  const v = bt.validation;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <Link href="/dashboard/backtests" className="text-gray-400 hover:text-white text-sm">
          ← Backtests
        </Link>
        <h2 className="text-2xl font-bold">Backtest Detail</h2>
        <span className={`px-2 py-1 rounded text-xs font-medium ${
          bt.status === "completed" ? "bg-green-600/20 text-green-400" : "bg-gray-700 text-gray-400"
        }`}>
          {bt.status}
        </span>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 mb-6">
        <MetricCard label="Total Return" value={formatPct(m.total_return)} color={metricColor(m.total_return)} />
        <MetricCard label="Annual Return" value={formatPct(m.annual_return)} color={metricColor(m.annual_return)} />
        <MetricCard label="Sharpe Ratio" value={m.sharpe_ratio?.toFixed(2)} color={metricColor(m.sharpe_ratio)} />
        <MetricCard label="Sortino Ratio" value={m.sortino_ratio?.toFixed(2)} color={metricColor(m.sortino_ratio)} />
        <MetricCard label="Max Drawdown" value={formatPct(m.max_drawdown)} color="text-red-400" />
        <MetricCard label="Win Rate" value={`${m.win_rate?.toFixed(1)}%`} />
        <MetricCard label="Profit Factor" value={m.profit_factor?.toFixed(2)} color={metricColor((m.profit_factor || 0) - 1)} />
        <MetricCard label="Total Trades" value={String(m.total_trades || 0)} />
        <MetricCard label="Calmar Ratio" value={m.calmar_ratio?.toFixed(2)} color={metricColor(m.calmar_ratio)} />
        <MetricCard label="WFA Score" value={v.wfa_score?.toFixed(0)} color={scoreColor(v.wfa_score)} />
        <MetricCard label="MC Score" value={v.mc_score?.toFixed(0)} color={scoreColor(v.mc_score)} />
        <MetricCard label="OOS Score" value={v.oos_score?.toFixed(0)} color={scoreColor(v.oos_score)} />
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-4">
        {(["equity", "trades", "monte-carlo"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab
                ? "bg-blue-600 text-white"
                : "bg-gray-800 text-gray-400 hover:text-white"
            }`}
          >
            {tab === "equity" ? "Equity Curve" : tab === "trades" ? "Trade Log" : "Monte Carlo"}
          </button>
        ))}
        {!mc && (
          <button
            onClick={runMonteCarlo}
            disabled={mcLoading}
            className="ml-auto px-4 py-2 rounded-lg text-sm font-medium bg-purple-600/20 text-purple-400 hover:bg-purple-600/30 disabled:opacity-50"
          >
            {mcLoading ? "Running MC..." : "Run Monte Carlo"}
          </button>
        )}
      </div>

      {/* Tab Content */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        {activeTab === "equity" && (
          <div>
            <h3 className="text-lg font-semibold mb-4">Equity Curve</h3>
            <div ref={equityChartRef} className="w-full" style={{ minHeight: 400 }}>
              {!bt.equity_curve?.length && (
                <div className="h-96 flex items-center justify-center text-gray-600">
                  No equity curve data available.
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === "trades" && (
          <div>
            <h3 className="text-lg font-semibold mb-4">
              Trade Log ({bt.trade_log?.length || 0} trades)
            </h3>
            {bt.trade_log?.length ? (
              <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-gray-900">
                    <tr className="border-b border-gray-800 text-gray-400">
                      <th className="text-left p-3">#</th>
                      <th className="text-left p-3">Entry</th>
                      <th className="text-left p-3">Exit</th>
                      <th className="text-right p-3">Entry Price</th>
                      <th className="text-right p-3">Exit Price</th>
                      <th className="text-right p-3">P&L %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bt.trade_log.map((trade, i) => (
                      <tr key={i} className="border-b border-gray-800/50">
                        <td className="p-3 text-gray-500">{i + 1}</td>
                        <td className="p-3 text-gray-300">{trade.entry_date}</td>
                        <td className="p-3 text-gray-300">{trade.exit_date}</td>
                        <td className="p-3 text-right font-mono">
                          {trade.entry_price?.toLocaleString()}
                        </td>
                        <td className="p-3 text-right font-mono">
                          {trade.exit_price?.toLocaleString()}
                        </td>
                        <td className={`p-3 text-right font-mono ${trade.pnl_percent >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {formatPct(trade.pnl_percent)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-gray-600">No trades recorded.</p>
            )}
          </div>
        )}

        {activeTab === "monte-carlo" && (
          <div>
            <h3 className="text-lg font-semibold mb-4">Monte Carlo Simulation</h3>
            {mc ? (
              <div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
                  <MetricCard label="MC Score" value={mc.mc_score?.toFixed(1)} color={scoreColor(mc.mc_score)} />
                  <MetricCard label="Simulations" value={String(mc.simulations_run)} />
                  <MetricCard label="Mean Return" value={formatPct(mc.statistics.mean_return)} color={metricColor(mc.statistics.mean_return)} />
                  <MetricCard label="Median Return" value={formatPct(mc.statistics.median_return)} color={metricColor(mc.statistics.median_return)} />
                  <MetricCard label="Best Case" value={formatPct(mc.statistics.best_case)} color="text-green-400" />
                  <MetricCard label="Worst Case" value={formatPct(mc.statistics.worst_case)} color="text-red-400" />
                  <MetricCard label="Risk of Ruin" value={`${mc.statistics.risk_of_ruin_pct?.toFixed(1)}%`} color="text-red-400" />
                  <MetricCard label="Avg Max DD" value={formatPct(mc.drawdown_stats.mean_max_dd)} color="text-red-400" />
                </div>
                <div className="bg-gray-800 rounded-lg p-4">
                  <h4 className="text-sm text-gray-400 mb-3">Return Percentiles</h4>
                  <div className="flex gap-4 text-sm">
                    {Object.entries(mc.percentiles).map(([key, val]) => (
                      <div key={key} className="text-center">
                        <div className="text-gray-500 text-xs">{key.toUpperCase()}</div>
                        <div className={`font-mono ${val >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {formatPct(val)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-gray-600">
                Click &ldquo;Run Monte Carlo&rdquo; to simulate strategy robustness.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  color = "text-gray-300",
}: {
  label: string;
  value: string | undefined;
  color?: string;
}) {
  return (
    <div className="bg-gray-800 rounded-lg p-3">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-lg font-semibold mt-1 font-mono ${color}`}>{value ?? "-"}</p>
    </div>
  );
}
