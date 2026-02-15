"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuthStore } from "@/store/auth";
import { useTradingStore } from "@/store/trading";
import { useTradingWebSocket, type PriceUpdateEvent } from "@/lib/useTradingWebSocket";
import api from "@/lib/api";
import { useI18n } from "@/i18n";
import Treemap from "@/app/dashboard/portfolio/_components/Treemap";
import type { Recipe } from "@/app/dashboard/recipes/types";

interface AllocationItem {
  stock_code: string;
  stock_name: string | null;
  value: number;
  weight: number;
  pnl_pct: number;
}

interface AgentAction {
  agent: string;
  action: string;
  timestamp: string;
}

function formatRelativeTime(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const fetchUser = useAuthStore((s) => s.fetchUser);
  const { positions, fetchPositions, updatePositionPrice } = useTradingStore();
  const { t } = useI18n();
  const [isLive, setIsLive] = useState(false);

  const handlePriceUpdate = useCallback(
    (data: PriceUpdateEvent) => {
      updatePositionPrice(data.stock_code, data.current_price);
      setIsLive(true);
    },
    [updatePositionPrice]
  );

  useTradingWebSocket({ onPriceUpdate: handlePriceUpdate });

  const [balance, setBalance] = useState<{
    total_balance: number;
    available_cash: number;
    invested_amount: number;
    total_pnl: number;
  } | null>(null);
  const [agentStatus, setAgentStatus] = useState<string>("Idle");
  const [strategyCount, setStrategyCount] = useState(0);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [allocation, setAllocation] = useState<AllocationItem[]>([]);
  const [recentActions, setRecentActions] = useState<AgentAction[]>([]);

  useEffect(() => {
    fetchUser();
    fetchPositions();
    loadDashboard();
  }, [fetchUser, fetchPositions]);

  const loadDashboard = async () => {
    try {
      const [balRes, stratRes, agentRes, recipesRes, analyticsRes] = await Promise.allSettled([
        api.get("/market/balance"),
        api.get("/strategies"),
        api.get("/agents/status"),
        api.get("/recipes"),
        api.get("/trading/portfolio/analytics"),
      ]);
      if (balRes.status === "fulfilled") setBalance(balRes.value.data);
      if (stratRes.status === "fulfilled") setStrategyCount(stratRes.value.data.length);
      if (agentRes.status === "fulfilled" && agentRes.value.data) {
        setAgentStatus(agentRes.value.data.status === "active" ? "Running" : "Idle");
        setRecentActions(agentRes.value.data.recent_actions || []);
      }
      if (recipesRes.status === "fulfilled") setRecipes(recipesRes.value.data);
      if (analyticsRes.status === "fulfilled" && analyticsRes.value.data?.allocation) {
        setAllocation(analyticsRes.value.data.allocation);
      }
    } catch {
      // Dashboard data is best-effort
    }
  };

  const totalPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
  const activeRecipes = recipes.filter((r) => r.is_active);

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">
        {t.dashboard.welcome} {user?.display_name || t.dashboard.defaultName}
      </h2>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8">
        <SummaryCard
          title={t.dashboard.totalBalance}
          value={balance ? `₩${balance.total_balance.toLocaleString()}` : "--"}
          subtitle={balance ? `Cash: ₩${balance.available_cash.toLocaleString()}` : t.dashboard.connectKis}
        />
        <SummaryCard
          title={t.dashboard.todayPnl}
          value={balance ? `₩${balance.total_pnl.toLocaleString()}` : "--"}
          subtitle={positions.length > 0 ? `${positions.length} ${t.dashboard.positions}` : t.dashboard.noPositions}
          color={balance && balance.total_pnl >= 0 ? "green" : "red"}
        />
        <SummaryCard
          title={t.dashboard.activeStrategies}
          value={String(strategyCount)}
          subtitle={strategyCount > 0 ? t.dashboard.strategiesConfigured : ""}
        />
        <SummaryCard
          title={t.dashboard.agentStatus}
          value={agentStatus}
          subtitle={agentStatus === "Running" ? t.dashboard.agentsWorking : t.dashboard.notRunning}
          color={agentStatus === "Running" ? "green" : "neutral"}
        />
      </div>

      {/* Insights Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        {/* Mini Portfolio Treemap */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-300">{t.dashboard.portfolioOverview}</h3>
            <a href="/dashboard/portfolio" className="text-xs text-blue-400 hover:text-blue-300">
              {t.dashboard.viewAll}
            </a>
          </div>
          {allocation.length > 0 ? (
            <Treemap
              items={allocation.map((a) => ({
                code: a.stock_code,
                name: a.stock_name,
                value: a.value,
                weight: a.weight,
                pnl_pct: a.pnl_pct,
              }))}
            />
          ) : (
            <p className="text-gray-600 text-sm py-8 text-center">{t.dashboard.noAllocation}</p>
          )}
        </div>

        {/* Active Recipes Widget */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-300">{t.dashboard.activeRecipes}</h3>
            <a href="/dashboard/recipes" className="text-xs text-blue-400 hover:text-blue-300">
              {t.dashboard.viewAll}
            </a>
          </div>
          {recipes.length > 0 ? (
            <>
              <div className="flex items-baseline gap-2 mb-3">
                <span className="text-2xl font-bold text-green-400">{activeRecipes.length}</span>
                <span className="text-sm text-gray-500">
                  / {recipes.length} {t.dashboard.recipesTotal}
                </span>
              </div>
              <div className="space-y-2">
                {activeRecipes.slice(0, 3).map((r) => (
                  <div key={r.id} className="flex items-center gap-2 text-sm">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-400 flex-shrink-0" />
                    <span className="text-gray-300 truncate">{r.name}</span>
                    <span className="text-gray-600 text-xs ml-auto">
                      {r.stock_codes?.length || 0} {t.common.stock}
                    </span>
                  </div>
                ))}
                {activeRecipes.length > 3 && (
                  <p className="text-xs text-gray-500">
                    +{activeRecipes.length - 3} {t.dashboard.moreRecipes}
                  </p>
                )}
              </div>
            </>
          ) : (
            <p className="text-gray-600 text-sm py-8 text-center">{t.dashboard.noRecipes}</p>
          )}
        </div>

        {/* Recent Activity Feed */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-300">{t.dashboard.recentActivity}</h3>
            <a href="/dashboard/agents" className="text-xs text-blue-400 hover:text-blue-300">
              {t.dashboard.viewAll}
            </a>
          </div>
          {recentActions.length > 0 ? (
            <div className="space-y-2.5">
              {recentActions.slice(0, 5).map((a, i) => (
                <div key={i} className="flex items-start gap-2 text-sm">
                  <span
                    className={`mt-1 w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                      a.action.includes("order")
                        ? "bg-yellow-400"
                        : a.action.includes("analysis")
                          ? "bg-blue-400"
                          : "bg-gray-500"
                    }`}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-gray-300 truncate">
                      <span className="text-gray-500">{a.agent}:</span> {a.action}
                    </p>
                    <p className="text-xs text-gray-600">{formatRelativeTime(a.timestamp)}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-600 text-sm py-8 text-center">{t.dashboard.noActivity}</p>
          )}
        </div>
      </div>

      {/* Positions */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-semibold">{t.dashboard.openPositions}</h3>
            {isLive && (
              <span className="inline-flex items-center gap-1 text-xs text-green-400">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                Live
              </span>
            )}
          </div>
          {positions.length > 0 && (
            <span className={`text-sm font-medium ${totalPnl >= 0 ? "text-green-400" : "text-red-400"}`}>
              {t.dashboard.totalPnl}: ₩{totalPnl.toLocaleString()}
            </span>
          )}
        </div>
        {positions.length === 0 ? (
          <p className="text-gray-500 text-sm">
            {t.dashboard.noPositions}
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-2">{t.common.stock}</th>
                <th className="text-right py-2">{t.common.qty}</th>
                <th className="text-right py-2">{t.dashboard.avgCost}</th>
                <th className="text-right py-2">{t.dashboard.current}</th>
                <th className="text-right py-2">{t.dashboard.pnl}</th>
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
        <h3 className="text-lg font-semibold mb-4">{t.dashboard.quickStart}</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <QuickAction
            title={t.dashboard.step1Title}
            description={t.dashboard.step1Desc}
            href="/dashboard/settings"
          />
          <QuickAction
            title={t.dashboard.step2Title}
            description={t.dashboard.step2Desc}
            href="/dashboard/strategies"
          />
          <QuickAction
            title={t.dashboard.step3Title}
            description={t.dashboard.step3Desc}
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
