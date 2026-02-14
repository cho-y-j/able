"use client";

import { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { useI18n } from "@/i18n";
import { StrategySearchPanel } from "./_components/StrategySearchPanel";
import { StrategyStockGroup } from "./_components/StrategyStockGroup";
import { Strategy } from "./_components/StrategyCard";

export default function StrategiesPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [activeStockCode, setActiveStockCode] = useState<string | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStrategies();
  }, []);

  const fetchStrategies = async (stockCode?: string) => {
    try {
      const params = stockCode ? { stock_code: stockCode } : {};
      const { data } = await api.get("/strategies", { params });
      setStrategies(data);
    } catch {
      /* */
    } finally {
      setLoading(false);
    }
  };

  const handleSearchComplete = (stockCode: string) => {
    setActiveStockCode(stockCode);
    fetchStrategies(); // fetch all to show grouped
    setExpandedGroups(new Set([stockCode])); // auto-expand searched stock
  };

  const toggleAutoTrading = async (
    e: React.MouseEvent,
    id: string,
    isActive: boolean
  ) => {
    e.stopPropagation();
    try {
      if (isActive) await api.post(`/strategies/${id}/deactivate`);
      else await api.post(`/strategies/${id}/activate`);
      fetchStrategies();
    } catch {
      alert(t.strategies.toggleFailed);
    }
  };

  const deleteStrategy = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm("이 전략을 삭제하시겠습니까?")) return;
    try {
      await api.delete(`/strategies/${id}`);
      fetchStrategies();
    } catch {
      /* */
    }
  };

  const navigateToStrategy = (id: string) => {
    router.push(`/dashboard/strategies/${id}`);
  };

  // Group strategies by stock_code
  const groupedStrategies = useMemo(() => {
    const groups: Record<string, Strategy[]> = {};
    strategies.forEach((s) => {
      if (!groups[s.stock_code]) groups[s.stock_code] = [];
      groups[s.stock_code].push(s);
    });
    return groups;
  }, [strategies]);

  // Order stock codes: active stock first, then the rest
  const stockCodes = useMemo(() => {
    const codes = Object.keys(groupedStrategies);
    if (activeStockCode && codes.includes(activeStockCode)) {
      return [activeStockCode, ...codes.filter((c) => c !== activeStockCode)];
    }
    return codes;
  }, [groupedStrategies, activeStockCode]);

  const toggleGroup = (code: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">{t.strategies.title}</h2>

      {/* Search Panel */}
      <StrategySearchPanel
        onSearchComplete={handleSearchComplete}
        onNavigate={navigateToStrategy}
      />

      {/* Strategy List */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">
            {t.strategies.myStrategies} ({strategies.length})
          </h3>
          {strategies.length > 0 && (
            <p className="text-xs text-gray-500">
              클릭하면 상세 분석 페이지로 이동합니다
            </p>
          )}
        </div>

        {/* Stock filter chips */}
        {strategies.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            <button
              onClick={() => {
                setActiveStockCode(null);
                fetchStrategies();
              }}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                !activeStockCode
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:bg-gray-700"
              }`}
            >
              전체 ({strategies.length})
            </button>
            {stockCodes.map((code) => {
              const group = groupedStrategies[code];
              const name = group[0]?.stock_name;
              return (
                <button
                  key={code}
                  onClick={() => {
                    setActiveStockCode(code);
                    setExpandedGroups(new Set([code]));
                  }}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                    activeStockCode === code
                      ? "bg-blue-600 text-white"
                      : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                  }`}
                >
                  {name || code} ({group.length})
                </button>
              );
            })}
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-20 bg-gray-800 rounded-lg animate-pulse"
              />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!loading && strategies.length === 0 && (
          <div className="text-center py-8">
            <div className="text-gray-600 text-4xl mb-3">&#x1F50D;</div>
            <p className="text-gray-500 text-sm">{t.strategies.noStrategies}</p>
          </div>
        )}

        {/* Stock groups */}
        {!loading && strategies.length > 0 && (
          <div className="space-y-3">
            {stockCodes
              .filter(
                (code) => !activeStockCode || code === activeStockCode
              )
              .map((code) => {
                const group = groupedStrategies[code];
                const stockName = group[0]?.stock_name ?? null;
                return (
                  <StrategyStockGroup
                    key={code}
                    stockCode={code}
                    stockName={stockName}
                    strategies={group}
                    isExpanded={expandedGroups.has(code)}
                    onToggle={() => toggleGroup(code)}
                    onNavigate={navigateToStrategy}
                    onToggleAutoTrading={toggleAutoTrading}
                    onDelete={deleteStrategy}
                  />
                );
              })}
          </div>
        )}
      </div>
    </div>
  );
}
