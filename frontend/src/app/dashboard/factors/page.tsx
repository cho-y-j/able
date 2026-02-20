"use client";

import { useState, useCallback, useEffect } from "react";
import api from "@/lib/api";
import { useI18n } from "@/i18n";
import { StockAutocomplete } from "@/components/StockAutocomplete";

interface FactorValue {
  factor_name: string;
  value: number;
  category?: string;
}

interface FactorCatalogItem {
  name: string;
  category: string;
  description: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  momentum: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  trend: "bg-green-500/20 text-green-400 border-green-500/30",
  volatility: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  volume: "bg-blue-500/20 text-blue-400 border-blue-500/30",
};

const CATEGORY_LABELS: Record<string, string> = {
  momentum: "Momentum",
  trend: "Trend",
  volatility: "Volatility",
  volume: "Volume",
};

export default function FactorsPage() {
  const { t } = useI18n();
  const [stockCode, setStockCode] = useState("");
  const [stockName, setStockName] = useState("");
  const [factors, setFactors] = useState<FactorValue[]>([]);
  const [catalog, setCatalog] = useState<FactorCatalogItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string>("all");

  // Fetch catalog on mount
  useEffect(() => {
    api.get("/factors/catalog").then((r) => setCatalog(r.data)).catch(() => {});
  }, []);

  const fetchFactors = useCallback(async (code: string) => {
    if (!code) return;
    setLoading(true);
    try {
      const resp = await api.get(`/factors/latest/${code}`);
      const data: FactorValue[] = resp.data.factors || [];
      // Enrich with catalog category
      const catMap = Object.fromEntries(catalog.map((c) => [c.name, c.category]));
      const enriched = data.map((f) => ({ ...f, category: catMap[f.factor_name] || "" }));
      setFactors(enriched);
    } catch {
      setFactors([]);
    } finally {
      setLoading(false);
    }
  }, [catalog]);

  const handleSelect = useCallback(
    (code: string, name?: string) => {
      setStockCode(code);
      setStockName(name || code);
      fetchFactors(code);
    },
    [fetchFactors]
  );

  const categories = ["all", ...new Set(catalog.map((c) => c.category))];
  const filtered = activeCategory === "all" ? factors : factors.filter((f) => f.category === activeCategory);

  // Factor value color
  const valueColor = (name: string, val: number) => {
    if (name.includes("rsi") || name.includes("stochastic") || name.includes("mfi") || name.includes("williams")) {
      if (val < 30) return "text-red-400";
      if (val > 70) return "text-blue-400";
    }
    if (name === "macd_signal_cross") {
      if (val > 0) return "text-red-400";
      if (val < 0) return "text-blue-400";
    }
    if (name.includes("rvol") || name.includes("volume_ma") || name.includes("vol_spike")) {
      if (val > 2) return "text-yellow-400";
    }
    return "text-gray-200";
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t.factors?.title || "Factor Store"}</h1>
        <p className="text-sm text-gray-400 mt-1">
          {t.factors?.description || "View technical factor snapshots per stock"}
        </p>
      </div>

      {/* Stock selector */}
      <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
        <div className="flex items-end gap-4">
          <div className="flex-1 min-w-[200px]">
            <label className="text-xs text-gray-400 mb-1 block">Stock</label>
            <StockAutocomplete onSelect={handleSelect} />
          </div>
          {stockCode && (
            <div className="text-sm text-gray-400">
              {stockName} <span className="text-gray-600">{stockCode}</span>
            </div>
          )}
        </div>
      </div>

      {/* Category tabs */}
      {factors.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                activeCategory === cat
                  ? "bg-indigo-600 border-indigo-500 text-white"
                  : "bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600"
              }`}
            >
              {cat === "all" ? "All" : CATEGORY_LABELS[cat] || cat} ({cat === "all" ? factors.length : factors.filter((f) => f.category === cat).length})
            </button>
          ))}
        </div>
      )}

      {/* Factor Grid */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading...</div>
      ) : filtered.length > 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {filtered.map((f) => {
            const catInfo = catalog.find((c) => c.name === f.factor_name);
            return (
              <div key={f.factor_name} className="bg-gray-900 rounded-xl p-4 border border-gray-800">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-gray-500 truncate">{f.factor_name}</span>
                  {f.category && (
                    <span className={`px-1.5 py-0.5 text-[10px] rounded border ${CATEGORY_COLORS[f.category] || "bg-gray-600/20 text-gray-400"}`}>
                      {f.category}
                    </span>
                  )}
                </div>
                <div className={`text-xl font-mono font-bold ${valueColor(f.factor_name, f.value)}`}>
                  {f.value.toFixed(2)}
                </div>
                {catInfo && (
                  <div className="text-[10px] text-gray-600 mt-1 truncate">{catInfo.description}</div>
                )}
              </div>
            );
          })}
        </div>
      ) : stockCode ? (
        <div className="text-center py-12 text-gray-500">
          No factor data available for {stockName}. Run factor collection first.
        </div>
      ) : (
        <div className="text-center py-20 text-gray-500">
          <div className="text-4xl mb-4">F</div>
          <p>Select a stock to view factor data</p>
        </div>
      )}

      {/* Factor Catalog */}
      {!stockCode && catalog.length > 0 && (
        <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">Available Factors ({catalog.length})</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {catalog.map((f) => (
              <div key={f.name} className="flex items-center gap-2 p-2 bg-gray-800/30 rounded-lg">
                <span className={`px-1.5 py-0.5 text-[10px] rounded border ${CATEGORY_COLORS[f.category] || "bg-gray-600/20 text-gray-400"}`}>
                  {f.category}
                </span>
                <div>
                  <span className="text-sm font-mono">{f.name}</span>
                  {f.description && <span className="text-[10px] text-gray-600 ml-2">{f.description}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
