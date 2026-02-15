"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import api from "@/lib/api";
import {
  CHART_COLORS,
  DEFAULT_CHART_OPTIONS,
  formatKRW,
  formatPct,
} from "@/lib/charts";

interface RiskConfigProps {
  recipeId: string | null;
  riskConfig: Record<string, number>;
  stockCodes: string[];
  onRiskChange: (config: Record<string, number>) => void;
}

interface TradeLogEntry {
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  pnl_percent: number;
  hold_days: number;
}

interface EquityCurvePoint {
  date: string;
  value: number;
}

interface BacktestResult {
  composite_score: number | null;
  grade: string | null;
  metrics: {
    total_return: number;
    annual_return: number;
    sharpe_ratio: number;
    max_drawdown: number;
    win_rate: number;
    total_trades: number;
    sortino_ratio?: number;
    profit_factor?: number;
    calmar_ratio?: number;
  };
  equity_curve: EquityCurvePoint[];
  trade_log: TradeLogEntry[];
}

type ResultTab = "metrics" | "equity" | "trades";

export default function RiskConfig({
  recipeId,
  riskConfig,
  stockCodes,
  onRiskChange,
}: RiskConfigProps) {
  const [backtesting, setBacktesting] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ResultTab>("metrics");

  const equityChartRef = useRef<HTMLDivElement>(null);

  const updateRisk = (key: string, value: number) => {
    onRiskChange({ ...riskConfig, [key]: value });
  };

  const runBacktest = async () => {
    if (!recipeId || stockCodes.length === 0) {
      setError("레시피를 먼저 저장하고 종목을 추가하세요");
      return;
    }

    setBacktesting(true);
    setError(null);
    setResult(null);

    try {
      const { data } = await api.post(`/recipes/${recipeId}/backtest`, {
        stock_code: stockCodes[0],
      });
      setResult(data);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "백테스트 실패";
      setError(msg);
    } finally {
      setBacktesting(false);
    }
  };

  // Equity curve chart rendering
  const renderEquityChart = useCallback(async () => {
    if (!equityChartRef.current || !result?.equity_curve?.length) return;

    try {
      const { createChart, BaselineSeries } = await import("lightweight-charts");

      equityChartRef.current.innerHTML = "";

      const chart = createChart(equityChartRef.current, {
        width: equityChartRef.current.clientWidth,
        height: 300,
        ...DEFAULT_CHART_OPTIONS,
      });

      const firstValue = result.equity_curve[0].value;
      const series = chart.addSeries(BaselineSeries, {
        baseValue: { type: "price" as const, price: firstValue },
        topLineColor: CHART_COLORS.up,
        topFillColor1: "rgba(16, 185, 129, 0.2)",
        topFillColor2: "rgba(16, 185, 129, 0.02)",
        bottomLineColor: CHART_COLORS.down,
        bottomFillColor1: "rgba(239, 68, 68, 0.02)",
        bottomFillColor2: "rgba(239, 68, 68, 0.2)",
      });

      const data = result.equity_curve.map((pt) => ({
        time: pt.date.split("T")[0].split(" ")[0],
        value: pt.value,
      }));

      series.setData(data as Parameters<typeof series.setData>[0]);
      chart.timeScale().fitContent();

      const handleResize = () => {
        if (equityChartRef.current) {
          chart.applyOptions({ width: equityChartRef.current.clientWidth });
        }
      };
      window.addEventListener("resize", handleResize);
      return () => {
        window.removeEventListener("resize", handleResize);
        chart.remove();
      };
    } catch {
      // chart library not available
    }
  }, [result]);

  useEffect(() => {
    if (activeTab === "equity" && result) {
      const cleanup = renderEquityChart();
      return () => {
        cleanup?.then((fn) => fn?.());
      };
    }
  }, [activeTab, result, renderEquityChart]);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-white mb-1">리스크 설정 + 백테스트</h3>
        <p className="text-gray-400 text-sm">리스크 관리 파라미터를 설정하고 백테스트로 검증하세요</p>
      </div>

      {/* Risk Parameters */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <label className="text-xs text-gray-400 block mb-2">손절 (%)</label>
          <input
            type="number"
            min={0.5}
            max={20}
            step={0.5}
            value={riskConfig.stop_loss ?? 3}
            onChange={(e) => updateRisk("stop_loss", Number(e.target.value))}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-red-400 text-lg font-mono"
          />
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <label className="text-xs text-gray-400 block mb-2">익절 (%)</label>
          <input
            type="number"
            min={0.5}
            max={50}
            step={0.5}
            value={riskConfig.take_profit ?? 5}
            onChange={(e) => updateRisk("take_profit", Number(e.target.value))}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-green-400 text-lg font-mono"
          />
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <label className="text-xs text-gray-400 block mb-2">포지션 크기 (% of 자산)</label>
          <input
            type="number"
            min={1}
            max={100}
            step={1}
            value={riskConfig.position_size ?? 10}
            onChange={(e) => updateRisk("position_size", Number(e.target.value))}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-blue-400 text-lg font-mono"
          />
        </div>
      </div>

      {/* Backtest Button */}
      <button
        onClick={runBacktest}
        disabled={backtesting || !recipeId}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white py-3 rounded-xl text-sm font-medium transition-colors"
      >
        {backtesting ? "백테스트 실행 중..." : "백테스트 실행"}
      </button>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          {/* Score Header */}
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-white font-semibold">백테스트 결과</h4>
            <div className="flex items-center gap-3">
              {result.composite_score != null && (
                <span className="text-2xl font-bold text-blue-400">
                  {result.composite_score.toFixed(1)}점
                </span>
              )}
              {result.grade && (
                <span className={`text-xl font-bold px-3 py-1 rounded-lg ${
                  result.grade.startsWith("A") ? "bg-green-500/20 text-green-400" :
                  result.grade.startsWith("B") ? "bg-blue-500/20 text-blue-400" :
                  result.grade.startsWith("C") ? "bg-yellow-500/20 text-yellow-400" :
                  "bg-red-500/20 text-red-400"
                }`}>
                  {result.grade}
                </span>
              )}
            </div>
          </div>

          {/* Result Tabs */}
          <div className="flex gap-2 mb-4">
            {(["metrics", "equity", "trades"] as ResultTab[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === tab
                    ? "bg-blue-600 text-white"
                    : "bg-gray-700 text-gray-400 hover:text-white"
                }`}
              >
                {tab === "metrics" ? "지표" : tab === "equity" ? "수익 곡선" : `거래 내역 (${result.trade_log?.length || 0})`}
              </button>
            ))}
          </div>

          {/* Metrics Tab */}
          {activeTab === "metrics" && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <MetricCard
                label="수익률"
                value={formatPct(result.metrics.total_return, 1)}
                color={result.metrics.total_return >= 0 ? "text-green-400" : "text-red-400"}
              />
              <MetricCard
                label="연수익률"
                value={formatPct(result.metrics.annual_return, 1)}
                color={result.metrics.annual_return >= 0 ? "text-green-400" : "text-red-400"}
              />
              <MetricCard label="샤프 비율" value={result.metrics.sharpe_ratio?.toFixed(2)} />
              <MetricCard label="MDD" value={`${result.metrics.max_drawdown?.toFixed(1)}%`} color="text-red-400" />
              <MetricCard label="승률" value={`${result.metrics.win_rate?.toFixed(1)}%`} />
              <MetricCard label="총 거래" value={`${result.metrics.total_trades}회`} />
              {result.metrics.sortino_ratio != null && (
                <MetricCard label="소르티노" value={result.metrics.sortino_ratio.toFixed(2)} />
              )}
              {result.metrics.profit_factor != null && (
                <MetricCard
                  label="수익 팩터"
                  value={result.metrics.profit_factor.toFixed(2)}
                  color={result.metrics.profit_factor >= 1 ? "text-green-400" : "text-red-400"}
                />
              )}
              {result.metrics.calmar_ratio != null && (
                <MetricCard label="칼마 비율" value={result.metrics.calmar_ratio.toFixed(2)} />
              )}
            </div>
          )}

          {/* Equity Curve Tab */}
          {activeTab === "equity" && (
            <div>
              {result.equity_curve?.length > 0 ? (
                <>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-4 text-sm">
                      <span className="text-gray-400">
                        시작: <span className="text-white font-mono">{formatKRW(result.equity_curve[0].value)}</span>
                      </span>
                      <span className="text-gray-400">
                        종료: <span className={`font-mono ${
                          result.equity_curve[result.equity_curve.length - 1].value >= result.equity_curve[0].value
                            ? "text-green-400" : "text-red-400"
                        }`}>
                          {formatKRW(result.equity_curve[result.equity_curve.length - 1].value)}
                        </span>
                      </span>
                    </div>
                  </div>
                  <div ref={equityChartRef} className="w-full rounded-lg overflow-hidden" style={{ minHeight: 300 }} />
                </>
              ) : (
                <p className="text-gray-500 text-center py-8">수익 곡선 데이터가 없습니다</p>
              )}
            </div>
          )}

          {/* Trade Log Tab */}
          {activeTab === "trades" && (
            <div>
              {result.trade_log?.length > 0 ? (
                <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-gray-800">
                      <tr className="border-b border-gray-700 text-gray-400">
                        <th className="text-left p-2.5">#</th>
                        <th className="text-left p-2.5">진입일</th>
                        <th className="text-left p-2.5">청산일</th>
                        <th className="text-right p-2.5">진입가</th>
                        <th className="text-right p-2.5">청산가</th>
                        <th className="text-right p-2.5">손익</th>
                        <th className="text-right p-2.5">보유일</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.trade_log.map((trade, i) => (
                        <tr key={i} className="border-b border-gray-700/50 hover:bg-gray-700/30">
                          <td className="p-2.5 text-gray-500">{i + 1}</td>
                          <td className="p-2.5 text-gray-300 text-xs">{trade.entry_date?.split("T")[0]?.split(" ")[0]}</td>
                          <td className="p-2.5 text-gray-300 text-xs">{trade.exit_date?.split("T")[0]?.split(" ")[0]}</td>
                          <td className="p-2.5 text-right font-mono text-gray-300">
                            {trade.entry_price?.toLocaleString()}
                          </td>
                          <td className="p-2.5 text-right font-mono text-gray-300">
                            {trade.exit_price?.toLocaleString()}
                          </td>
                          <td className={`p-2.5 text-right font-mono ${trade.pnl_percent >= 0 ? "text-green-400" : "text-red-400"}`}>
                            {formatPct(trade.pnl_percent)}
                          </td>
                          <td className="p-2.5 text-right text-gray-400">{trade.hold_days}일</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-gray-500 text-center py-8">거래 내역이 없습니다</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  color = "text-white",
}: {
  label: string;
  value: string | undefined;
  color?: string;
}) {
  return (
    <div className="bg-gray-900 rounded-lg p-3">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-lg font-bold font-mono ${color}`}>{value ?? "-"}</p>
    </div>
  );
}
