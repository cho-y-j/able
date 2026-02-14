"use client";

import { ChevronDown } from "lucide-react";
import { GradeBadge } from "./GradeBadge";
import { StrategyCard, Strategy } from "./StrategyCard";

interface StrategyStockGroupProps {
  stockCode: string;
  stockName: string | null;
  strategies: Strategy[];
  isExpanded: boolean;
  onToggle: () => void;
  onNavigate: (id: string) => void;
  onToggleAutoTrading: (e: React.MouseEvent, id: string, isActive: boolean) => void;
  onDelete: (e: React.MouseEvent, id: string) => void;
}

export function StrategyStockGroup({
  stockCode,
  stockName,
  strategies,
  isExpanded,
  onToggle,
  onNavigate,
  onToggleAutoTrading,
  onDelete,
}: StrategyStockGroupProps) {
  const bestScore = strategies.reduce<number | null>((best, s) => {
    if (s.composite_score === null) return best;
    if (best === null) return s.composite_score;
    return s.composite_score > best ? s.composite_score : best;
  }, null);

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
      {/* Header */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-5 py-4 hover:bg-gray-800/50 transition-colors"
      >
        <span className="text-lg">📈</span>
        <span className="font-mono text-sm text-gray-400">{stockCode}</span>
        {stockName && (
          <span className="font-medium text-white">{stockName}</span>
        )}
        <span className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded-full">
          {strategies.length}개 전략
        </span>
        {bestScore !== null && (
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-gray-500">최고</span>
            <GradeBadge score={bestScore} size="sm" />
          </div>
        )}
        <div className="ml-auto">
          <ChevronDown
            className={`w-5 h-5 text-gray-500 transition-transform duration-200 ${
              isExpanded ? "rotate-180" : ""
            }`}
          />
        </div>
      </button>

      {/* Body */}
      <div
        className={`transition-all duration-300 ease-in-out overflow-hidden ${
          isExpanded ? "max-h-[5000px] opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <div className="px-5 pb-4 space-y-2">
          {strategies.map((s) => (
            <StrategyCard
              key={s.id}
              strategy={s}
              onNavigate={onNavigate}
              onToggleAutoTrading={onToggleAutoTrading}
              onDelete={onDelete}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
