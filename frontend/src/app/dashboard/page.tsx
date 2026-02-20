"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useAuthStore } from "@/store/auth";
import { useTradingStore } from "@/store/trading";
import { useTradingWebSocket, type PriceUpdateEvent } from "@/lib/useTradingWebSocket";
import api from "@/lib/api";
import { useI18n } from "@/i18n";
import Treemap from "@/app/dashboard/portfolio/_components/Treemap";
import type { Recipe } from "@/app/dashboard/recipes/types";

/* ── Types ─────────────────────────────────────────── */

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

type WidgetId =
  | "summary"
  | "portfolio"
  | "recipes"
  | "activity"
  | "positions"
  | "quickstart"
  | "trending"
  | "indices";

interface WidgetConfig {
  id: WidgetId;
  visible: boolean;
}

const WIDGET_LABELS: Record<WidgetId, { en: string; ko: string }> = {
  summary:    { en: "Summary Cards",     ko: "요약 카드" },
  portfolio:  { en: "Portfolio Overview", ko: "포트폴리오 현황" },
  recipes:    { en: "Active Recipes",    ko: "활성 레시피" },
  activity:   { en: "Recent Activity",   ko: "최근 활동" },
  positions:  { en: "Open Positions",    ko: "보유 종목" },
  quickstart: { en: "Quick Start",       ko: "빠른 시작" },
  trending:   { en: "Trending Stocks",   ko: "인기 종목" },
  indices:    { en: "Market Indices",    ko: "시장 지수" },
};

const DEFAULT_WIDGETS: WidgetConfig[] = [
  { id: "summary",    visible: true },
  { id: "portfolio",  visible: true },
  { id: "recipes",    visible: true },
  { id: "activity",   visible: true },
  { id: "positions",  visible: true },
  { id: "quickstart", visible: true },
  { id: "trending",   visible: true },
  { id: "indices",    visible: true },
];

const STORAGE_KEY = "dashboard-widgets";

function loadWidgetConfig(): WidgetConfig[] {
  if (typeof window === "undefined") return DEFAULT_WIDGETS;
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return DEFAULT_WIDGETS;
    const parsed = JSON.parse(saved) as WidgetConfig[];
    // Ensure all widget IDs exist (in case new widgets were added)
    const savedIds = new Set(parsed.map((w) => w.id));
    const merged = [...parsed];
    for (const dw of DEFAULT_WIDGETS) {
      if (!savedIds.has(dw.id)) merged.push(dw);
    }
    return merged;
  } catch {
    return DEFAULT_WIDGETS;
  }
}

function saveWidgetConfig(config: WidgetConfig[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
}

/* ── Helpers ───────────────────────────────────────── */

function formatRelativeTime(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

interface TrendingStock {
  rank: number;
  stock_name: string;
  stock_code: string;
  search_ratio: number;
  price: number;
  change_pct: number;
}

interface MarketIndex {
  name: string;
  value: number;
  change_pct: number;
}

/* ── Main Component ────────────────────────────────── */

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const fetchUser = useAuthStore((s) => s.fetchUser);
  const { positions, fetchPositions, updatePositionPrice } = useTradingStore();
  const { t } = useI18n();
  const [isLive, setIsLive] = useState(false);
  const [customizing, setCustomizing] = useState(false);
  const [widgets, setWidgets] = useState<WidgetConfig[]>(DEFAULT_WIDGETS);

  useEffect(() => {
    setWidgets(loadWidgetConfig());
  }, []);

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
  const [trending, setTrending] = useState<TrendingStock[]>([]);
  const [indices, setIndices] = useState<MarketIndex[]>([]);

  useEffect(() => {
    fetchUser();
    fetchPositions();
    loadDashboard();
  }, [fetchUser, fetchPositions]);

  const loadDashboard = async () => {
    try {
      const [balRes, stratRes, agentRes, recipesRes, analyticsRes, trendRes, idxRes] =
        await Promise.allSettled([
          api.get("/market/balance"),
          api.get("/strategies"),
          api.get("/agents/status"),
          api.get("/recipes"),
          api.get("/trading/portfolio/analytics"),
          api.get("/rankings/trending?limit=5"),
          api.get("/factors/global"),
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
      if (trendRes.status === "fulfilled") setTrending(trendRes.value.data || []);
      if (idxRes.status === "fulfilled" && Array.isArray(idxRes.value.data)) {
        setIndices(
          idxRes.value.data
            .filter((f: { factor_name: string }) => f.factor_name.endsWith("_change_pct"))
            .slice(0, 6)
            .map((f: { factor_name: string; value: number }) => ({
              name: f.factor_name.replace("_change_pct", "").toUpperCase(),
              value: 0,
              change_pct: f.value,
            }))
        );
      }
    } catch {
      // Dashboard data is best-effort
    }
  };

  const totalPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
  const activeRecipes = recipes.filter((r) => r.is_active);

  const isVisible = useCallback(
    (id: WidgetId) => widgets.find((w) => w.id === id)?.visible ?? true,
    [widgets]
  );

  const toggleWidget = useCallback((id: WidgetId) => {
    setWidgets((prev) => {
      const next = prev.map((w) => (w.id === id ? { ...w, visible: !w.visible } : w));
      saveWidgetConfig(next);
      return next;
    });
  }, []);

  const moveWidget = useCallback((id: WidgetId, direction: "up" | "down") => {
    setWidgets((prev) => {
      const idx = prev.findIndex((w) => w.id === id);
      if (idx < 0) return prev;
      const swapIdx = direction === "up" ? idx - 1 : idx + 1;
      if (swapIdx < 0 || swapIdx >= prev.length) return prev;
      const next = [...prev];
      [next[idx], next[swapIdx]] = [next[swapIdx], next[idx]];
      saveWidgetConfig(next);
      return next;
    });
  }, []);

  const resetWidgets = useCallback(() => {
    setWidgets(DEFAULT_WIDGETS);
    saveWidgetConfig(DEFAULT_WIDGETS);
  }, []);

  // Widget render map
  const widgetRenderers: Record<WidgetId, () => React.ReactNode> = useMemo(
    () => ({
      summary: () => (
        <div key="summary" className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
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
      ),

      portfolio: () => (
        <div key="portfolio" className="bg-gray-900 rounded-xl border border-gray-800 p-5">
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
      ),

      recipes: () => (
        <div key="recipes" className="bg-gray-900 rounded-xl border border-gray-800 p-5">
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
      ),

      activity: () => (
        <div key="activity" className="bg-gray-900 rounded-xl border border-gray-800 p-5">
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
      ),

      positions: () => (
        <div key="positions" className="bg-gray-900 rounded-xl border border-gray-800 p-6">
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
            <p className="text-gray-500 text-sm">{t.dashboard.noPositions}</p>
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
      ),

      quickstart: () => (
        <div key="quickstart" className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="text-lg font-semibold mb-4">{t.dashboard.quickStart}</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <QuickAction title={t.dashboard.step1Title} description={t.dashboard.step1Desc} href="/dashboard/settings" />
            <QuickAction title={t.dashboard.step2Title} description={t.dashboard.step2Desc} href="/dashboard/strategies" />
            <QuickAction title={t.dashboard.step3Title} description={t.dashboard.step3Desc} href="/dashboard/agents" />
          </div>
        </div>
      ),

      trending: () => (
        <div key="trending" className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-300">
              {t.dashboard.trendingStocks || "Trending Stocks"}
            </h3>
            <a href="/dashboard/rankings" className="text-xs text-blue-400 hover:text-blue-300">
              {t.dashboard.viewAll}
            </a>
          </div>
          {trending.length > 0 ? (
            <div className="space-y-2">
              {trending.map((s) => (
                <div key={s.stock_code} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className="text-gray-500 font-mono text-xs w-4">{s.rank}</span>
                    <span className="text-gray-200">{s.stock_name}</span>
                  </div>
                  <span className={s.change_pct >= 0 ? "text-green-400 font-mono text-xs" : "text-red-400 font-mono text-xs"}>
                    {s.change_pct >= 0 ? "+" : ""}{s.change_pct.toFixed(2)}%
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-600 text-sm py-6 text-center">
              {t.dashboard.noTrending || "No trending data"}
            </p>
          )}
        </div>
      ),

      indices: () => (
        <div key="indices" className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-300">
              {t.dashboard.marketIndices || "Market Indices"}
            </h3>
            <a href="/dashboard/factors" className="text-xs text-blue-400 hover:text-blue-300">
              {t.dashboard.viewAll}
            </a>
          </div>
          {indices.length > 0 ? (
            <div className="grid grid-cols-2 gap-2">
              {indices.map((idx) => (
                <div key={idx.name} className="bg-gray-800 rounded-lg px-3 py-2">
                  <p className="text-xs text-gray-500">{idx.name}</p>
                  <p className={`text-sm font-mono font-semibold ${idx.change_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {idx.change_pct >= 0 ? "+" : ""}{idx.change_pct.toFixed(2)}%
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-600 text-sm py-6 text-center">
              {t.dashboard.noIndices || "No index data"}
            </p>
          )}
        </div>
      ),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, balance, positions, strategyCount, agentStatus, recipes, activeRecipes, allocation, recentActions, trending, indices, isLive, totalPnl]
  );

  // Group widgets: summary is full-width, next 3 (portfolio/recipes/activity) are a 3-col row,
  // trending+indices are 2-col, positions and quickstart full-width.
  // But with customization, we just render in order, with layout hints per widget type.
  const fullWidthIds = new Set<WidgetId>(["summary", "positions", "quickstart"]);
  const visibleWidgets = widgets.filter((w) => w.visible);

  // Separate widgets into layout groups for better visual structure
  const renderWidgets = () => {
    const result: React.ReactNode[] = [];
    let smallBatch: WidgetConfig[] = [];

    const flushSmallBatch = () => {
      if (smallBatch.length === 0) return;
      const cols = smallBatch.length >= 3 ? "lg:grid-cols-3" : smallBatch.length === 2 ? "lg:grid-cols-2" : "";
      result.push(
        <div key={`batch-${smallBatch[0].id}`} className={`grid grid-cols-1 ${cols} gap-4`}>
          {smallBatch.map((w) => widgetRenderers[w.id]())}
        </div>
      );
      smallBatch = [];
    };

    for (const w of visibleWidgets) {
      if (fullWidthIds.has(w.id)) {
        flushSmallBatch();
        result.push(widgetRenderers[w.id]());
      } else {
        smallBatch.push(w);
        if (smallBatch.length === 3) flushSmallBatch();
      }
    }
    flushSmallBatch();
    return result;
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">
          {t.dashboard.welcome} {user?.display_name || t.dashboard.defaultName}
        </h2>
        <button
          onClick={() => setCustomizing((v) => !v)}
          className="text-sm text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg border border-gray-700 hover:border-gray-500"
          data-testid="customize-btn"
        >
          {customizing
            ? (t.dashboard.doneCustomizing || "Done")
            : (t.dashboard.customize || "Customize")}
        </button>
      </div>

      {/* Customize Panel */}
      {customizing && (
        <div className="bg-gray-900 rounded-xl border border-gray-700 p-4 mb-6" data-testid="customize-panel">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-300">
              {t.dashboard.customizeWidgets || "Customize Widgets"}
            </h3>
            <button
              onClick={resetWidgets}
              className="text-xs text-gray-500 hover:text-white"
              data-testid="reset-btn"
            >
              {t.dashboard.resetDefault || "Reset to Default"}
            </button>
          </div>
          <div className="space-y-1">
            {widgets.map((w, idx) => (
              <div
                key={w.id}
                className="flex items-center gap-3 bg-gray-800 rounded-lg px-3 py-2"
              >
                <label className="flex items-center gap-2 flex-1 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={w.visible}
                    onChange={() => toggleWidget(w.id)}
                    className="accent-blue-500"
                    data-testid={`toggle-${w.id}`}
                  />
                  <span className="text-sm text-gray-300">
                    {WIDGET_LABELS[w.id]?.en || w.id}
                  </span>
                </label>
                <div className="flex gap-1">
                  <button
                    onClick={() => moveWidget(w.id, "up")}
                    disabled={idx === 0}
                    className="text-gray-500 hover:text-white disabled:opacity-30 text-xs px-1"
                    data-testid={`move-up-${w.id}`}
                  >
                    ↑
                  </button>
                  <button
                    onClick={() => moveWidget(w.id, "down")}
                    disabled={idx === widgets.length - 1}
                    className="text-gray-500 hover:text-white disabled:opacity-30 text-xs px-1"
                    data-testid={`move-down-${w.id}`}
                  >
                    ↓
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Widgets */}
      <div className="space-y-4 sm:space-y-6">
        {renderWidgets()}
      </div>
    </div>
  );
}

/* ── Sub-components ────────────────────────────────── */

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
