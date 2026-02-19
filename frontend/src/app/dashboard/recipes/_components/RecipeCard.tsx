"use client";

import {
  SIGNAL_INFO,
  CATEGORY_COLORS,
  getSignalLabel,
} from "@/lib/signalMetadata";
import type { Recipe } from "../types";

interface RecipeCardProps {
  recipe: Recipe;
  onClick: () => void;
  onActivate: (e: React.MouseEvent) => void;
  onDelete: (e: React.MouseEvent) => void;
}

function CombinatorBadge({ combinator, minAgree }: { combinator: string; minAgree?: number }) {
  const label =
    combinator === "AND" ? "AND" : combinator === "OR" ? "OR" : `${minAgree || 2}+`;
  return (
    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-gray-600 text-gray-300">
      {label}
    </span>
  );
}

export default function RecipeCard({ recipe, onClick, onActivate, onDelete }: RecipeCardProps) {
  const signals = recipe.signal_config?.signals || [];
  const combinator = recipe.signal_config?.combinator || "AND";
  const minAgree = recipe.signal_config?.min_agree;
  const risk = recipe.risk_config;

  return (
    <div
      onClick={onClick}
      className="bg-gray-800 border border-gray-700 rounded-xl p-5 cursor-pointer hover:border-blue-500/50 hover:translate-x-1 transition-all duration-200 group"
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onClick()}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-white font-semibold truncate group-hover:text-blue-400 transition-colors">
            {recipe.name}
          </h3>
          {recipe.description && (
            <p className="text-gray-400 text-sm mt-1 line-clamp-2">{recipe.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2 ml-3 flex-shrink-0">
          {recipe.is_active && recipe.auto_execute && (
            <span
              className="bg-green-500/20 text-green-400 text-xs px-2 py-0.5 rounded-full flex items-center gap-1"
              title="신호 감지 시 자동으로 주문이 실행됩니다"
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
              </span>
              자동매매
            </span>
          )}
          {recipe.is_active && !recipe.auto_execute && (
            <span
              className="bg-blue-500/20 text-blue-400 text-xs px-2 py-0.5 rounded-full"
              title="신호를 감지하고 알림만 보냅니다. 주문은 수동으로 실행하세요."
            >
              모니터링
            </span>
          )}
          {recipe.is_template && (
            <span className="bg-purple-500/20 text-purple-400 text-xs px-2 py-0.5 rounded-full">
              템플릿
            </span>
          )}
        </div>
      </div>

      {/* Signal badges with combinator separators */}
      <div className="flex flex-wrap items-center gap-1.5 mb-3">
        {signals.map((sig, i) => {
          const name = sig.strategy_type || sig.type;
          const info = SIGNAL_INFO[name];
          const catColor = info
            ? (CATEGORY_COLORS[info.category] || "bg-gray-700 text-gray-400")
            : "bg-gray-700 text-gray-400";
          return (
            <span key={i} className="contents">
              {i > 0 && (
                <CombinatorBadge combinator={combinator} minAgree={minAgree} />
              )}
              <span className={`text-xs px-2 py-0.5 rounded-full border ${catColor}`}>
                {getSignalLabel(name)}
              </span>
            </span>
          );
        })}
        {signals.length === 0 && (
          <span className="text-xs text-gray-500">시그널 없음</span>
        )}
      </div>

      {/* Stock codes + risk summary row */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        {recipe.stock_codes?.slice(0, 3).map((code) => (
          <span key={code} className="bg-gray-700 text-gray-400 text-xs px-2.5 py-1 rounded-full">
            {code}
          </span>
        ))}
        {(recipe.stock_codes?.length || 0) > 3 && (
          <span className="text-gray-500 text-xs py-1">
            +{recipe.stock_codes.length - 3}
          </span>
        )}
        {risk && (risk.stop_loss || risk.take_profit) && (
          <span className="text-xs text-gray-500 ml-auto">
            {risk.stop_loss ? `손절 ${risk.stop_loss}%` : ""}
            {risk.stop_loss && risk.take_profit ? " / " : ""}
            {risk.take_profit ? `익절 ${risk.take_profit}%` : ""}
          </span>
        )}
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-gray-700">
        <span className="text-xs text-gray-500">
          {recipe.created_at ? new Date(recipe.created_at).toLocaleDateString("ko-KR") : ""}
        </span>
        <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={onActivate}
            aria-label={recipe.is_active ? "레시피 중지" : "레시피 활성화"}
            className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
              recipe.is_active
                ? "bg-red-500/20 text-red-400 hover:bg-red-500/30"
                : "bg-green-500/20 text-green-400 hover:bg-green-500/30"
            }`}
          >
            {recipe.is_active ? "중지" : "활성화"}
          </button>
          <button
            onClick={onDelete}
            aria-label="레시피 삭제"
            className="text-xs px-3 py-1.5 rounded-lg bg-gray-700 text-gray-400 hover:bg-red-500/20 hover:text-red-400 transition-colors"
          >
            삭제
          </button>
        </div>
      </div>
    </div>
  );
}
