"use client";

interface Recipe {
  id: string;
  name: string;
  description: string | null;
  signal_config: {
    combinator: string;
    signals: Array<{ type: string; strategy_type?: string; weight?: number }>;
  };
  stock_codes: string[];
  is_active: boolean;
  is_template: boolean;
  created_at: string;
}

interface RecipeCardProps {
  recipe: Recipe;
  onClick: () => void;
  onActivate: (e: React.MouseEvent) => void;
  onDelete: (e: React.MouseEvent) => void;
}

export type { Recipe };

export default function RecipeCard({ recipe, onClick, onActivate, onDelete }: RecipeCardProps) {
  const signalCount = recipe.signal_config?.signals?.length || 0;
  const combinator = recipe.signal_config?.combinator || "AND";

  return (
    <div
      onClick={onClick}
      className="bg-gray-800 border border-gray-700 rounded-xl p-5 cursor-pointer hover:border-blue-500/50 hover:translate-x-1 transition-all duration-200 group"
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
          {recipe.is_active && (
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500" />
            </span>
          )}
          {recipe.is_template && (
            <span className="bg-purple-500/20 text-purple-400 text-xs px-2 py-0.5 rounded-full">
              템플릿
            </span>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-3">
        <span className="bg-blue-500/20 text-blue-400 text-xs px-2.5 py-1 rounded-full">
          {signalCount}개 시그널
        </span>
        <span className="bg-gray-700 text-gray-300 text-xs px-2.5 py-1 rounded-full">
          {combinator}
        </span>
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
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-gray-700">
        <span className="text-xs text-gray-500">
          {new Date(recipe.created_at).toLocaleDateString("ko-KR")}
        </span>
        <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={onActivate}
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
            className="text-xs px-3 py-1.5 rounded-lg bg-gray-700 text-gray-400 hover:bg-red-500/20 hover:text-red-400 transition-colors"
          >
            삭제
          </button>
        </div>
      </div>
    </div>
  );
}
