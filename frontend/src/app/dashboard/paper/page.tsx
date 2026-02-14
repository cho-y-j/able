"use client";

import { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";

interface PaperSession {
  id: string;
  name: string;
  status: string;
  initial_cash: number;
  fill_model: string;
  created_at: string;
  ended_at: string | null;
}

interface PaperOrderItem {
  id: string;
  stock_code: string;
  stock_name: string;
  side: string;
  order_type: string;
  quantity: number;
  filled_quantity: number;
  avg_fill_price: number;
  status: string;
  slippage_bps: number;
  created_at: string;
  filled_at: string | null;
}

interface PaperPositionItem {
  stock_code: string;
  stock_name: string;
  quantity: number;
  avg_cost_price: number;
  current_price: number;
  unrealized_pnl: number;
  pnl_pct: number;
}

interface PaperTradeItem {
  stock_code: string;
  side: string;
  quantity: number;
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_percent: number;
  entry_at: string;
  exit_at: string;
}

interface SessionSummary {
  session: PaperSession;
  stats: {
    initial_cash: number;
    cash: number;
    portfolio_value: number;
    total_pnl: number;
    total_pnl_pct: number;
    unrealized_pnl: number;
    realized_pnl: number;
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    win_rate: number;
    avg_win: number;
    avg_loss: number;
    profit_factor: number;
    max_drawdown_pct: number;
    open_positions: number;
  };
  positions: PaperPositionItem[];
  orders: PaperOrderItem[];
  trades: PaperTradeItem[];
  equity_curve: { time: string; value: number }[];
}

export default function PaperTradingPage() {
  const [sessions, setSessions] = useState<PaperSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<"positions" | "orders" | "trades">("positions");

  // Order form
  const [orderForm, setOrderForm] = useState({
    stock_code: "",
    stock_name: "",
    side: "buy",
    quantity: 0,
    current_price: 0,
    order_type: "market",
    limit_price: undefined as number | undefined,
  });
  const [orderResult, setOrderResult] = useState<string | null>(null);

  // New session form
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("Paper Trading");
  const [newCash, setNewCash] = useState(100_000_000);
  const [newFillModel, setNewFillModel] = useState("realistic");

  const loadSessions = useCallback(async () => {
    try {
      const res = await api.get("/paper/sessions");
      setSessions(res.data);
    } catch {
      // best effort
    }
  }, []);

  const loadSummary = useCallback(async (sessionId: string) => {
    try {
      const res = await api.get(`/paper/sessions/${sessionId}`);
      setSummary(res.data);
    } catch {
      setSummary(null);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (activeSessionId) {
      loadSummary(activeSessionId);
      const interval = setInterval(() => loadSummary(activeSessionId), 5000);
      return () => clearInterval(interval);
    }
  }, [activeSessionId, loadSummary]);

  const createSession = async () => {
    setLoading(true);
    try {
      const res = await api.post("/paper/sessions", {
        name: newName,
        initial_cash: newCash,
        fill_model: newFillModel,
      });
      setActiveSessionId(res.data.id);
      setShowCreate(false);
      await loadSessions();
    } catch {
      // error
    }
    setLoading(false);
  };

  const stopSession = async () => {
    if (!activeSessionId) return;
    try {
      await api.post(`/paper/sessions/${activeSessionId}/stop`);
      await loadSessions();
      await loadSummary(activeSessionId);
    } catch {
      // error
    }
  };

  const placeOrder = async () => {
    if (!activeSessionId) return;
    setOrderResult(null);
    try {
      const res = await api.post(`/paper/sessions/${activeSessionId}/order`, {
        stock_code: orderForm.stock_code,
        stock_name: orderForm.stock_name,
        side: orderForm.side,
        quantity: orderForm.quantity,
        current_price: orderForm.current_price,
        order_type: orderForm.order_type,
        limit_price: orderForm.order_type === "limit" ? orderForm.limit_price : undefined,
      });
      const o = res.data;
      setOrderResult(
        `${o.status === "filled" ? "Filled" : o.status} — ${o.side.toUpperCase()} ${o.quantity} @ ₩${o.avg_fill_price.toLocaleString()}`
      );
      await loadSummary(activeSessionId);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Order failed";
      setOrderResult(msg);
    }
  };

  const stats = summary?.stats;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Paper Trading</h2>
        <div className="flex gap-2">
          {activeSessionId && summary?.session.status === "active" && (
            <button
              onClick={stopSession}
              className="px-4 py-2 text-sm bg-red-600/20 text-red-400 rounded-lg hover:bg-red-600/30 border border-red-800"
            >
              Stop Session
            </button>
          )}
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            New Session
          </button>
        </div>
      </div>

      {/* Create Session Form */}
      {showCreate && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
          <h3 className="text-lg font-semibold mb-4">Create Paper Trading Session</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Session Name</label>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Initial Cash (₩)</label>
              <input
                type="number"
                value={newCash}
                onChange={(e) => setNewCash(Number(e.target.value))}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Fill Model</label>
              <select
                value={newFillModel}
                onChange={(e) => setNewFillModel(e.target.value)}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm"
              >
                <option value="realistic">Realistic (Slippage)</option>
                <option value="immediate">Immediate (No Slippage)</option>
              </select>
            </div>
          </div>
          <button
            onClick={createSession}
            disabled={loading}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
          >
            {loading ? "Creating..." : "Create Session"}
          </button>
        </div>
      )}

      {/* Session Selector */}
      {sessions.length > 0 && (
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => setActiveSessionId(s.id)}
              className={`px-4 py-2 rounded-lg text-sm whitespace-nowrap border transition-colors ${
                activeSessionId === s.id
                  ? "bg-blue-600/20 border-blue-500 text-blue-400"
                  : "bg-gray-900 border-gray-800 text-gray-400 hover:border-gray-600"
              }`}
            >
              {s.name}
              <span className={`ml-2 text-xs ${s.status === "active" ? "text-green-400" : "text-gray-500"}`}>
                {s.status === "active" ? "● Active" : "Completed"}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* No active session */}
      {!activeSessionId && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-12 text-center">
          <p className="text-gray-500 mb-4">Start a paper trading session to practice without risking real money.</p>
          <button
            onClick={() => setShowCreate(true)}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Create Your First Session
          </button>
        </div>
      )}

      {/* Stats Cards */}
      {stats && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <StatCard
              label="Portfolio Value"
              value={`₩${stats.portfolio_value.toLocaleString()}`}
            />
            <StatCard
              label="Total P&L"
              value={`₩${stats.total_pnl.toLocaleString()}`}
              sub={`${stats.total_pnl_pct >= 0 ? "+" : ""}${stats.total_pnl_pct}%`}
              color={stats.total_pnl >= 0 ? "green" : "red"}
            />
            <StatCard
              label="Win Rate"
              value={`${stats.win_rate}%`}
              sub={`${stats.winning_trades}W / ${stats.losing_trades}L`}
            />
            <StatCard
              label="Max Drawdown"
              value={`${stats.max_drawdown_pct}%`}
              sub={`Profit Factor: ${stats.profit_factor}`}
              color={stats.max_drawdown_pct > 5 ? "red" : "neutral"}
            />
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <StatCard label="Cash" value={`₩${stats.cash.toLocaleString()}`} />
            <StatCard
              label="Unrealized P&L"
              value={`₩${stats.unrealized_pnl.toLocaleString()}`}
              color={stats.unrealized_pnl >= 0 ? "green" : "red"}
            />
            <StatCard
              label="Realized P&L"
              value={`₩${stats.realized_pnl.toLocaleString()}`}
              color={stats.realized_pnl >= 0 ? "green" : "red"}
            />
            <StatCard
              label="Open Positions"
              value={String(stats.open_positions)}
              sub={`${stats.total_trades} total trades`}
            />
          </div>
        </>
      )}

      {/* Order Form */}
      {activeSessionId && summary?.session.status === "active" && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
          <h3 className="text-lg font-semibold mb-4">Place Paper Order</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 mb-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Stock Code</label>
              <input
                value={orderForm.stock_code}
                onChange={(e) => setOrderForm({ ...orderForm, stock_code: e.target.value })}
                placeholder="005930"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Stock Name</label>
              <input
                value={orderForm.stock_name}
                onChange={(e) => setOrderForm({ ...orderForm, stock_name: e.target.value })}
                placeholder="Samsung"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Side</label>
              <select
                value={orderForm.side}
                onChange={(e) => setOrderForm({ ...orderForm, side: e.target.value })}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm"
              >
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Quantity</label>
              <input
                type="number"
                value={orderForm.quantity || ""}
                onChange={(e) => setOrderForm({ ...orderForm, quantity: Number(e.target.value) })}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Current Price</label>
              <input
                type="number"
                value={orderForm.current_price || ""}
                onChange={(e) => setOrderForm({ ...orderForm, current_price: Number(e.target.value) })}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Order Type</label>
              <select
                value={orderForm.order_type}
                onChange={(e) => setOrderForm({ ...orderForm, order_type: e.target.value })}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm"
              >
                <option value="market">Market</option>
                <option value="limit">Limit</option>
              </select>
            </div>
            {orderForm.order_type === "limit" && (
              <div>
                <label className="block text-xs text-gray-400 mb-1">Limit Price</label>
                <input
                  type="number"
                  value={orderForm.limit_price || ""}
                  onChange={(e) => setOrderForm({ ...orderForm, limit_price: Number(e.target.value) })}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm"
                />
              </div>
            )}
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={placeOrder}
              disabled={!orderForm.stock_code || !orderForm.quantity || !orderForm.current_price}
              className={`px-6 py-2 rounded-lg text-sm font-medium disabled:opacity-50 ${
                orderForm.side === "buy"
                  ? "bg-green-600 hover:bg-green-700 text-white"
                  : "bg-red-600 hover:bg-red-700 text-white"
              }`}
            >
              {orderForm.side === "buy" ? "Buy" : "Sell"}
            </button>
            {orderResult && (
              <span className="text-sm text-gray-300">{orderResult}</span>
            )}
          </div>
        </div>
      )}

      {/* Tabs: Positions / Orders / Trades */}
      {summary && (
        <div className="bg-gray-900 rounded-xl border border-gray-800">
          <div className="flex border-b border-gray-800">
            {(["positions", "orders", "trades"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-6 py-3 text-sm font-medium transition-colors ${
                  tab === t
                    ? "text-blue-400 border-b-2 border-blue-400"
                    : "text-gray-500 hover:text-gray-300"
                }`}
              >
                {t === "positions" && `Positions (${summary.positions.length})`}
                {t === "orders" && `Orders (${summary.orders.length})`}
                {t === "trades" && `Trades (${summary.trades.length})`}
              </button>
            ))}
          </div>

          <div className="p-4 overflow-x-auto">
            {tab === "positions" && (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 border-b border-gray-800">
                    <th className="text-left py-2">Stock</th>
                    <th className="text-right py-2">Qty</th>
                    <th className="text-right py-2">Avg Cost</th>
                    <th className="text-right py-2">Current</th>
                    <th className="text-right py-2">P&L</th>
                    <th className="text-right py-2">P&L %</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.positions.length === 0 ? (
                    <tr><td colSpan={6} className="py-8 text-center text-gray-500">No open positions</td></tr>
                  ) : (
                    summary.positions.map((p) => (
                      <tr key={p.stock_code} className="border-b border-gray-800/50">
                        <td className="py-3">
                          <span className="font-medium">{p.stock_name || p.stock_code}</span>
                          <span className="text-gray-500 text-xs ml-2">{p.stock_code}</span>
                        </td>
                        <td className="text-right">{p.quantity.toLocaleString()}</td>
                        <td className="text-right">₩{p.avg_cost_price.toLocaleString()}</td>
                        <td className="text-right">₩{p.current_price.toLocaleString()}</td>
                        <td className={`text-right ${p.unrealized_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                          ₩{p.unrealized_pnl.toLocaleString()}
                        </td>
                        <td className={`text-right ${p.pnl_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {p.pnl_pct >= 0 ? "+" : ""}{p.pnl_pct}%
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            )}

            {tab === "orders" && (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 border-b border-gray-800">
                    <th className="text-left py-2">Stock</th>
                    <th className="text-center py-2">Side</th>
                    <th className="text-center py-2">Type</th>
                    <th className="text-right py-2">Qty</th>
                    <th className="text-right py-2">Filled</th>
                    <th className="text-right py-2">Fill Price</th>
                    <th className="text-center py-2">Status</th>
                    <th className="text-right py-2">Slippage</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.orders.length === 0 ? (
                    <tr><td colSpan={8} className="py-8 text-center text-gray-500">No orders yet</td></tr>
                  ) : (
                    [...summary.orders].reverse().map((o) => (
                      <tr key={o.id} className="border-b border-gray-800/50">
                        <td className="py-3">{o.stock_name || o.stock_code}</td>
                        <td className="text-center">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                            o.side === "buy" ? "bg-green-900/50 text-green-400" : "bg-red-900/50 text-red-400"
                          }`}>
                            {o.side.toUpperCase()}
                          </span>
                        </td>
                        <td className="text-center text-gray-400">{o.order_type}</td>
                        <td className="text-right">{o.quantity.toLocaleString()}</td>
                        <td className="text-right">{o.filled_quantity.toLocaleString()}</td>
                        <td className="text-right">
                          {o.avg_fill_price > 0 ? `₩${o.avg_fill_price.toLocaleString()}` : "--"}
                        </td>
                        <td className="text-center">
                          <span className={`px-2 py-0.5 rounded text-xs ${
                            o.status === "filled" ? "bg-green-900/30 text-green-400"
                            : o.status === "pending" ? "bg-yellow-900/30 text-yellow-400"
                            : o.status === "rejected" ? "bg-red-900/30 text-red-400"
                            : "bg-gray-800 text-gray-400"
                          }`}>
                            {o.status}
                          </span>
                        </td>
                        <td className="text-right text-gray-400">
                          {o.slippage_bps > 0 ? `${o.slippage_bps} bps` : "--"}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            )}

            {tab === "trades" && (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 border-b border-gray-800">
                    <th className="text-left py-2">Stock</th>
                    <th className="text-right py-2">Qty</th>
                    <th className="text-right py-2">Entry</th>
                    <th className="text-right py-2">Exit</th>
                    <th className="text-right py-2">P&L</th>
                    <th className="text-right py-2">P&L %</th>
                    <th className="text-right py-2">Exit Time</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.trades.length === 0 ? (
                    <tr><td colSpan={7} className="py-8 text-center text-gray-500">No completed trades yet</td></tr>
                  ) : (
                    [...summary.trades].reverse().map((t, i) => (
                      <tr key={i} className="border-b border-gray-800/50">
                        <td className="py-3">{t.stock_code}</td>
                        <td className="text-right">{t.quantity.toLocaleString()}</td>
                        <td className="text-right">₩{t.entry_price.toLocaleString()}</td>
                        <td className="text-right">₩{t.exit_price.toLocaleString()}</td>
                        <td className={`text-right font-medium ${t.pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                          ₩{t.pnl.toLocaleString()}
                        </td>
                        <td className={`text-right ${t.pnl_percent >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {t.pnl_percent >= 0 ? "+" : ""}{t.pnl_percent}%
                        </td>
                        <td className="text-right text-gray-400 text-xs">
                          {new Date(t.exit_at).toLocaleString("ko-KR", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({
  label, value, sub, color = "neutral",
}: {
  label: string; value: string; sub?: string; color?: string;
}) {
  const cls = color === "green" ? "text-green-400"
    : color === "red" ? "text-red-400"
    : "";
  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-xl font-bold mt-1 ${cls}`}>{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  );
}
