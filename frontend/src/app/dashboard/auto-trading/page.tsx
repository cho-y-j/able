"use client";

import { useState, useEffect, useCallback } from "react";
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
  side: string;
  quantity: number;
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
  const [recipes, setRecipes] = useState<Recipe[]>([]);
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
      const active = (data as Recipe[]).filter((r) => r.is_active);
      setRecipes(active);
      return active;
    } catch {
      setRecipes([]);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchOrders = useCallback(async (recipeId: string) => {
    try {
      const { data } = await api.get(`/recipes/${recipeId}/orders?limit=5`);
      setOrdersMap((prev) => ({ ...prev, [recipeId]: data }));
    } catch { /* ignore */ }
  }, []);

  const fetchBalance = useCallback(async () => {
    try {
      const { data } = await api.get("/trading/balance");
      setBalance(data.total_balance || data.available_cash || 0);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchBalance();
    fetchRecipes().then((active) => {
      active.forEach((r) => fetchOrders(r.id));
      const allCodes = new Set<string>();
      active.forEach((r) => r.stock_codes?.forEach((c) => allCodes.add(c)));
      fetchStockNames(Array.from(allCodes));
      if (active.length > 0) setSelectedRecipeId(active[0].id);
    });
  }, [fetchRecipes, fetchOrders, fetchStockNames, fetchBalance]);

  useEffect(() => {
    if (alert) {
      const timer = setTimeout(() => setAlert(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [alert]);

  // WebSocket
  const handlePriceUpdate = useCallback((data: PriceUpdateEvent) => {
    setPrices((prev) => ({
      ...prev,
      [data.stock_code]: { price: data.current_price, change_percent: data.change_percent },
    }));
  }, []);

  const handleOrderUpdate = useCallback(
    (data: OrderUpdateEvent) => {
      if (recipes.some((r) => r.id === data.recipe_id)) {
        fetchOrders(data.recipe_id);
      }
    },
    [recipes, fetchOrders]
  );

  useTradingWebSocket({
    onPriceUpdate: handlePriceUpdate,
    onOrderUpdate: handleOrderUpdate,
  });

  // Actions
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
      await api.post(`/recipes/${recipeId}/execute`);
      setAlert({ type: "success", message: t.autoTrading.executeSuccess });
      fetchOrders(recipeId);
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
      await api.post(`/recipes/${selectedRecipeId}/execute`, {
        stock_code: selectedStock.code,
      });
      setAlert({ type: "success", message: t.autoTrading.executeSuccess });
      fetchOrders(selectedRecipeId);
    } catch {
      setAlert({ type: "error", message: t.autoTrading.executeFailed });
    } finally {
      setExecuting(false);
    }
  };

  // Stats
  const totalStocks = new Set(recipes.flatMap((r) => r.stock_codes || [])).size;
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
          onClick={() => { fetchRecipes(); fetchBalance(); }}
          className="text-sm text-gray-400 hover:text-white transition-colors"
        >
          {t.autoTrading.refresh}
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SummaryCard
          label={t.autoTrading.activeRecipes}
          value={`${recipes.length}개`}
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

      {/* Active Recipes or Empty State */}
      {recipes.length === 0 ? (
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
          {recipes.map((recipe) => {
            const orders = ordersMap[recipe.id] || [];
            const successCount = orders.filter((o) => o.status === "submitted" || o.status === "filled").length;
            const failCount = orders.filter((o) => o.status === "failed").length;

            return (
              <div key={recipe.id} className="bg-gray-800 border border-gray-700 rounded-xl p-5 hover:border-green-500/50 transition-colors">
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
                    onClick={() => router.push(`/dashboard/recipes/${recipe.id}`)}
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

      {/* Stock Search + Recipe Execution */}
      <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-white mb-3">{t.autoTrading.searchStock}</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <StockAutocomplete
              value={searchInput}
              onChange={setSearchInput}
              onSelect={(stock) => { setSelectedStock(stock); setSearchInput(""); }}
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
              {recipes.map((r) => (
                <option key={r.id} value={r.id}>{r.name}</option>
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
