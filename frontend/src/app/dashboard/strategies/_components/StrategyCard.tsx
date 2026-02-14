"use client";

import { GradeBadge, gradeInfo } from "./GradeBadge";

export interface Strategy {
  id: string;
  name: string;
  stock_code: string;
  stock_name: string | null;
  strategy_type: string;
  composite_score: number | null;
  validation_results: {
    wfa?: { wfa_score: number };
    mc?: { mc_score: number };
    oos?: { oos_score: number };
    backtest?: Record<string, number>;
  } | null;
  status: string;
  is_auto_trading: boolean;
  created_at: string;
}

export interface StrategyCardProps {
  strategy: Strategy;
  onNavigate: (id: string) => void;
  onToggleAutoTrading: (e: React.MouseEvent, id: string, isActive: boolean) => void;
  onDelete: (e: React.MouseEvent, id: string) => void;
}

export const STRATEGY_TYPE_LABELS: Record<string, string> = {
  elder_impulse: "엘더 임펄스",
  roc_momentum: "ROC 모멘텀",
  atr_trailing_stop: "ATR 추세추종",
  multi_ma_vote: "다중 이동평균",
  macd_crossover: "MACD 크로스",
  rsi_mean_reversion: "RSI 평균회귀",
  bb_width_breakout: "볼린저 돌파",
  cci_reversal: "CCI 반전",
  stochastic_crossover: "스토캐스틱",
  squeeze_momentum: "스퀴즈 모멘텀",
  sma_crossover: "SMA 크로스",
  ema_crossover: "EMA 크로스",
  mfi_signal: "MFI 시그널",
  williams_r_signal: "윌리엄스 %R",
  rsi_macd_combo: "RSI+MACD 콤보",
};

export function statusLabel(status: string): string {
  switch (status) {
    case "active":
      return "자동매매 중";
    case "validated":
      return "검증 완료";
    case "draft":
      return "초안";
    case "paused":
      return "일시정지";
    default:
      return status;
  }
}

export function StrategyCard({
  strategy: s,
  onNavigate,
  onToggleAutoTrading,
  onDelete,
}: StrategyCardProps) {
  const vr = s.validation_results;
  const bt = vr?.backtest;
  const gi = gradeInfo(s.composite_score);

  const statusClasses =
    s.status === "active"
      ? "bg-green-900/50 text-green-400 border-green-800"
      : s.status === "validated"
        ? "bg-blue-900/50 text-blue-400 border-blue-800"
        : s.status === "paused"
          ? "bg-yellow-900/50 text-yellow-400 border-yellow-800"
          : "bg-gray-700 text-gray-400 border-gray-600";

  return (
    <div
      onClick={() => onNavigate(s.id)}
      className="flex items-center gap-4 p-4 bg-gray-800 rounded-lg cursor-pointer transition-all duration-200 border border-transparent hover:border-gray-600 hover:translate-x-1 hover:shadow-lg hover:shadow-blue-900/10"
    >
      {/* Left: Grade Badge */}
      <GradeBadge score={s.composite_score} size="lg" />

      {/* Center: Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1.5">
          <h4 className="font-medium text-white truncate">
            {STRATEGY_TYPE_LABELS[s.strategy_type] || s.strategy_type}
          </h4>
          <span className="text-xs text-gray-500">
            {s.stock_name ? `${s.stock_name} (${s.stock_code})` : s.stock_code}
          </span>
        </div>

        {/* Metric pills */}
        <div className="flex items-center gap-2 flex-wrap">
          {bt && (
            <>
              <span
                className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                  (bt.total_return || 0) >= 0
                    ? "bg-green-900/40 text-green-400"
                    : "bg-red-900/40 text-red-400"
                }`}
              >
                수익률 {(bt.total_return || 0) >= 0 ? "+" : ""}
                {(bt.total_return || 0).toFixed(1)}%
              </span>
              <span
                className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                  (bt.sharpe_ratio || 0) >= 1
                    ? "bg-blue-900/40 text-blue-400"
                    : "bg-gray-700 text-gray-400"
                }`}
              >
                샤프 {(bt.sharpe_ratio || 0).toFixed(2)}
              </span>
              <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-gray-700 text-gray-400">
                MDD {(bt.max_drawdown || 0).toFixed(1)}%
              </span>
            </>
          )}
          {s.composite_score && !bt && (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-blue-900/40 text-blue-400">
              종합점수 {s.composite_score.toFixed(1)}점
            </span>
          )}
          {s.composite_score !== null && (
            <span className="text-xs text-gray-600">{gi.label}</span>
          )}
        </div>
      </div>

      {/* Right: Status + Actions */}
      <div className="flex items-center gap-3 shrink-0">
        <span className={`text-xs px-2.5 py-1 rounded-full border ${statusClasses} flex items-center gap-1.5`}>
          {s.status === "active" && (
            <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
          )}
          {statusLabel(s.status)}
        </span>

        <button
          onClick={(e) => onToggleAutoTrading(e, s.id, s.is_auto_trading)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            s.is_auto_trading
              ? "bg-red-600/20 text-red-400 hover:bg-red-600/30"
              : "bg-green-600/20 text-green-400 hover:bg-green-600/30"
          }`}
        >
          {s.is_auto_trading ? "매매 중지" : "자동매매 시작"}
        </button>

        <button
          onClick={(e) => onDelete(e, s.id)}
          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-700 text-gray-400 hover:bg-red-600/20 hover:text-red-400 transition-colors"
        >
          삭제
        </button>
      </div>
    </div>
  );
}
