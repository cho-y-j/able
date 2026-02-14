"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useTradingStore, type Position, type Order } from "@/store/trading";
import { useAuthStore } from "@/store/auth";
import { createWSConnection } from "@/lib/ws";
import { CHART_COLORS, DEFAULT_CHART_OPTIONS, formatKRW, formatPct } from "@/lib/charts";
import api from "@/lib/api";
import { useI18n } from "@/i18n";

export default function TradingPage() {
  const { t } = useI18n();
  const {
    positions, orders, portfolioStats,
    fetchPositions, fetchOrders, fetchPortfolioStats,
    selectedStock, setSelectedStock, updatePositionPrice,
  } = useTradingStore();
  const token = useAuthStore((s) => s.token);
  const [activeTab, setActiveTab] = useState<"positions" | "orders">("positions");
  const [orderFilter, setOrderFilter] = useState<string>("all");

  useEffect(() => {
    fetchPositions();
    fetchOrders();
    fetchPortfolioStats();
  }, [fetchPositions, fetchOrders, fetchPortfolioStats]);

  // WebSocket for real-time updates
  useEffect(() => {
    if (!token) return;

    const ws = createWSConnection("trading");
    ws.connect(token);

    const unsubOrder = ws.on("order_update", () => {
      fetchOrders();
      fetchPositions();
    });

    const unsubPrice = ws.on("price_update", (data: unknown) => {
      const d = data as { stock_code: string; price: number };
      if (d.stock_code && d.price) {
        updatePositionPrice(d.stock_code, d.price);
      }
    });

    return () => {
      unsubOrder();
      unsubPrice();
      ws.disconnect();
    };
  }, [token, fetchOrders, fetchPositions, updatePositionPrice]);

  // Auto-select first position's stock for chart
  useEffect(() => {
    if (!selectedStock && positions.length > 0) {
      setSelectedStock(positions[0].stock_code);
    }
  }, [positions, selectedStock, setSelectedStock]);

  const totalUnrealized = positions.reduce((s, p) => s + (p.unrealized_pnl || 0), 0);
  const totalValue = positions.reduce((s, p) => s + (p.current_price || p.avg_cost_price) * p.quantity, 0);
  const activeOrders = orders.filter((o) => o.status === "submitted" || o.status === "pending");
  const filteredOrders = orderFilter === "all" ? orders : orders.filter((o) => o.status === orderFilter);

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <h2 className="text-xl sm:text-2xl font-bold">{t.trading.title}</h2>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span className="inline-block w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          Live
          <button
            onClick={() => { fetchPositions(); fetchOrders(); fetchPortfolioStats(); }}
            className="ml-2 px-3 py-1 bg-gray-800 hover:bg-gray-700 rounded text-gray-300 transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <StatCard
          label={t.portfolio.portfolioValue}
          value={formatKRW(totalValue)}
        />
        <StatCard
          label={t.portfolio.unrealized}
          value={formatKRW(totalUnrealized)}
          color={totalUnrealized >= 0 ? "green" : "red"}
          sub={portfolioStats ? formatPct(portfolioStats.total_pnl_pct) : undefined}
        />
        <StatCard
          label={t.portfolio.positionCount}
          value={String(positions.length)}
          sub={activeOrders.length > 0 ? `${activeOrders.length} ${t.trading.openOrders}` : t.trading.noOrders}
        />
        <StatCard
          label={t.portfolio.winRate}
          value={portfolioStats ? `${portfolioStats.trade_stats.win_rate}%` : "--"}
          sub={portfolioStats ? `${portfolioStats.trade_stats.total_trades} trades` : undefined}
          color={portfolioStats && portfolioStats.trade_stats.win_rate >= 50 ? "green" : "neutral"}
        />
      </div>

      {/* Chart + Positions layout */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 sm:gap-6">
        {/* Chart section (takes 2/3 on XL) */}
        <div className="xl:col-span-2">
          <StockChart stockCode={selectedStock} />
        </div>

        {/* Position list (takes 1/3 on XL) */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 sm:p-5 overflow-hidden">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
            {t.portfolio.positionCount} ({positions.length})
          </h3>
          {positions.length === 0 ? (
            <div className="text-center py-8 text-gray-600 text-sm">
              <p>No open positions</p>
              <p className="mt-1 text-xs">Start trading to see positions here</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[400px] overflow-y-auto">
              {positions.map((p) => (
                <PositionCard
                  key={p.id}
                  position={p}
                  isSelected={selectedStock === p.stock_code}
                  onSelect={() => setSelectedStock(p.stock_code)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Orders section */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 sm:p-6">
        {/* Tabs & Filter */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
          <div className="flex gap-1 bg-gray-800 rounded-lg p-1">
            <TabButton active={activeTab === "positions"} onClick={() => setActiveTab("positions")}>
              Positions
            </TabButton>
            <TabButton active={activeTab === "orders"} onClick={() => setActiveTab("orders")}>
              {t.trading.openOrders} ({orders.length})
            </TabButton>
          </div>
          {activeTab === "orders" && (
            <div className="flex gap-1 flex-wrap">
              {["all", "submitted", "filled", "cancelled", "failed"].map((f) => (
                <button
                  key={f}
                  onClick={() => setOrderFilter(f)}
                  className={`px-3 py-1 rounded text-xs transition-colors ${
                    orderFilter === f
                      ? "bg-blue-600 text-white"
                      : "bg-gray-800 text-gray-400 hover:text-white"
                  }`}
                >
                  {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>
          )}
        </div>

        {activeTab === "positions" ? (
          <PositionsTable positions={positions} onSelect={setSelectedStock} selectedStock={selectedStock} />
        ) : (
          <OrdersTable orders={filteredOrders} />
        )}
      </div>
    </div>
  );
}


// ─── Sub Components ──────────────────────────────────────────

function StatCard({ label, value, sub, color = "neutral" }: {
  label: string; value: string; sub?: string; color?: string;
}) {
  const textColor = color === "green" ? "text-green-400"
    : color === "red" ? "text-red-400"
    : "text-white";
  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p className={`text-lg sm:text-xl font-bold mt-1 ${textColor}`}>{value}</p>
      {sub && <p className="text-xs text-gray-600 mt-0.5">{sub}</p>}
    </div>
  );
}

function TabButton({ active, onClick, children }: {
  active: boolean; onClick: () => void; children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
        active ? "bg-gray-700 text-white" : "text-gray-400 hover:text-white"
      }`}
    >
      {children}
    </button>
  );
}

function PositionCard({ position: p, isSelected, onSelect }: {
  position: Position; isSelected: boolean; onSelect: () => void;
}) {
  const pnlPct = p.current_price && p.avg_cost_price
    ? ((p.current_price - p.avg_cost_price) / p.avg_cost_price * 100) : 0;
  const pnlColor = (p.unrealized_pnl || 0) >= 0 ? "text-green-400" : "text-red-400";
  const barWidth = Math.min(Math.abs(pnlPct), 20) / 20 * 100;
  const barColor = pnlPct >= 0 ? "bg-green-500/30" : "bg-red-500/30";

  return (
    <button
      onClick={onSelect}
      className={`w-full text-left p-3 rounded-lg transition-all relative overflow-hidden ${
        isSelected
          ? "bg-blue-600/10 border border-blue-500/30"
          : "bg-gray-800/50 border border-transparent hover:border-gray-700"
      }`}
    >
      {/* P&L bar background */}
      <div
        className={`absolute inset-y-0 left-0 ${barColor} transition-all`}
        style={{ width: `${barWidth}%` }}
      />
      <div className="relative flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">{p.stock_name || p.stock_code}</p>
          <p className="text-xs text-gray-500">{p.stock_code} &middot; {p.quantity}주</p>
        </div>
        <div className="text-right">
          <p className={`text-sm font-semibold ${pnlColor}`}>
            {formatPct(pnlPct)}
          </p>
          <p className={`text-xs ${pnlColor}`}>
            {p.unrealized_pnl != null ? formatKRW(p.unrealized_pnl) : "--"}
          </p>
        </div>
      </div>
    </button>
  );
}

function StockChart({ stockCode }: { stockCode: string | null }) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const renderChart = useCallback(async () => {
    if (!chartContainerRef.current || !stockCode) return;

    setLoading(true);
    setError(null);

    try {
      const { data } = await api.get(`/market/ohlcv/${stockCode}?period=3m`);
      const ohlcv = data.data || [];

      if (ohlcv.length === 0) {
        setError("No chart data available");
        setLoading(false);
        return;
      }

      const { createChart, CandlestickSeries, HistogramSeries } = await import("lightweight-charts");

      chartContainerRef.current.innerHTML = "";

      const chart = createChart(chartContainerRef.current, {
        width: chartContainerRef.current.clientWidth,
        height: 320,
        ...DEFAULT_CHART_OPTIONS,
      });

      const candleSeries = chart.addSeries(CandlestickSeries, {
        upColor: CHART_COLORS.up,
        downColor: CHART_COLORS.down,
        borderDownColor: CHART_COLORS.down,
        borderUpColor: CHART_COLORS.up,
        wickDownColor: CHART_COLORS.down,
        wickUpColor: CHART_COLORS.up,
      });

      const volumeSeries = chart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      });

      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.82, bottom: 0 },
      });

      const candleData = ohlcv.map((d: { date: string; open: number; high: number; low: number; close: number }) => ({
        time: d.date.replace(/(\d{4})(\d{2})(\d{2})/, "$1-$2-$3"),
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
      }));

      const volumeData = ohlcv.map((d: { date: string; open: number; close: number; volume: number }) => ({
        time: d.date.replace(/(\d{4})(\d{2})(\d{2})/, "$1-$2-$3"),
        value: d.volume,
        color: d.close >= d.open ? CHART_COLORS.upAlpha : CHART_COLORS.downAlpha,
      }));

      candleSeries.setData(candleData as Parameters<typeof candleSeries.setData>[0]);
      volumeSeries.setData(volumeData as Parameters<typeof volumeSeries.setData>[0]);
      chart.timeScale().fitContent();
      chartRef.current = chart;

      const handleResize = () => {
        if (chartContainerRef.current) {
          chart.applyOptions({ width: chartContainerRef.current.clientWidth });
        }
      };
      window.addEventListener("resize", handleResize);
      setLoading(false);
      return () => window.removeEventListener("resize", handleResize);
    } catch {
      setError("Failed to load chart");
      setLoading(false);
    }
  }, [stockCode]);

  useEffect(() => {
    renderChart();
  }, [renderChart]);

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 sm:p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide">
          {stockCode ? `Chart — ${stockCode}` : "Chart"}
        </h3>
        {stockCode && (
          <span className="text-xs text-gray-600">3M</span>
        )}
      </div>
      <div ref={chartContainerRef} className="w-full rounded-lg overflow-hidden" style={{ minHeight: 320 }}>
        {!stockCode && (
          <div className="h-80 flex items-center justify-center border border-gray-800 rounded-lg">
            <p className="text-gray-600 text-sm">Select a position to view chart</p>
          </div>
        )}
        {loading && (
          <div className="h-80 flex items-center justify-center">
            <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        )}
        {error && (
          <div className="h-80 flex items-center justify-center border border-gray-800 rounded-lg">
            <p className="text-gray-600 text-sm">{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function PositionsTable({ positions, onSelect, selectedStock }: {
  positions: Position[]; onSelect: (code: string) => void; selectedStock: string | null;
}) {
  if (positions.length === 0) {
    return <p className="text-gray-600 text-sm py-4">No open positions</p>;
  }

  return (
    <div className="overflow-x-auto -mx-4 sm:-mx-6">
      <table className="w-full text-sm min-w-[600px]">
        <thead>
          <tr className="text-gray-500 text-xs uppercase border-b border-gray-800">
            <th className="text-left py-2 px-4 sm:px-6">Stock</th>
            <th className="text-right py-2 px-2">Qty</th>
            <th className="text-right py-2 px-2">Avg Cost</th>
            <th className="text-right py-2 px-2">Current</th>
            <th className="text-right py-2 px-2">P&L</th>
            <th className="text-right py-2 px-4 sm:px-6">P&L %</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => {
            const pnlPct = p.current_price && p.avg_cost_price
              ? ((p.current_price - p.avg_cost_price) / p.avg_cost_price * 100) : 0;
            const pnlColor = (p.unrealized_pnl || 0) >= 0 ? "text-green-400" : "text-red-400";
            return (
              <tr
                key={p.id}
                onClick={() => onSelect(p.stock_code)}
                className={`border-b border-gray-800/50 cursor-pointer transition-colors ${
                  selectedStock === p.stock_code ? "bg-blue-600/5" : "hover:bg-gray-800/50"
                }`}
              >
                <td className="py-3 px-4 sm:px-6">
                  <p className="font-medium">{p.stock_name || p.stock_code}</p>
                  <p className="text-xs text-gray-600">{p.stock_code}</p>
                </td>
                <td className="text-right px-2">{p.quantity.toLocaleString()}</td>
                <td className="text-right px-2 text-gray-400">₩{p.avg_cost_price.toLocaleString()}</td>
                <td className="text-right px-2 font-medium">
                  {p.current_price ? `₩${p.current_price.toLocaleString()}` : "--"}
                </td>
                <td className={`text-right px-2 ${pnlColor}`}>
                  {p.unrealized_pnl != null ? formatKRW(p.unrealized_pnl) : "--"}
                </td>
                <td className={`text-right px-4 sm:px-6 font-semibold ${pnlColor}`}>
                  {formatPct(pnlPct)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function OrdersTable({ orders }: { orders: Order[] }) {
  if (orders.length === 0) {
    return <p className="text-gray-600 text-sm py-4">No orders</p>;
  }

  return (
    <div className="overflow-x-auto -mx-4 sm:-mx-6">
      <table className="w-full text-sm min-w-[700px]">
        <thead>
          <tr className="text-gray-500 text-xs uppercase border-b border-gray-800">
            <th className="text-left py-2 px-4 sm:px-6">Time</th>
            <th className="text-left py-2 px-2">Stock</th>
            <th className="text-left py-2 px-2">Side</th>
            <th className="text-right py-2 px-2">Qty</th>
            <th className="text-right py-2 px-2">Price</th>
            <th className="text-right py-2 px-2">Filled</th>
            <th className="text-left py-2 px-4 sm:px-6">Status</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
              <td className="py-3 px-4 sm:px-6 text-gray-500 text-xs whitespace-nowrap">
                {new Date(o.created_at).toLocaleString("ko-KR", {
                  month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                })}
              </td>
              <td className="px-2 font-medium">{o.stock_name || o.stock_code}</td>
              <td className="px-2">
                <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
                  o.side === "buy"
                    ? "bg-green-900/40 text-green-400"
                    : "bg-red-900/40 text-red-400"
                }`}>
                  {o.side.toUpperCase()}
                </span>
              </td>
              <td className="text-right px-2">{o.quantity.toLocaleString()}</td>
              <td className="text-right px-2 text-gray-400">
                {o.limit_price ? `₩${o.limit_price.toLocaleString()}` : "Market"}
              </td>
              <td className="text-right px-2">
                {o.filled_quantity > 0 ? (
                  <span className="text-green-400">
                    {o.filled_quantity}/{o.quantity}
                    {o.avg_fill_price && <span className="text-xs text-gray-500 ml-1">@₩{o.avg_fill_price.toLocaleString()}</span>}
                  </span>
                ) : (
                  <span className="text-gray-600">--</span>
                )}
              </td>
              <td className="px-4 sm:px-6">
                <OrderStatusBadge status={o.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OrderStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    filled: "bg-green-900/50 text-green-400 border-green-800",
    submitted: "bg-blue-900/50 text-blue-400 border-blue-800",
    pending: "bg-yellow-900/50 text-yellow-400 border-yellow-800",
    cancelled: "bg-gray-800 text-gray-500 border-gray-700",
    failed: "bg-red-900/50 text-red-400 border-red-800",
    rejected: "bg-red-900/50 text-red-400 border-red-800",
  };

  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded border ${
      styles[status] || "bg-gray-800 text-gray-400 border-gray-700"
    }`}>
      <span className={`w-1.5 h-1.5 rounded-full ${
        status === "filled" ? "bg-green-400" :
        status === "submitted" ? "bg-blue-400 animate-pulse" :
        status === "pending" ? "bg-yellow-400 animate-pulse" :
        "bg-gray-500"
      }`} />
      {status}
    </span>
  );
}
