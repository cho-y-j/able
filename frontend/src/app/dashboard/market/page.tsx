"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import api from "@/lib/api";

interface OHLCVItem {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export default function MarketPage() {
  const [stockCode, setStockCode] = useState("");
  const [priceData, setPriceData] = useState<Record<string, unknown> | null>(null);
  const [ohlcvData, setOhlcvData] = useState<OHLCVItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [period, setPeriod] = useState("1y");
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<unknown>(null);

  const fetchPrice = async () => {
    if (!stockCode.trim()) return;
    setLoading(true);
    try {
      const [priceRes, ohlcvRes] = await Promise.all([
        api.get(`/market/price/${stockCode.trim()}`),
        api.get(`/market/ohlcv/${stockCode.trim()}?period=${period}`),
      ]);
      setPriceData(priceRes.data);
      setOhlcvData(ohlcvRes.data.data || []);
    } catch {
      setPriceData(null);
      setOhlcvData([]);
    } finally {
      setLoading(false);
    }
  };

  const renderChart = useCallback(async () => {
    if (!chartContainerRef.current || ohlcvData.length === 0) return;

    try {
      const { createChart, CandlestickSeries, HistogramSeries } = await import("lightweight-charts");

      // Remove old chart
      chartContainerRef.current.innerHTML = "";

      const chart = createChart(chartContainerRef.current, {
        width: chartContainerRef.current.clientWidth,
        height: 400,
        layout: {
          background: { color: "#111827" },
          textColor: "#9CA3AF",
        },
        grid: {
          vertLines: { color: "#1F2937" },
          horzLines: { color: "#1F2937" },
        },
        crosshair: {
          mode: 0,
        },
        timeScale: {
          borderColor: "#374151",
        },
      });

      const candlestickSeries = chart.addSeries(CandlestickSeries, {
        upColor: "#10B981",
        downColor: "#EF4444",
        borderDownColor: "#EF4444",
        borderUpColor: "#10B981",
        wickDownColor: "#EF4444",
        wickUpColor: "#10B981",
      });

      const volumeSeries = chart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      });

      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });

      const candleData = ohlcvData.map((d) => ({
        time: d.date.replace(/(\d{4})(\d{2})(\d{2})/, "$1-$2-$3"),
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
      }));

      const volumeData = ohlcvData.map((d) => ({
        time: d.date.replace(/(\d{4})(\d{2})(\d{2})/, "$1-$2-$3"),
        value: d.volume,
        color: d.close >= d.open ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)",
      }));

      candlestickSeries.setData(candleData as Parameters<typeof candlestickSeries.setData>[0]);
      volumeSeries.setData(volumeData as Parameters<typeof volumeSeries.setData>[0]);

      chart.timeScale().fitContent();
      chartRef.current = chart;

      const handleResize = () => {
        if (chartContainerRef.current) {
          chart.applyOptions({ width: chartContainerRef.current.clientWidth });
        }
      };
      window.addEventListener("resize", handleResize);
      return () => window.removeEventListener("resize", handleResize);
    } catch {
      // lightweight-charts not available
    }
  }, [ohlcvData]);

  useEffect(() => {
    renderChart();
  }, [renderChart]);

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Market Analysis</h2>

      {/* Stock Search */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <h3 className="text-lg font-semibold mb-4">Stock Lookup</h3>
        <div className="flex gap-3">
          <input
            type="text"
            value={stockCode}
            onChange={(e) => setStockCode(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && fetchPrice()}
            placeholder="Stock code (e.g., 005930)"
            className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
          />
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="px-3 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm"
          >
            <option value="1m">1M</option>
            <option value="3m">3M</option>
            <option value="6m">6M</option>
            <option value="1y">1Y</option>
            <option value="2y">2Y</option>
          </select>
          <button onClick={fetchPrice} disabled={loading}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 rounded-lg text-sm font-medium transition-colors">
            {loading ? "Loading..." : "Lookup"}
          </button>
        </div>
      </div>

      {/* Price Display */}
      {priceData && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold">
              {String(priceData.stock_code)}
            </h3>
            <span className={`text-2xl font-bold ${
              Number(priceData.change) >= 0 ? "text-green-400" : "text-red-400"
            }`}>
              ₩{Number(priceData.current_price).toLocaleString()}
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <PriceItem label="Change" value={String(priceData.change)} color={Number(priceData.change) >= 0} />
            <PriceItem label="Change %" value={`${priceData.change_percent}%`} color={Number(priceData.change_percent) >= 0} />
            <PriceItem label="Volume" value={Number(priceData.volume).toLocaleString()} />
            <PriceItem label="High" value={Number(priceData.high || 0).toLocaleString()} />
            <PriceItem label="Low" value={Number(priceData.low || 0).toLocaleString()} />
          </div>
          {typeof priceData.message === "string" && (
            <p className="text-sm text-yellow-400 mt-4">{priceData.message}</p>
          )}
        </div>
      )}

      {/* Chart */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <h3 className="text-lg font-semibold mb-4">
          Chart {ohlcvData.length > 0 && `(${ohlcvData.length} candles)`}
        </h3>
        <div ref={chartContainerRef} className="w-full" style={{ minHeight: 400 }}>
          {ohlcvData.length === 0 && (
            <div className="h-96 flex items-center justify-center border border-gray-800 rounded-lg">
              <p className="text-gray-600">
                Search a stock above to load chart data.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PriceItem({ label, value, color }: { label: string; value: string; color?: boolean }) {
  const colorClass = color === undefined ? "" : color ? "text-green-400" : "text-red-400";
  return (
    <div className="bg-gray-800 rounded-lg p-3">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-lg font-semibold mt-1 ${colorClass}`}>{value}</p>
    </div>
  );
}
