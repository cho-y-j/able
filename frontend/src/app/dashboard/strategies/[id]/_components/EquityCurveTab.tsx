"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import {
  DEFAULT_CHART_OPTIONS,
  CHART_COLORS,
  formatKRW,
} from "@/lib/charts";

interface EquityCurveTabProps {
  equityCurve: { date: string; value: number }[] | null;
  dateRangeStart: string;
  dateRangeEnd: string;
  totalReturn: number;
}

type TimeRange = "1M" | "3M" | "6M" | "1Y" | "ALL";

function computeDrawdownSeries(
  curve: { date: string; value: number }[]
): { time: string; value: number }[] {
  let peak = -Infinity;
  return curve.map((p) => {
    const t = p.date.split(" ")[0].split("T")[0];
    if (p.value > peak) peak = p.value;
    const dd = peak > 0 ? ((p.value - peak) / peak) * 100 : 0;
    return { time: t, value: dd };
  });
}

function subtractMonths(dateStr: string, months: number): string {
  const d = new Date(dateStr);
  d.setMonth(d.getMonth() - months);
  return d.toISOString().split("T")[0];
}

export default function EquityCurveTab({
  equityCurve,
  dateRangeStart,
  dateRangeEnd,
  totalReturn,
}: EquityCurveTabProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<any>(null);
  const [range, setRange] = useState<TimeRange>("ALL");

  const renderChart = useCallback(async () => {
    if (!chartRef.current || !equityCurve || equityCurve.length === 0) return;

    const lc = await import("lightweight-charts");

    // Check if DOM element is still mounted (React StrictMode cleanup race)
    if (!chartRef.current) return;

    // Clean up previous chart
    if (chartInstanceRef.current) {
      try {
        chartInstanceRef.current.remove();
      } catch {
        // Chart may already be disposed
      }
      chartInstanceRef.current = null;
    }

    const chart = lc.createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 400,
      ...DEFAULT_CHART_OPTIONS,
    });
    chartInstanceRef.current = chart;

    // Equity curve series
    const equitySeries = chart.addSeries(lc.BaselineSeries, {
      baseValue: { type: "price" as const, price: 10_000_000 },
      topLineColor: CHART_COLORS.up,
      bottomLineColor: CHART_COLORS.down,
      topFillColor1: CHART_COLORS.upAlpha,
      topFillColor2: "rgba(16,185,129,0)",
      bottomFillColor1: "rgba(239,68,68,0)",
      bottomFillColor2: CHART_COLORS.downAlpha,
      priceScaleId: "left",
    });

    const chartData = equityCurve.map((p) => ({
      time: p.date.split(" ")[0].split("T")[0],
      value: p.value,
    }));
    equitySeries.setData(chartData as any);

    // Drawdown series
    const ddData = computeDrawdownSeries(equityCurve);
    const ddSeries = chart.addSeries(lc.AreaSeries, {
      topColor: "rgba(239,68,68,0.1)",
      bottomColor: "rgba(239,68,68,0.4)",
      lineColor: CHART_COLORS.down,
      lineWidth: 1,
      priceScaleId: "right",
    });
    ddSeries.setData(ddData as any);

    // Configure price scales
    chart.priceScale("left").applyOptions({
      borderColor: CHART_COLORS.border,
      scaleMargins: { top: 0.05, bottom: 0.35 },
    });
    chart.priceScale("right").applyOptions({
      borderColor: CHART_COLORS.border,
      scaleMargins: { top: 0.7, bottom: 0.02 },
    });

    chart.timeScale().fitContent();

    // Handle resize
    const resizeObserver = new ResizeObserver(() => {
      if (chartRef.current) {
        chart.applyOptions({ width: chartRef.current.clientWidth });
      }
    });
    resizeObserver.observe(chartRef.current);

    return () => {
      resizeObserver.disconnect();
      try {
        chart.remove();
      } catch {
        // Chart may already be disposed in StrictMode
      }
      chartInstanceRef.current = null;
    };
  }, [equityCurve]);

  useEffect(() => {
    let disposed = false;
    const cleanup = renderChart();
    return () => {
      disposed = true;
      cleanup?.then((fn) => {
        if (fn) {
          try { fn(); } catch { /* already disposed */ }
        }
      });
    };
  }, [renderChart]);

  // Apply time range
  useEffect(() => {
    if (!chartInstanceRef.current || !equityCurve || equityCurve.length === 0)
      return;

    const chart = chartInstanceRef.current;
    if (range === "ALL") {
      chart.timeScale().fitContent();
    } else {
      const endDate =
        equityCurve[equityCurve.length - 1].date.split(" ")[0].split("T")[0];
      const months =
        range === "1M" ? 1 : range === "3M" ? 3 : range === "6M" ? 6 : 12;
      const startDate = subtractMonths(endDate, months);
      chart.timeScale().setVisibleRange({
        from: startDate,
        to: endDate,
      });
    }
  }, [range, equityCurve]);

  // Summary calculations
  const startCapital = 10_000_000;
  const endCapital =
    equityCurve && equityCurve.length > 0
      ? Math.round(equityCurve[equityCurve.length - 1].value)
      : null;
  const peakCapital =
    equityCurve && equityCurve.length > 0
      ? Math.round(Math.max(...equityCurve.map((p) => p.value)))
      : null;

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">에쿼티 커브</h3>
        {equityCurve && equityCurve.length > 0 && (
          <div className="flex gap-1">
            {(["1M", "3M", "6M", "1Y", "ALL"] as TimeRange[]).map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                  range === r
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700"
                }`}
              >
                {r === "ALL" ? "전체" : r}
              </button>
            ))}
          </div>
        )}
      </div>

      {equityCurve && equityCurve.length > 0 ? (
        <>
          <div ref={chartRef} className="w-full" style={{ height: 400 }} />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4">
            <div className="text-center bg-gray-800/50 rounded-lg py-3">
              <div className="text-xs text-gray-500 mb-1">시작 자본</div>
              <div className="text-white font-bold text-sm">
                {formatKRW(startCapital)}
              </div>
            </div>
            <div className="text-center bg-gray-800/50 rounded-lg py-3">
              <div className="text-xs text-gray-500 mb-1">최종 자본</div>
              <div
                className={`font-bold text-sm ${totalReturn >= 0 ? "text-green-400" : "text-red-400"}`}
              >
                {endCapital !== null ? formatKRW(endCapital) : "N/A"}
              </div>
            </div>
            <div className="text-center bg-gray-800/50 rounded-lg py-3">
              <div className="text-xs text-gray-500 mb-1">최고 자본</div>
              <div className="text-white font-bold text-sm">
                {peakCapital !== null ? formatKRW(peakCapital) : "N/A"}
              </div>
            </div>
            <div className="text-center bg-gray-800/50 rounded-lg py-3">
              <div className="text-xs text-gray-500 mb-1">기간</div>
              <div className="text-white font-bold text-sm">
                {dateRangeStart} ~ {dateRangeEnd}
              </div>
            </div>
          </div>
        </>
      ) : (
        <p className="text-gray-500">에쿼티 커브 데이터가 없습니다.</p>
      )}
    </div>
  );
}
