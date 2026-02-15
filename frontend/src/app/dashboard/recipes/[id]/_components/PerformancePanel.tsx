"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import api from "@/lib/api";
import {
  DEFAULT_CHART_OPTIONS,
  CHART_COLORS,
  formatKRW,
  formatPct,
  metricColor,
} from "@/lib/charts";

interface PerformanceData {
  total_trades: number;
  closed_trades: number;
  open_trades: number;
  win_rate: number | null;
  total_pnl: number;
  total_pnl_percent: number | null;
  avg_win: number | null;
  avg_loss: number | null;
  profit_factor: number | null;
  avg_slippage_bps: number | null;
  equity_curve: { date: string; value: number }[];
  trades: PerformanceTrade[];
  trades_total: number;
}

interface PerformanceTrade {
  id: string;
  stock_code: string;
  side: string;
  entry_price: number;
  exit_price: number | null;
  quantity: number;
  pnl: number | null;
  pnl_percent: number | null;
  entry_at: string;
  exit_at: string | null;
}

interface PerformancePanelProps {
  recipeId: string | null;
}

const PAGE_SIZE = 20;

export default function PerformancePanel({ recipeId }: PerformancePanelProps) {
  const [data, setData] = useState<PerformanceData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<any>(null);

  const fetchPerformance = useCallback(async () => {
    if (!recipeId) return;
    setLoading(true);
    setError(null);
    try {
      const { data: resp } = await api.get(`/recipes/${recipeId}/performance`);
      setData(resp);
    } catch {
      setError("성과 데이터를 불러오지 못했습니다");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [recipeId]);

  useEffect(() => {
    fetchPerformance();
  }, [fetchPerformance]);

  // Render equity curve chart
  const renderChart = useCallback(async () => {
    if (!chartRef.current || !data?.equity_curve?.length) return;

    const lc = await import("lightweight-charts");

    if (chartInstanceRef.current) {
      chartInstanceRef.current.remove();
      chartInstanceRef.current = null;
    }

    const chart = lc.createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 300,
      ...DEFAULT_CHART_OPTIONS,
    });
    chartInstanceRef.current = chart;

    const series = chart.addSeries(lc.BaselineSeries, {
      baseValue: { type: "price" as const, price: 0 },
      topLineColor: CHART_COLORS.up,
      bottomLineColor: CHART_COLORS.down,
      topFillColor1: CHART_COLORS.upAlpha,
      topFillColor2: "rgba(16,185,129,0)",
      bottomFillColor1: "rgba(239,68,68,0)",
      bottomFillColor2: CHART_COLORS.downAlpha,
    });

    series.setData(
      data.equity_curve.map((p) => ({
        time: p.date.split("T")[0],
        value: p.value,
      })) as any
    );

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver(() => {
      if (chartRef.current) {
        chart.applyOptions({ width: chartRef.current.clientWidth });
      }
    });
    resizeObserver.observe(chartRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartInstanceRef.current = null;
    };
  }, [data?.equity_curve]);

  useEffect(() => {
    const cleanup = renderChart();
    return () => {
      cleanup?.then((fn) => fn?.());
    };
  }, [renderChart]);

  // Pagination
  const pageTrades = useMemo(() => {
    if (!data?.trades) return [];
    return data.trades.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  }, [data?.trades, page]);

  const totalPages = data ? Math.max(1, Math.ceil(data.trades.length / PAGE_SIZE)) : 1;

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-20 bg-gray-800 rounded-xl" />
          ))}
        </div>
        <div className="h-[300px] bg-gray-800 rounded-xl" />
        <div className="h-48 bg-gray-800 rounded-xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
        <p className="text-red-400 text-sm">{error}</p>
      </div>
    );
  }

  if (!data || data.total_trades === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-semibold text-white mb-1">실거래 성과</h3>
          <p className="text-gray-400 text-sm">레시피의 실거래 성과를 확인하세요</p>
        </div>
        <div className="text-center py-12 bg-gray-800/50 rounded-xl border border-gray-700 border-dashed">
          <p className="text-gray-400 text-lg mb-2">
            아직 거래 성과 데이터가 없습니다
          </p>
          <p className="text-gray-500 text-sm">
            레시피를 실행하면 거래 결과가 여기에 표시됩니다
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-white mb-1">실거래 성과</h3>
        <p className="text-gray-400 text-sm">레시피의 실거래 성과를 확인하세요</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <p className="text-xs text-gray-400">총 손익</p>
          <p className={`text-xl font-bold mt-1 ${metricColor(data.total_pnl)}`}>
            {formatKRW(data.total_pnl)}
          </p>
          {data.total_pnl_percent != null && (
            <p className={`text-xs mt-0.5 ${metricColor(data.total_pnl_percent)}`}>
              {formatPct(data.total_pnl_percent)}
            </p>
          )}
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <p className="text-xs text-gray-400">승률</p>
          <p className="text-xl font-bold mt-1 text-white">
            {data.win_rate != null ? `${data.win_rate}%` : "-"}
          </p>
          <p className="text-xs text-gray-500 mt-0.5">
            {data.closed_trades}건 중 {data.win_rate != null ? Math.round(data.closed_trades * data.win_rate / 100) : 0}건 수익
          </p>
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <p className="text-xs text-gray-400">거래 수</p>
          <p className="text-xl font-bold mt-1 text-white">{data.total_trades}</p>
          <p className="text-xs text-gray-500 mt-0.5">
            완료 {data.closed_trades} / 진행 {data.open_trades}
          </p>
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <p className="text-xs text-gray-400">수익률 팩터</p>
          <p className={`text-xl font-bold mt-1 ${data.profit_factor != null && data.profit_factor >= 1 ? "text-green-400" : "text-gray-400"}`}>
            {data.profit_factor != null ? `${data.profit_factor}x` : "-"}
          </p>
          {data.avg_slippage_bps != null && (
            <p className="text-xs text-gray-500 mt-0.5">
              슬리피지 {data.avg_slippage_bps}bps
            </p>
          )}
        </div>
      </div>

      {/* Additional Stats */}
      {(data.avg_win != null || data.avg_loss != null) && (
        <div className="flex gap-6 text-sm">
          {data.avg_win != null && (
            <span className="text-green-400">평균 수익: {formatPct(data.avg_win)}</span>
          )}
          {data.avg_loss != null && (
            <span className="text-red-400">평균 손실: {formatPct(data.avg_loss)}</span>
          )}
        </div>
      )}

      {/* Equity Curve */}
      {data.equity_curve.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-400 mb-2">누적 손익</h4>
          <div ref={chartRef} className="w-full rounded-lg overflow-hidden" style={{ height: 300 }} />
        </div>
      )}

      {/* Trade History */}
      {data.trades.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-medium text-gray-400">거래 내역</h4>
            <span className="text-xs text-gray-500">
              총 {data.trades_total}건
            </span>
          </div>
          <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-gray-800">
                <tr className="border-b border-gray-700 text-gray-400">
                  <th className="text-left p-2.5">종목</th>
                  <th className="text-left p-2.5">방향</th>
                  <th className="text-right p-2.5">수량</th>
                  <th className="text-right p-2.5">진입가</th>
                  <th className="text-right p-2.5">청산가</th>
                  <th className="text-right p-2.5">손익</th>
                  <th className="text-center p-2.5">결과</th>
                  <th className="text-left p-2.5">진입일</th>
                </tr>
              </thead>
              <tbody>
                {pageTrades.map((trade) => (
                  <tr
                    key={trade.id}
                    className="border-b border-gray-700/50 hover:bg-gray-700/30"
                  >
                    <td className="p-2.5 text-white font-mono text-xs">
                      {trade.stock_code}
                    </td>
                    <td className="p-2.5">
                      <span
                        className={`text-xs font-medium ${trade.side === "buy" ? "text-green-400" : "text-red-400"}`}
                      >
                        {trade.side === "buy" ? "매수" : "매도"}
                      </span>
                    </td>
                    <td className="p-2.5 text-right font-mono text-gray-300">
                      {trade.quantity.toLocaleString()}
                    </td>
                    <td className="p-2.5 text-right font-mono text-gray-300">
                      {`₩${trade.entry_price.toLocaleString()}`}
                    </td>
                    <td className="p-2.5 text-right font-mono text-gray-300">
                      {trade.exit_price
                        ? `₩${trade.exit_price.toLocaleString()}`
                        : "-"}
                    </td>
                    <td className={`p-2.5 text-right font-mono text-xs ${metricColor(trade.pnl_percent)}`}>
                      {trade.pnl_percent != null
                        ? formatPct(trade.pnl_percent)
                        : "-"}
                    </td>
                    <td className="p-2.5 text-center">
                      {trade.pnl != null ? (
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                            trade.pnl > 0
                              ? "bg-green-500/20 text-green-400"
                              : "bg-red-500/20 text-red-400"
                          }`}
                        >
                          {trade.pnl > 0 ? "수익" : "손실"}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-500">진행중</span>
                      )}
                    </td>
                    <td className="p-2.5 text-gray-400 text-xs">
                      {trade.entry_at?.split("T")[0]}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-3">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-1.5 rounded text-xs bg-gray-800 text-gray-400 hover:text-white disabled:text-gray-600 transition-colors"
              >
                이전
              </button>
              <span className="px-3 py-1.5 text-xs text-gray-500">
                {page + 1} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="px-3 py-1.5 rounded text-xs bg-gray-800 text-gray-400 hover:text-white disabled:text-gray-600 transition-colors"
              >
                다음
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
