"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/auth";
import { useTradingStore } from "@/store/trading";
import api from "@/lib/api";

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const fetchUser = useAuthStore((s) => s.fetchUser);
  const { positions, fetchPositions } = useTradingStore();
  const [balance, setBalance] = useState<{
    total_balance: number;
    available_cash: number;
    invested_amount: number;
    total_pnl: number;
  } | null>(null);
  const [agentStatus, setAgentStatus] = useState<string>("Idle");
  const [strategyCount, setStrategyCount] = useState(0);

  useEffect(() => {
    fetchUser();
    fetchPositions();
    loadDashboard();
  }, [fetchUser, fetchPositions]);

  const loadDashboard = async () => {
    try {
      const [balRes, stratRes, agentRes] = await Promise.allSettled([
        api.get("/market/balance"),
        api.get("/strategies"),
        api.get("/agents/status"),
      ]);
      if (balRes.status === "fulfilled") setBalance(balRes.value.data);
      if (stratRes.status === "fulfilled") setStrategyCount(stratRes.value.data.length);
      if (agentRes.status === "fulfilled" && agentRes.value.data) {
        setAgentStatus(agentRes.value.data.status === "active" ? "Running" : "Idle");
      }
    } catch {
      // Dashboard data is best-effort
    }
  };

  const totalPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">
        Welcome back, {user?.display_name || "Trader"}
      </h2>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8">
        <SummaryCard
          title="Total Balance"
          value={balance ? `₩${balance.total_balance.toLocaleString()}` : "--"}
          subtitle={balance ? `Cash: ₩${balance.available_cash.toLocaleString()}` : "Connect KIS API"}
        />
        <SummaryCard
          title="Today P&L"
          value={balance ? `₩${balance.total_pnl.toLocaleString()}` : "--"}
          subtitle={positions.length > 0 ? `${positions.length} positions` : "No active trades"}
          color={balance && balance.total_pnl >= 0 ? "green" : "red"}
        />
        <SummaryCard
          title="Active Strategies"
          value={String(strategyCount)}
          subtitle={strategyCount > 0 ? "strategies configured" : "No strategies"}
        />
        <SummaryCard
          title="AI Agent Status"
          value={agentStatus}
          subtitle={agentStatus === "Running" ? "Agents working" : "Not running"}
          color={agentStatus === "Running" ? "green" : "neutral"}
        />
      </div>

      {/* Positions */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Open Positions</h3>
          {positions.length > 0 && (
            <span className={`text-sm font-medium ${totalPnl >= 0 ? "text-green-400" : "text-red-400"}`}>
              Total P&L: ₩{totalPnl.toLocaleString()}
            </span>
          )}
        </div>
        {positions.length === 0 ? (
          <p className="text-gray-500 text-sm">
            No open positions. Configure your API keys in Settings to start trading.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-2">Stock</th>
                <th className="text-right py-2">Qty</th>
                <th className="text-right py-2">Avg Cost</th>
                <th className="text-right py-2">Current</th>
                <th className="text-right py-2">P&L</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => (
                <tr key={p.id} className="border-b border-gray-800/50">
                  <td className="py-3">{p.stock_name || p.stock_code}</td>
                  <td className="text-right">{p.quantity}</td>
                  <td className="text-right">₩{p.avg_cost_price.toLocaleString()}</td>
                  <td className="text-right">{p.current_price ? `₩${p.current_price.toLocaleString()}` : "--"}</td>
                  <td className={`text-right ${(p.unrealized_pnl || 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {p.unrealized_pnl != null ? `₩${p.unrealized_pnl.toLocaleString()}` : "--"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Quick Actions */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <h3 className="text-lg font-semibold mb-4">Quick Start</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <QuickAction
            title="1. Setup API Keys"
            description="Configure your Korea Investment & LLM API keys"
            href="/dashboard/settings"
          />
          <QuickAction
            title="2. Search Strategies"
            description="Let AI find optimal trading strategies"
            href="/dashboard/strategies"
          />
          <QuickAction
            title="3. Start AI Agent"
            description="Activate the automated trading agent team"
            href="/dashboard/agents"
          />
        </div>
      </div>
    </div>
  );
}

function SummaryCard({
  title, value, subtitle, color = "neutral",
}: {
  title: string; value: string; subtitle: string; color?: string;
}) {
  const colorClass = color === "green" ? "text-green-400"
    : color === "red" ? "text-red-400"
    : "";
  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
      <p className="text-sm text-gray-500">{title}</p>
      <p className={`text-2xl font-bold mt-1 ${colorClass}`}>{value}</p>
      <p className="text-xs text-gray-600 mt-1">{subtitle}</p>
    </div>
  );
}

function QuickAction({
  title, description, href,
}: {
  title: string; description: string; href: string;
}) {
  return (
    <a
      href={href}
      className="block p-4 rounded-lg border border-gray-700 hover:border-blue-500 transition-colors"
    >
      <h4 className="font-medium text-blue-400">{title}</h4>
      <p className="text-sm text-gray-500 mt-1">{description}</p>
    </a>
  );
}
