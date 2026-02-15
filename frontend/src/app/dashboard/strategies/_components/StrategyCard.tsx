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
  onCreateRecipe: (e: React.MouseEvent, id: string) => void;
  onDelete: (e: React.MouseEvent, id: string) => void;
}

export interface StrategyTypeInfo {
  label: string;
  category: "추세추종" | "모멘텀" | "변동성" | "복합";
  description: string;
}

export const STRATEGY_TYPE_INFO: Record<string, StrategyTypeInfo> = {
  // ── 추세추종 (Trend Following) ─────────────────────────
  sma_crossover: {
    label: "SMA 크로스",
    category: "추세추종",
    description: "단기 이동평균이 장기 이동평균을 상향 돌파하면 매수, 하향 돌파하면 매도. 가장 기본적인 추세 전략.",
  },
  ema_crossover: {
    label: "EMA 크로스",
    category: "추세추종",
    description: "지수이동평균(EMA) 크로스. SMA보다 최근 가격에 더 민감하게 반응하여 빠른 추세 전환을 포착.",
  },
  macd_crossover: {
    label: "MACD 크로스",
    category: "추세추종",
    description: "MACD 선이 시그널 선을 상향 돌파하면 매수. 추세의 방향과 강도를 동시에 측정하는 인기 지표.",
  },
  supertrend: {
    label: "슈퍼트렌드",
    category: "추세추종",
    description: "변동성(ATR) 기반 추세 지표. 가격이 밴드 위에 있으면 상승 추세, 아래면 하락 추세로 판단.",
  },
  ichimoku_cloud: {
    label: "일목균형표",
    category: "추세추종",
    description: "구름(Cloud) 위로 가격이 돌파하면 매수. 일본에서 개발된 종합 추세 분석 시스템.",
  },
  adx_trend: {
    label: "ADX 추세 확인",
    category: "추세추종",
    description: "ADX가 25 이상이면 강한 추세 존재. 추세의 '강도'를 측정하여 추세장에서만 진입.",
  },
  psar_reversal: {
    label: "파라볼릭 SAR",
    category: "추세추종",
    description: "가격 위/아래 점으로 표시되는 추세 반전 신호. 점이 가격 아래로 이동하면 매수 신호.",
  },
  donchian_breakout: {
    label: "돈치안 돌파",
    category: "추세추종",
    description: "N일 최고가 돌파 시 매수(터틀 트레이딩). 신고가 갱신 = 강한 상승 모멘텀으로 판단.",
  },
  atr_trailing_stop: {
    label: "ATR 추세추종",
    category: "추세추종",
    description: "변동성(ATR)에 따라 자동 조절되는 손절선. 변동성이 크면 손절폭도 넓어져 조기 청산 방지.",
  },
  // ── 모멘텀 (Momentum) ─────────────────────────────────
  rsi_mean_reversion: {
    label: "RSI 평균회귀",
    category: "모멘텀",
    description: "RSI가 과매도(30 이하)에서 반등하면 매수, 과매수(70 이상)에서 꺾이면 매도. 급락 후 반등 포착.",
  },
  stochastic_crossover: {
    label: "스토캐스틱",
    category: "모멘텀",
    description: "%K선이 %D선을 상향 돌파하면 매수. 현재 가격이 최근 범위에서 어디에 위치하는지 측정.",
  },
  cci_reversal: {
    label: "CCI 반전",
    category: "모멘텀",
    description: "CCI가 과매도(-100 이하)에서 반등하면 매수. 평균 가격 대비 현재 가격의 편차를 이용.",
  },
  williams_r_signal: {
    label: "윌리엄스 %R",
    category: "모멘텀",
    description: "%R이 -80 이하(과매도)에서 올라오면 매수. 최고가 대비 현재 가격 위치로 매수 타이밍 포착.",
  },
  mfi_signal: {
    label: "MFI 시그널",
    category: "모멘텀",
    description: "거래량 가중 RSI. 가격+거래량 모두 분석하여 실제 자금 유입/유출 방향을 파악.",
  },
  roc_momentum: {
    label: "ROC 모멘텀",
    category: "모멘텀",
    description: "N일 전 대비 변화율(Rate of Change)이 임계값을 돌파하면 매수. 가격 상승 가속도 측정.",
  },
  // ── 변동성 (Volatility) ────────────────────────────────
  bb_bounce: {
    label: "볼린저 반등",
    category: "변동성",
    description: "볼린저 밴드 하단 터치 후 반등 시 매수. 가격이 평균에서 크게 벗어나면 되돌아온다는 원리.",
  },
  bb_width_breakout: {
    label: "볼린저 돌파",
    category: "변동성",
    description: "볼린저 밴드가 극도로 좁아진(변동성 수축) 후 상단 돌파 시 매수. 큰 움직임 전조 포착.",
  },
  keltner_breakout: {
    label: "켈트너 돌파",
    category: "변동성",
    description: "켈트너 채널 상단 돌파 시 매수. ATR 기반 채널로 추세 돌파의 신뢰도를 측정.",
  },
  squeeze_momentum: {
    label: "스퀴즈 모멘텀",
    category: "변동성",
    description: "볼린저가 켈트너 안에 들어가면 '스퀴즈'(압축). 스퀴즈 해제 + 상승 모멘텀이면 매수.",
  },
  // ── 복합 (Composite) ──────────────────────────────────
  elder_impulse: {
    label: "엘더 임펄스",
    category: "복합",
    description: "EMA 방향 + MACD 변화를 동시 확인. 둘 다 상승이면 초록(강한 매수), 둘 다 하락이면 빨강(매도).",
  },
  multi_ma_vote: {
    label: "다중 이동평균",
    category: "복합",
    description: "3개 이동평균이 모두 정배열(단기>중기>장기)이면 매수. 여러 지표의 '다수결' 방식.",
  },
  rsi_macd_combo: {
    label: "RSI+MACD 콤보",
    category: "복합",
    description: "RSI가 과매도 탈출 + MACD 골든크로스가 동시에 나타나면 매수. 두 신호의 교집합으로 신뢰도 향상.",
  },
  obv_trend: {
    label: "OBV 추세 확인",
    category: "복합",
    description: "거래량 누적(OBV)이 상승 추세이면 매수. 가격보다 거래량이 먼저 방향을 바꾼다는 원리 활용.",
  },
};

export const STRATEGY_TYPE_LABELS: Record<string, string> = Object.fromEntries(
  Object.entries(STRATEGY_TYPE_INFO).map(([k, v]) => [k, v.label])
);

const CATEGORY_COLORS: Record<string, string> = {
  "추세추종": "bg-blue-500/20 text-blue-300",
  "모멘텀": "bg-purple-500/20 text-purple-300",
  "변동성": "bg-orange-500/20 text-orange-300",
  "복합": "bg-emerald-500/20 text-emerald-300",
};

export function statusLabel(status: string): string {
  switch (status) {
    case "active":
      return "활성";
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
  onCreateRecipe,
  onDelete,
}: StrategyCardProps) {
  const vr = s.validation_results;
  const bt = vr?.backtest;
  const gi = gradeInfo(s.composite_score);
  const typeInfo = STRATEGY_TYPE_INFO[s.strategy_type];

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
        <div className="flex items-center gap-2 mb-0.5">
          <h4 className="font-medium text-white truncate">
            {STRATEGY_TYPE_LABELS[s.strategy_type] || s.strategy_type}
          </h4>
          {typeInfo && (
            <span className={`text-xs px-1.5 py-0.5 rounded ${CATEGORY_COLORS[typeInfo.category] || "bg-gray-700 text-gray-400"}`}>
              {typeInfo.category}
            </span>
          )}
          <span className="text-xs text-gray-500">
            {s.stock_name ? `${s.stock_name} (${s.stock_code})` : s.stock_code}
          </span>
        </div>
        {typeInfo && (
          <p className="text-xs text-gray-500 mb-1.5 line-clamp-1">{typeInfo.description}</p>
        )}

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
          onClick={(e) => onCreateRecipe(e, s.id)}
          className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors bg-purple-600/20 text-purple-400 hover:bg-purple-600/30"
        >
          레시피 만들기
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
