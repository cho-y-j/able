"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import api from "@/lib/api";
import { useI18n } from "@/i18n";
import { formatKRW } from "@/lib/charts";
import {
  useTradingWebSocket,
  type OrderUpdateEvent,
  type PriceUpdateEvent,
  type RecipeSignalEvent,
} from "@/lib/useTradingWebSocket";
import type { Recipe } from "../types";

interface RecipeOrder {
  id: string;
  stock_code: string;
  side: string;
  quantity: number;
  avg_fill_price: number | null;
  status: string;
  created_at: string;
}

interface SignalAlert {
  recipeId: string;
  recipeName: string;
  stockCode: string;
  signalType: "entry" | "exit";
  timestamp: number;
}

interface StockInfo {
  code: string;
  name: string;
  market: string;
  sector: string;
}

export default function RecipeMonitorPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [loading, setLoading] = useState(true);
  const [ordersMap, setOrdersMap] = useState<Record<string, RecipeOrder[]>>({});
  const [prices, setPrices] = useState<
    Record<string, { price: number; change_percent: number }>
  >({});
  const [signals, setSignals] = useState<SignalAlert[]>([]);
  const [stockNames, setStockNames] = useState<Record<string, string>>({});

  const fetchStockNames = useCallback(async (codes: string[]) => {
    if (codes.length === 0) return;
    try {
      const { data } = await api.get(
        `/market/stock-info-batch?codes=${codes.join(",")}`
      );
      const nameMap: Record<string, string> = {};
      for (const item of data.results as StockInfo[]) {
        if (item.name && item.name !== item.code) {
          nameMap[item.code] = item.name;
        }
      }
      setStockNames((prev) => ({ ...prev, ...nameMap }));
    } catch {
      // fallback: use codes as names
    }
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
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchRecipes().then((active) => {
      active.forEach((r) => fetchOrders(r.id));
      // Collect all stock codes and fetch names
      const allCodes = new Set<string>();
      active.forEach((r) => r.stock_codes?.forEach((c) => allCodes.add(c)));
      fetchStockNames(Array.from(allCodes));
    });
  }, [fetchRecipes, fetchOrders, fetchStockNames]);

  // WebSocket handlers
  const handlePriceUpdate = useCallback((data: PriceUpdateEvent) => {
    setPrices((prev) => ({
      ...prev,
      [data.stock_code]: {
        price: data.current_price,
        change_percent: data.change_percent,
      },
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

  const handleRecipeSignal = useCallback((data: RecipeSignalEvent) => {
    const alert: SignalAlert = {
      recipeId: data.recipe_id,
      recipeName: data.recipe_name,
      stockCode: data.stock_code,
      signalType: data.signal_type,
      timestamp: Date.now(),
    };
    setSignals((prev) => [alert, ...prev].slice(0, 20));
    setTimeout(() => {
      setSignals((prev) => prev.filter((s) => s.timestamp !== alert.timestamp));
    }, 10000);
  }, []);

  useTradingWebSocket({
    onPriceUpdate: handlePriceUpdate,
    onOrderUpdate: handleOrderUpdate,
    onRecipeSignal: handleRecipeSignal,
  });

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 bg-gray-800 rounded w-48 animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-gray-800 rounded-xl p-5 border border-gray-700 animate-pulse h-64"
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-white">
            {t.recipes.monitor}
          </h1>
          <span className="bg-green-500/20 text-green-400 text-xs px-2.5 py-1 rounded-full font-medium">
            {recipes.length} {t.recipes.activeRecipes}
          </span>
        </div>
        <Link
          href="/dashboard/recipes"
          className="text-sm text-gray-400 hover:text-white transition-colors"
        >
          {t.recipes.goToRecipes}
        </Link>
      </div>

      {/* Signal Alerts */}
      {signals.length > 0 && (
        <div className="space-y-2">
          {signals.slice(0, 3).map((s) => (
            <div
              key={s.timestamp}
              className={`flex items-center justify-between p-3 rounded-xl border ${
                s.signalType === "entry"
                  ? "bg-green-500/10 border-green-500/30"
                  : "bg-red-500/10 border-red-500/30"
              }`}
            >
              <p
                className={`text-sm ${
                  s.signalType === "entry" ? "text-green-400" : "text-red-400"
                }`}
              >
                {s.signalType === "entry"
                  ? t.recipes.entrySignal
                  : t.recipes.exitSignal}
                :{" "}
                <span className="font-medium text-white">
                  {stockNames[s.stockCode] || s.stockCode}
                </span>{" "}
                <span className="text-gray-500 font-mono text-xs">{s.stockCode}</span>
                {" — "}
                {s.recipeName}
              </p>
              <button
                onClick={() =>
                  setSignals((prev) =>
                    prev.filter((x) => x.timestamp !== s.timestamp)
                  )
                }
                className="text-gray-500 hover:text-gray-300 text-xs"
              >
                &times;
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {recipes.length === 0 ? (
        <div className="text-center py-16 bg-gray-800/50 rounded-xl border border-gray-700 border-dashed">
          <p className="text-gray-400 text-lg mb-2">
            {t.recipes.noActiveRecipes}
          </p>
          <p className="text-gray-500 text-sm mb-6">
            {t.recipes.monitorDesc}
          </p>
          <Link
            href="/dashboard/recipes"
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            {t.recipes.goToRecipes}
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {recipes.map((recipe) => (
            <RecipeMonitorCard
              key={recipe.id}
              recipe={recipe}
              orders={ordersMap[recipe.id] || []}
              prices={prices}
              stockNames={stockNames}
              onViewDetail={() =>
                router.push(`/dashboard/recipes/${recipe.id}`)
              }
              t={t}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function RecipeMonitorCard({
  recipe,
  orders,
  prices,
  stockNames,
  onViewDetail,
  t,
}: {
  recipe: Recipe;
  orders: RecipeOrder[];
  prices: Record<string, { price: number; change_percent: number }>;
  stockNames: Record<string, string>;
  onViewDetail: () => void;
  t: ReturnType<typeof useI18n>["t"];
}) {
  const successCount = orders.filter(
    (o) => o.status === "submitted" || o.status === "filled"
  ).length;
  const failCount = orders.filter((o) => o.status === "failed").length;

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-5 hover:border-green-500/50 transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500" />
            </span>
            <h3 className="text-white font-semibold truncate">{recipe.name}</h3>
          </div>
          {recipe.auto_execute && (
            <span className="text-[10px] text-green-400 bg-green-500/10 px-1.5 py-0.5 rounded mt-1 inline-block">
              자동매매
            </span>
          )}
          {recipe.is_active && !recipe.auto_execute && (
            <span className="text-[10px] text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded mt-1 inline-block">
              모니터링
            </span>
          )}
        </div>
      </div>

      {/* Stock Rows with Names and Prices */}
      <div className="space-y-1.5 mb-4">
        {recipe.stock_codes.map((code) => {
          const priceData = prices[code];
          const name = stockNames[code];
          return (
            <div
              key={code}
              className="flex items-center justify-between bg-gray-900 rounded-lg px-3 py-2"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-sm font-medium text-white truncate">
                  {name || code}
                </span>
                {name && (
                  <span className="text-[11px] text-gray-500 font-mono">{code}</span>
                )}
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {priceData ? (
                  <>
                    <span className="text-sm font-mono text-gray-300">
                      {formatKRW(priceData.price)}
                    </span>
                    <span
                      className={`text-xs font-medium ${
                        priceData.change_percent >= 0
                          ? "text-green-400"
                          : "text-red-400"
                      }`}
                    >
                      {priceData.change_percent >= 0 ? "+" : ""}
                      {priceData.change_percent.toFixed(2)}%
                    </span>
                  </>
                ) : (
                  <span className="text-xs text-gray-600">--</span>
                )}
              </div>
            </div>
          );
        })}
        {recipe.stock_codes.length === 0 && (
          <p className="text-xs text-gray-500 py-2">종목 없음</p>
        )}
      </div>

      {/* Order Stats */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        <div className="bg-gray-900 rounded-lg p-2.5 text-center">
          <p className="text-xs text-gray-500">{t.recipes.totalOrders}</p>
          <p className="text-lg font-bold text-white">{orders.length}</p>
        </div>
        <div className="bg-gray-900 rounded-lg p-2.5 text-center">
          <p className="text-xs text-gray-500">{t.recipes.successOrders}</p>
          <p className="text-lg font-bold text-green-400">{successCount}</p>
        </div>
        <div className="bg-gray-900 rounded-lg p-2.5 text-center">
          <p className="text-xs text-gray-500">{t.recipes.failedOrders}</p>
          <p className="text-lg font-bold text-red-400">{failCount}</p>
        </div>
      </div>

      {/* Recent Orders with Stock Names */}
      {orders.length > 0 && (
        <div className="mb-4">
          <p className="text-xs text-gray-500 mb-2">{t.recipes.recentOrders}</p>
          <div className="space-y-1">
            {orders.slice(0, 3).map((order) => (
              <div
                key={order.id}
                className="flex items-center justify-between text-xs bg-gray-900 rounded-lg px-2.5 py-1.5"
              >
                <span className="text-gray-300 truncate max-w-[100px]">
                  {stockNames[order.stock_code] || order.stock_code}
                </span>
                <span
                  className={
                    order.side === "buy" ? "text-green-400" : "text-red-400"
                  }
                >
                  {order.side === "buy" ? "BUY" : "SELL"}{" "}
                  {order.quantity.toLocaleString()}
                </span>
                <span
                  className={`${
                    order.status === "filled" || order.status === "submitted"
                      ? "text-green-400"
                      : order.status === "failed"
                        ? "text-red-400"
                        : "text-yellow-400"
                  }`}
                >
                  {order.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* View Detail */}
      <button
        onClick={onViewDetail}
        className="w-full bg-gray-700 hover:bg-gray-600 text-gray-300 py-2 rounded-lg text-sm transition-colors"
      >
        {t.recipes.viewDetail}
      </button>
    </div>
  );
}
