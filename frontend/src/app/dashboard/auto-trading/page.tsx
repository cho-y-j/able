"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import { useI18n } from "@/i18n";
import { formatKRW, formatPct } from "@/lib/charts";
import { StockAutocomplete } from "@/components/StockAutocomplete";
import type { StockResult } from "@/lib/useStockSearch";
import {
  useTradingWebSocket,
  type OrderUpdateEvent,
  type PriceUpdateEvent,
  type RecipeSignalEvent,
} from "@/lib/useTradingWebSocket";

interface Recipe {
  id: string;
  name: string;
  description?: string;
  signal_config?: { combinator?: string; signals?: { strategy_type?: string; type?: string }[] };
  stock_codes: string[];
  risk_config?: Record<string, number>;
  is_active: boolean;
  auto_execute?: boolean;
}

interface RecipeOrder {
  id: string;
  stock_code: string;
  stock_name?: string;
  side: string;
  quantity: number;
  status: string;
  created_at: string;
}

interface ActivityOrder {
  id: string;
  recipe_id?: string;
  recipe_name?: string;
  stock_code: string;
  stock_name?: string;
  side: string;
  quantity: number;
  avg_fill_price?: number;
  status: string;
  created_at: string;
}

interface StockInfo {
  code: string;
  name: string;
}

export default function AutoTradingPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [activeRecipes, setActiveRecipes] = useState<Recipe[]>([]);
  const [allRecipes, setAllRecipes] = useState<Recipe[]>([]);
  const [loading, setLoading] = useState(true);
  const [ordersMap, setOrdersMap] = useState<Record<string, RecipeOrder[]>>({});
  const [stockNames, setStockNames] = useState<Record<string, string>>({});
  const [prices, setPrices] = useState<Record<string, { price: number; change_percent: number }>>({});
  const [balance, setBalance] = useState<number | null>(null);

  // Stock search + recipe execution
  const [searchInput, setSearchInput] = useState("");
  const [selectedStock, setSelectedStock] = useState<StockResult | null>(null);
  const [selectedRecipeId, setSelectedRecipeId] = useState<string>("");
  const [executing, setExecuting] = useState(false);
  const [alert, setAlert] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Highlight a card after execution
  const [highlightedRecipeId, setHighlightedRecipeId] = useState<string | null>(null);
  const cardRefs = useRef<Record<string, HTMLDivElement | null>>({});

  // Activity feed
  const [activityOrders, setActivityOrders] = useState<ActivityOrder[]>([]);
  const [activityFilter, setActivityFilter] = useState<{ recipe?: string; stock?: string; status?: string }>({});

  const fetchStockNames = useCallback(async (codes: string[]) => {
    if (codes.length === 0) return;
    try {
      const { data } = await api.get(`/market/stock-info-batch?codes=${codes.join(",")}`);
      const nameMap: Record<string, string> = {};
      for (const item of data.results as StockInfo[]) {
        if (item.name && item.name !== item.code) nameMap[item.code] = item.name;
      }
      setStockNames((prev) => ({ ...prev, ...nameMap }));
    } catch { /* ignore */ }
  }, []);

  const fetchRecipes = useCallback(async () => {
    try {
      const { data } = await api.get("/recipes");
      const all = data as Recipe[];
      // Deduplicate by id
      const seen = new Set<string>();
      const unique = all.filter((r) => {
        if (seen.has(r.id)) return false;
        seen.add(r.id);
        return true;
      });
      setAllRecipes(unique);
      const active = unique.filter((r) => r.is_active);
      setActiveRecipes(active);
      return { all: unique, active };
    } catch {
      setAllRecipes([]);
      setActiveRecipes([]);
      return { all: [], active: [] };
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchOrders = useCallback(async (recipeId: string) => {
    try {
      const { data } = await api.get(`/recipes/${recipeId}/orders?limit=10`);
      setOrdersMap((prev) => ({ ...prev, [recipeId]: data }));
    } catch { /* ignore */ }
  }, []);

  const fetchBalance = useCallback(async () => {
    try {
      const { data } = await api.get("/trading/balance");
      setBalance(data.total_balance || data.available_cash || 0);
    } catch { /* ignore */ }
  }, []);

  const fetchActivityFeed = useCallback(async () => {
    try {
      const { data } = await api.get("/recipes/activity-feed?limit=50");
      setActivityOrders(data as ActivityOrder[]);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchBalance();
    fetchRecipes().then(({ all, active }) => {
      active.forEach((r) => fetchOrders(r.id));
      const allCodes = new Set<string>();
      active.forEach((r) => r.stock_codes?.forEach((c) => allCodes.add(c)));
      fetchStockNames(Array.from(allCodes));
      if (all.length > 0) setSelectedRecipeId(all[0].id);
      fetchActivityFeed();
    });
  }, [fetchRecipes, fetchOrders, fetchStockNames, fetchBalance, fetchActivityFeed]);

  useEffect(() => {
    if (alert) {
      const timer = setTimeout(() => setAlert(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [alert]);

  // Auto-clear highlight after 3 seconds
  useEffect(() => {
    if (highlightedRecipeId) {
      const timer = setTimeout(() => setHighlightedRecipeId(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [highlightedRecipeId]);

  // Scroll to highlighted card when it appears
  useEffect(() => {
    if (highlightedRecipeId) {
      setTimeout(() => {
        const el = cardRefs.current[highlightedRecipeId];
        if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 200);
    }
  }, [highlightedRecipeId, activeRecipes]);

  // WebSocket
  const handlePriceUpdate = useCallback((data: PriceUpdateEvent) => {
    setPrices((prev) => ({
      ...prev,
      [data.stock_code]: { price: data.current_price, change_percent: data.change_percent },
    }));
  }, []);

  const handleOrderUpdate = useCallback(
    (data: OrderUpdateEvent) => {
      if (activeRecipes.some((r) => r.id === data.recipe_id)) {
        fetchOrders(data.recipe_id);
      }
      fetchActivityFeed();
    },
    [activeRecipes, fetchOrders, fetchActivityFeed]
  );

  useTradingWebSocket({
    onPriceUpdate: handlePriceUpdate,
    onOrderUpdate: handleOrderUpdate,
  });

  // ── Actions ──

  const handlePause = async (recipeId: string) => {
    try {
      await api.post(`/recipes/${recipeId}/deactivate`);
      setAlert({ type: "success", message: t.autoTrading.pauseSuccess });
      fetchRecipes();
    } catch {
      setAlert({ type: "error", message: t.autoTrading.pauseFailed });
    }
  };

  const handleExecuteNow = async (recipeId: string) => {
    setExecuting(true);
    try {
      const { data } = await api.post(`/recipes/${recipeId}/execute`);
      const submitted = data.total_submitted ?? 0;
      const failed = data.total_failed ?? 0;
      setAlert({
        type: failed > 0 ? "error" : "success",
        message: `${t.autoTrading.executeSuccess} (${t.autoTrading.submitted}: ${submitted}, ${t.autoTrading.failedOrders}: ${failed})`,
      });
      fetchOrders(recipeId);
      fetchActivityFeed();
      setHighlightedRecipeId(recipeId);
    } catch {
      setAlert({ type: "error", message: t.autoTrading.executeFailed });
    } finally {
      setExecuting(false);
    }
  };

  const handleStockExecute = async () => {
    if (!selectedStock || !selectedRecipeId) return;
    if (!confirm(t.autoTrading.executeConfirm)) return;
    setExecuting(true);
    try {
      // 1) Execute the recipe for this stock
      const { data } = await api.post(`/recipes/${selectedRecipeId}/execute`, {
        stock_code: selectedStock.code,
      });

      const recipe = allRecipes.find((r) => r.id === selectedRecipeId);

      // 2) Add stock to recipe if not already included
      if (recipe && !recipe.stock_codes.includes(selectedStock.code)) {
        try {
          await api.put(`/recipes/${selectedRecipeId}`, {
            stock_codes: [...recipe.stock_codes, selectedStock.code],
          });
        } catch { /* best effort */ }
      }

      // 3) Activate recipe if not already active
      if (recipe && !recipe.is_active) {
        try {
          await api.post(`/recipes/${selectedRecipeId}/activate`);
        } catch { /* best effort */ }
      }

      // 4) Register stock name
      if (selectedStock.name && selectedStock.name !== selectedStock.code) {
        setStockNames((prev) => ({ ...prev, [selectedStock.code]: selectedStock.name }));
      }

      // 5) Refresh everything
      await fetchRecipes();
      fetchOrders(selectedRecipeId);
      fetchActivityFeed();
      fetchBalance();

      // 6) Show result + highlight the card
      const submitted = data.total_submitted ?? 0;
      const failed = data.total_failed ?? 0;
      setAlert({
        type: failed > 0 ? "error" : "success",
        message: `${selectedStock.name} - ${t.autoTrading.executeSuccess} (${t.autoTrading.submitted}: ${submitted}, ${t.autoTrading.failedOrders}: ${failed})`,
      });
      setHighlightedRecipeId(selectedRecipeId);

      // 7) Clear stock selection
      setSelectedStock(null);
      setSearchInput("");
    } catch {
      setAlert({ type: "error", message: t.autoTrading.executeFailed });
    } finally {
      setExecuting(false);
    }
  };

  // Stats
  const totalStocks = new Set(activeRecipes.flatMap((r) => r.stock_codes || [])).size;
  const allOrders = Object.values(ordersMap).flat();
  const todayOrders = allOrders.filter((o) => {
    const d = new Date(o.created_at);
    const today = new Date();
    return d.toDateString() === today.toDateString();
  });

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 bg-gray-800 rounded w-64" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => <div key={i} className="h-24 bg-gray-800 rounded-xl" />)}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2].map((i) => <div key={i} className="h-64 bg-gray-800 rounded-xl" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Alert */}
      {alert && (
        <div className={`px-4 py-3 rounded-lg text-sm font-medium ${
          alert.type === "success"
            ? "bg-green-500/10 border border-green-500/30 text-green-400"
            : "bg-red-500/10 border border-red-500/30 text-red-400"
        }`}>
          {alert.message}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">{t.autoTrading.title}</h1>
        <button
          onClick={() => { fetchRecipes(); fetchBalance(); fetchActivityFeed(); }}
          className="text-sm text-gray-400 hover:text-white transition-colors"
        >
          {t.autoTrading.refresh}
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SummaryCard
          label={t.autoTrading.activeRecipes}
          value={`${activeRecipes.length}개`}
          color="text-green-400"
        />
        <SummaryCard
          label={t.autoTrading.monitoredStocks}
          value={`${totalStocks}개`}
          color="text-blue-400"
        />
        <SummaryCard
          label={t.autoTrading.todayPnl}
          value={`${todayOrders.length}건`}
          sub="오늘 주문"
          color="text-yellow-400"
        />
        <SummaryCard
          label={t.autoTrading.accountBalance}
          value={balance != null ? formatKRW(balance) : "--"}
          color="text-white"
        />
      </div>

      {/* Stock Search + Recipe Execution — moved above cards */}
      <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-white mb-3">{t.autoTrading.searchStock}</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <StockAutocomplete
              value={searchInput}
              onChange={setSearchInput}
              onSelect={(code, name) => { setSelectedStock({ code, name: name || code, market: "", sector: "" }); setSearchInput(""); }}
              placeholder="종목코드 또는 종목명"
              className="!py-2.5"
            />
            {selectedStock && (
              <div className="mt-2 bg-gray-900 rounded-lg px-3 py-2 flex items-center justify-between">
                <div>
                  <span className="text-sm text-white font-medium">{selectedStock.name}</span>
                  <span className="text-xs text-gray-500 font-mono ml-2">{selectedStock.code}</span>
                </div>
                <button
                  onClick={() => setSelectedStock(null)}
                  className="text-gray-500 hover:text-red-400 text-xs"
                >
                  &times;
                </button>
              </div>
            )}
          </div>
          <div>
            <select
              value={selectedRecipeId}
              onChange={(e) => setSelectedRecipeId(e.target.value)}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white focus:border-blue-500 focus:outline-none"
            >
              <option value="">{t.autoTrading.selectRecipe}</option>
              {allRecipes.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} {r.is_active ? "" : `(${t.autoTrading.inactive})`}
                </option>
              ))}
            </select>
          </div>
          <div>
            <button
              onClick={handleStockExecute}
              disabled={!selectedStock || !selectedRecipeId || executing}
              className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-700 disabled:text-gray-500 text-white py-2.5 rounded-lg text-sm font-medium transition-colors"
            >
              {executing ? t.autoTrading.executing : t.autoTrading.execute}
            </button>
          </div>
        </div>
      </div>

      {/* Active Recipes Grid */}
      {activeRecipes.length === 0 ? (
        <div className="text-center py-16 bg-gray-800/50 rounded-xl border border-gray-700 border-dashed">
          <p className="text-gray-400 text-lg mb-2">{t.autoTrading.noActiveRecipes}</p>
          <p className="text-gray-500 text-sm mb-6">{t.autoTrading.noActiveDesc}</p>
          <Link
            href="/dashboard/recipes"
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            {t.autoTrading.goToRecipes}
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {activeRecipes.map((recipe) => {
            const orders = ordersMap[recipe.id] || [];
            const successCount = orders.filter((o) => o.status === "submitted" || o.status === "filled").length;
            const failCount = orders.filter((o) => o.status === "failed").length;
            const isHighlighted = highlightedRecipeId === recipe.id;

            return (
              <div
                key={recipe.id}
                ref={(el) => { cardRefs.current[recipe.id] = el; }}
                className={`bg-gray-800 border rounded-xl p-5 transition-all duration-500 ${
                  isHighlighted
                    ? "border-green-400 ring-2 ring-green-400/30 shadow-lg shadow-green-500/10"
                    : "border-gray-700 hover:border-green-500/50"
                }`}
              >
                {/* Recipe Header */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="relative flex h-3 w-3 flex-shrink-0">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                      <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500" />
                    </span>
                    <h3 className="text-white font-semibold truncate">{recipe.name}</h3>
                    {recipe.auto_execute ? (
                      <span className="text-[10px] text-green-400 bg-green-500/10 px-1.5 py-0.5 rounded flex-shrink-0">자동매매</span>
                    ) : (
                      <span className="text-[10px] text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded flex-shrink-0">모니터링</span>
                    )}
                  </div>
                </div>

                {/* Stocks with Names */}
                <div className="space-y-1 mb-3">
                  {recipe.stock_codes.slice(0, 4).map((code) => {
                    const priceData = prices[code];
                    const name = stockNames[code];
                    return (
                      <div key={code} className="flex items-center justify-between bg-gray-900 rounded-lg px-3 py-1.5">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <span className="text-sm text-white truncate">{name || code}</span>
                          {name && <span className="text-[10px] text-gray-500 font-mono">{code}</span>}
                        </div>
                        {priceData ? (
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <span className="text-xs font-mono text-gray-300">{formatKRW(priceData.price)}</span>
                            <span className={`text-[11px] ${priceData.change_percent >= 0 ? "text-green-400" : "text-red-400"}`}>
                              {priceData.change_percent >= 0 ? "+" : ""}{priceData.change_percent.toFixed(2)}%
                            </span>
                          </div>
                        ) : (
                          <span className="text-xs text-gray-600">--</span>
                        )}
                      </div>
                    );
                  })}
                  {recipe.stock_codes.length > 4 && (
                    <p className="text-xs text-gray-500 pl-3">+{recipe.stock_codes.length - 4}개 종목</p>
                  )}
                </div>

                {/* Order Stats */}
                <div className="grid grid-cols-3 gap-2 mb-3">
                  <div className="bg-gray-900 rounded-lg p-2 text-center">
                    <p className="text-[10px] text-gray-500">{t.autoTrading.totalOrders}</p>
                    <p className="text-base font-bold text-white">{orders.length}</p>
                  </div>
                  <div className="bg-gray-900 rounded-lg p-2 text-center">
                    <p className="text-[10px] text-gray-500">{t.autoTrading.successOrders}</p>
                    <p className="text-base font-bold text-green-400">{successCount}</p>
                  </div>
                  <div className="bg-gray-900 rounded-lg p-2 text-center">
                    <p className="text-[10px] text-gray-500">{t.autoTrading.failedOrders}</p>
                    <p className="text-base font-bold text-red-400">{failCount}</p>
                  </div>
                </div>

                {/* Recent orders preview */}
                {orders.length > 0 && (
                  <div className="mb-3 space-y-1">
                    {orders.slice(0, 3).map((o) => {
                      const d = new Date(o.created_at);
                      const timeStr = `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
                      return (
                        <div key={o.id} className="flex items-center justify-between text-xs bg-gray-900/50 rounded px-2 py-1">
                          <span className="text-gray-500">{timeStr}</span>
                          <span className="text-white truncate mx-1">{o.stock_name || stockNames[o.stock_code] || o.stock_code}</span>
                          <span className={o.side === "buy" ? "text-green-400" : "text-red-400"}>
                            {o.side === "buy" ? "BUY" : "SELL"} {o.quantity}
                          </span>
                          <span className={`text-[10px] px-1 rounded ${
                            o.status === "filled" || o.status === "submitted"
                              ? "text-green-400"
                              : o.status === "failed" ? "text-red-400" : "text-yellow-400"
                          }`}>
                            {o.status}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2">
                  <button
                    onClick={() => handlePause(recipe.id)}
                    className="flex-1 bg-yellow-500/10 hover:bg-yellow-500/20 text-yellow-400 py-2 rounded-lg text-xs font-medium transition-colors"
                  >
                    {t.autoTrading.pause}
                  </button>
                  <button
                    onClick={() => handleExecuteNow(recipe.id)}
                    disabled={executing}
                    className="flex-1 bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 py-2 rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
                  >
                    {executing ? t.autoTrading.executing : t.autoTrading.executeNow}
                  </button>
                  <button
                    onClick={() => router.push(`/dashboard/recipes/${recipe.id}?tab=execution`)}
                    className="flex-1 bg-gray-700 hover:bg-gray-600 text-gray-300 py-2 rounded-lg text-xs font-medium transition-colors"
                  >
                    {t.recipes.viewDetail}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Activity Feed */}
      <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
          <h3 className="text-sm font-semibold text-white">{t.autoTrading.activityFeed}</h3>
          <div className="flex gap-2 flex-wrap">
            <select
              value={activityFilter.recipe || ""}
              onChange={(e) => setActivityFilter((f) => ({ ...f, recipe: e.target.value || undefined }))}
              className="bg-gray-900 border border-gray-700 rounded-lg px-2 py-1 text-xs text-gray-300"
            >
              <option value="">{t.autoTrading.allRecipes}</option>
              {allRecipes.map((r) => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>
            <select
              value={activityFilter.status || ""}
              onChange={(e) => setActivityFilter((f) => ({ ...f, status: e.target.value || undefined }))}
              className="bg-gray-900 border border-gray-700 rounded-lg px-2 py-1 text-xs text-gray-300"
            >
              <option value="">{t.autoTrading.allStatuses}</option>
              {["submitted", "filled", "failed", "pending", "cancelled"].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
        </div>

        {(() => {
          const filtered = activityOrders.filter((o) => {
            if (activityFilter.recipe && o.recipe_id !== activityFilter.recipe) return false;
            if (activityFilter.status && o.status !== activityFilter.status) return false;
            return true;
          });

          if (filtered.length === 0) {
            return (
              <p className="text-center text-gray-500 text-sm py-6">
                {t.autoTrading.noOrders}
              </p>
            );
          }

          return (
            <div className="overflow-x-auto -mx-5">
              <table className="w-full text-xs min-w-[600px]">
                <thead>
                  <tr className="text-gray-500 uppercase border-b border-gray-700">
                    <th className="text-left py-2 px-5">{t.autoTrading.time}</th>
                    <th className="text-left py-2 px-2">{t.common.stock}</th>
                    <th className="text-left py-2 px-2">{t.autoTrading.selectRecipe}</th>
                    <th className="text-left py-2 px-2">{t.common.side}</th>
                    <th className="text-right py-2 px-2">{t.common.qty}</th>
                    <th className="text-left py-2 px-5">{t.common.status}</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.slice(0, 30).map((o) => {
                    const d = new Date(o.created_at);
                    const timeStr = `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
                    const dateStr = o.created_at?.split("T")[0]?.slice(5);
                    return (
                      <tr key={o.id} className="border-b border-gray-700/50 hover:bg-gray-700/30">
                        <td className="py-2 px-5 text-gray-400">
                          {timeStr} <span className="text-gray-600">{dateStr}</span>
                        </td>
                        <td className="py-2 px-2">
                          <span className="text-white font-medium">
                            {o.stock_name || stockNames[o.stock_code] || o.stock_code}
                          </span>
                          {(o.stock_name || stockNames[o.stock_code]) && (
                            <span className="text-gray-600 font-mono ml-1">{o.stock_code}</span>
                          )}
                        </td>
                        <td className="py-2 px-2 text-gray-400">{o.recipe_name || "-"}</td>
                        <td className="py-2 px-2">
                          <span className={o.side === "buy" ? "text-green-400" : "text-red-400"}>
                            {o.side === "buy" ? "BUY" : "SELL"}
                          </span>
                        </td>
                        <td className="py-2 px-2 text-right text-gray-300">
                          {o.quantity.toLocaleString()}
                        </td>
                        <td className="py-2 px-5">
                          <span className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded ${
                            o.status === "filled" || o.status === "submitted"
                              ? "bg-green-900/40 text-green-400"
                              : o.status === "failed"
                                ? "bg-red-900/40 text-red-400"
                                : "bg-yellow-900/40 text-yellow-400"
                          }`}>
                            {o.status}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          );
        })()}
      </div>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  sub,
  color = "text-white",
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-[10px] text-gray-600 mt-0.5">{sub}</p>}
    </div>
  );
}
