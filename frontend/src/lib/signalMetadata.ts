/**
 * Unified signal metadata — single source of truth for signal labels,
 * descriptions, categories, parameter ranges, and colors.
 *
 * All 24 signal names match backend `register_signal()` names exactly.
 */

// ── Types ────────────────────────────────────────────────────────────

export interface SignalInfo {
  label: string;
  category: "추세추종" | "모멘텀" | "변동성" | "거래량" | "복합";
  description: string;
}

export interface ParamRange {
  label: string;
  description: string;
  min: number;
  max: number;
  step: number;
  default: number;
}

// ── Signal Info (24 signals, 1:1 with backend registry) ──────────────

export const SIGNAL_INFO: Record<string, SignalInfo> = {
  // ── 추세추종 (Trend Following) ──
  sma_crossover: {
    label: "SMA 크로스오버",
    category: "추세추종",
    description:
      "단기 이동평균이 장기 이동평균을 상향 돌파하면 매수, 하향 돌파하면 매도. 가장 기본적인 추세 전략.",
  },
  ema_crossover: {
    label: "EMA 크로스오버",
    category: "추세추종",
    description:
      "지수이동평균(EMA) 크로스. SMA보다 최근 가격에 더 민감하게 반응하여 빠른 추세 전환을 포착.",
  },
  macd_crossover: {
    label: "MACD 크로스",
    category: "추세추종",
    description:
      "MACD 선이 시그널 선을 상향 돌파하면 매수. 추세의 방향과 강도를 동시에 측정하는 인기 지표.",
  },
  supertrend: {
    label: "슈퍼트렌드",
    category: "추세추종",
    description:
      "변동성(ATR) 기반 추세 지표. 가격이 밴드 위에 있으면 상승 추세, 아래면 하락 추세로 판단.",
  },
  ichimoku_cloud: {
    label: "일목균형표",
    category: "추세추종",
    description:
      "구름(Cloud) 위로 가격이 돌파하면 매수. 일본에서 개발된 종합 추세 분석 시스템.",
  },
  adx_trend: {
    label: "ADX 추세 확인",
    category: "추세추종",
    description:
      "ADX가 25 이상이면 강한 추세 존재. 추세의 '강도'를 측정하여 추세장에서만 진입.",
  },
  psar_reversal: {
    label: "파라볼릭 SAR",
    category: "추세추종",
    description:
      "가격 위/아래 점으로 표시되는 추세 반전 신호. 점이 가격 아래로 이동하면 매수 신호.",
  },
  donchian_breakout: {
    label: "돈치안 돌파",
    category: "추세추종",
    description:
      "N일 최고가 돌파 시 매수(터틀 트레이딩). 신고가 갱신 = 강한 상승 모멘텀으로 판단.",
  },

  // ── 모멘텀 (Momentum) ──
  rsi_mean_reversion: {
    label: "RSI 평균회귀",
    category: "모멘텀",
    description:
      "RSI가 과매도(30 이하)에서 반등하면 매수, 과매수(70 이상)에서 꺾이면 매도. 급락 후 반등 포착.",
  },
  stochastic_crossover: {
    label: "스토캐스틱",
    category: "모멘텀",
    description:
      "%K선이 %D선을 상향 돌파하면 매수. 현재 가격이 최근 범위에서 어디에 위치하는지 측정.",
  },
  cci_reversal: {
    label: "CCI 반전",
    category: "모멘텀",
    description:
      "CCI가 과매도(-100 이하)에서 반등하면 매수. 평균 가격 대비 현재 가격의 편차를 이용.",
  },
  williams_r_signal: {
    label: "윌리엄스 %R",
    category: "모멘텀",
    description:
      "%R이 -80 이하(과매도)에서 올라오면 매수. 최고가 대비 현재 가격 위치로 매수 타이밍 포착.",
  },
  mfi_signal: {
    label: "MFI 시그널",
    category: "모멘텀",
    description:
      "거래량 가중 RSI. 가격+거래량 모두 분석하여 실제 자금 유입/유출 방향을 파악.",
  },
  roc_momentum: {
    label: "ROC 모멘텀",
    category: "모멘텀",
    description:
      "N일 전 대비 변화율(Rate of Change)이 임계값을 돌파하면 매수. 가격 상승 가속도 측정.",
  },

  // ── 변동성 (Volatility) ──
  bb_bounce: {
    label: "볼린저 반등",
    category: "변동성",
    description:
      "볼린저 밴드 하단 터치 후 반등 시 매수. 가격이 평균에서 크게 벗어나면 되돌아온다는 원리.",
  },
  bb_width_breakout: {
    label: "볼린저 돌파",
    category: "변동성",
    description:
      "볼린저 밴드가 극도로 좁아진(변동성 수축) 후 상단 돌파 시 매수. 큰 움직임 전조 포착.",
  },
  keltner_breakout: {
    label: "켈트너 돌파",
    category: "변동성",
    description:
      "켈트너 채널 상단 돌파 시 매수. ATR 기반 채널로 추세 돌파의 신뢰도를 측정.",
  },
  squeeze_momentum: {
    label: "스퀴즈 모멘텀",
    category: "변동성",
    description:
      "볼린저가 켈트너 안에 들어가면 '스퀴즈'(압축). 스퀴즈 해제 + 상승 모멘텀이면 매수.",
  },
  atr_trailing_stop: {
    label: "ATR 추세추종",
    category: "변동성",
    description:
      "변동성(ATR)에 따라 자동 조절되는 손절선. 변동성이 크면 손절폭도 넓어져 조기 청산 방지.",
  },

  // ── 거래량 (Volume) ──
  volume_spike: {
    label: "거래량 폭증 (RVOL)",
    category: "거래량",
    description:
      "평균 거래량 대비 급증(RVOL) 감지. 거래량 폭증은 큰 가격 변동의 선행 지표.",
  },
  vwap_deviation: {
    label: "VWAP 이탈",
    category: "거래량",
    description:
      "거래량 가중 평균가(VWAP) 대비 가격 이탈 감지. VWAP 하단에서 반등 시 매수 신호.",
  },
  volume_breakout: {
    label: "거래량+가격 돌파",
    category: "거래량",
    description:
      "가격이 N일 최고가를 돌파하면서 거래량도 급증할 때 매수. 가격+거래량 동시 확인.",
  },

  // ── 복합 (Composite) ──
  elder_impulse: {
    label: "엘더 임펄스",
    category: "복합",
    description:
      "EMA 방향 + MACD 변화를 동시 확인. 둘 다 상승이면 초록(강한 매수), 둘 다 하락이면 빨강(매도).",
  },
  multi_ma_vote: {
    label: "다중 이동평균",
    category: "복합",
    description:
      "3개 이동평균이 모두 정배열(단기>중기>장기)이면 매수. 여러 지표의 '다수결' 방식.",
  },
  rsi_macd_combo: {
    label: "RSI+MACD 콤보",
    category: "복합",
    description:
      "RSI가 과매도 탈출 + MACD 골든크로스가 동시에 나타나면 매수. 두 신호의 교집합으로 신뢰도 향상.",
  },
  obv_trend: {
    label: "OBV 추세 확인",
    category: "복합",
    description:
      "거래량 누적(OBV)이 상승 추세이면 매수. 가격보다 거래량이 먼저 방향을 바꾼다는 원리 활용.",
  },
};

// ── Categories (ordered, for signal selector UI) ─────────────────────

export const SIGNAL_CATEGORIES_ORDERED: Record<
  string,
  { label: string; signals: string[] }
> = {
  trend: {
    label: "추세 추종",
    signals: [
      "sma_crossover",
      "ema_crossover",
      "macd_crossover",
      "supertrend",
      "ichimoku_cloud",
      "adx_trend",
      "psar_reversal",
      "donchian_breakout",
    ],
  },
  momentum: {
    label: "모멘텀",
    signals: [
      "rsi_mean_reversion",
      "stochastic_crossover",
      "cci_reversal",
      "williams_r_signal",
      "mfi_signal",
      "roc_momentum",
    ],
  },
  volatility: {
    label: "변동성",
    signals: [
      "bb_bounce",
      "bb_width_breakout",
      "keltner_breakout",
      "squeeze_momentum",
      "atr_trailing_stop",
    ],
  },
  volume: {
    label: "거래량",
    signals: ["volume_spike", "vwap_deviation", "volume_breakout"],
  },
  composite: {
    label: "복합",
    signals: ["elder_impulse", "multi_ma_vote", "rsi_macd_combo", "obv_trend"],
  },
};

// ── Category Colors ──────────────────────────────────────────────────

export const CATEGORY_COLORS: Record<string, string> = {
  추세추종: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  모멘텀: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  변동성: "bg-orange-500/20 text-orange-300 border-orange-500/30",
  거래량: "bg-teal-500/20 text-teal-300 border-teal-500/30",
  복합: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
};

// ── Full Parameter Ranges (all 24 signals, matches backend param_space) ──

export const FULL_PARAM_RANGES: Record<
  string,
  Record<string, ParamRange>
> = {
  sma_crossover: {
    fast_period: { label: "빠른 이평선", description: "단기 이동평균 기간 (일)", min: 5, max: 30, step: 1, default: 10 },
    slow_period: { label: "느린 이평선", description: "장기 이동평균 기간 (일)", min: 30, max: 200, step: 5, default: 50 },
  },
  ema_crossover: {
    fast_period: { label: "빠른 EMA", description: "단기 지수이동평균 기간", min: 5, max: 25, step: 1, default: 12 },
    slow_period: { label: "느린 EMA", description: "장기 지수이동평균 기간", min: 25, max: 100, step: 5, default: 50 },
  },
  macd_crossover: {
    fast: { label: "빠른 기간", description: "MACD 단기 EMA 기간", min: 8, max: 16, step: 1, default: 12 },
    slow: { label: "느린 기간", description: "MACD 장기 EMA 기간", min: 20, max: 35, step: 1, default: 26 },
    signal: { label: "시그널 기간", description: "MACD 시그널 라인 기간", min: 5, max: 12, step: 1, default: 9 },
  },
  supertrend: {
    period: { label: "ATR 기간", description: "변동성 측정 기간", min: 7, max: 21, step: 1, default: 10 },
    multiplier: { label: "배수", description: "ATR 밴드 폭 배수", min: 1.5, max: 4.0, step: 0.1, default: 3.0 },
  },
  ichimoku_cloud: {
    tenkan: { label: "전환선", description: "전환선(단기) 기간", min: 7, max: 12, step: 1, default: 9 },
    kijun: { label: "기준선", description: "기준선(중기) 기간", min: 20, max: 35, step: 1, default: 26 },
  },
  adx_trend: {
    period: { label: "ADX 기간", description: "ADX 산출 기간", min: 10, max: 25, step: 1, default: 14 },
    adx_threshold: { label: "추세 임계값", description: "추세 판단 기준 ADX 값", min: 20, max: 35, step: 1, default: 25 },
  },
  psar_reversal: {
    af_start: { label: "초기 가속", description: "파라볼릭 SAR 초기 가속 계수", min: 0.01, max: 0.04, step: 0.005, default: 0.02 },
    af_max: { label: "최대 가속", description: "가속 계수 최대값", min: 0.15, max: 0.30, step: 0.01, default: 0.20 },
  },
  donchian_breakout: {
    entry_period: { label: "돌파 기간", description: "최고가/최저가 산출 기간", min: 10, max: 55, step: 5, default: 20 },
    exit_period: { label: "청산 기간", description: "청산 기준 기간", min: 5, max: 20, step: 1, default: 10 },
  },
  rsi_mean_reversion: {
    period: { label: "RSI 기간", description: "RSI 산출 기간 (일)", min: 5, max: 30, step: 1, default: 14 },
    oversold: { label: "과매도", description: "과매도 기준선 (매수 신호)", min: 15, max: 40, step: 1, default: 30 },
    overbought: { label: "과매수", description: "과매수 기준선 (매도 신호)", min: 60, max: 85, step: 1, default: 70 },
  },
  stochastic_crossover: {
    k_period: { label: "%K 기간", description: "스토캐스틱 %K 산출 기간", min: 5, max: 21, step: 1, default: 14 },
    d_period: { label: "%D 기간", description: "%K의 이동평균 기간", min: 3, max: 7, step: 1, default: 3 },
    oversold: { label: "과매도", description: "과매도 기준", min: 15, max: 30, step: 1, default: 20 },
    overbought: { label: "과매수", description: "과매수 기준", min: 70, max: 85, step: 1, default: 80 },
  },
  cci_reversal: {
    period: { label: "CCI 기간", description: "CCI 산출 기간", min: 10, max: 30, step: 1, default: 20 },
    lower: { label: "과매도 수준", description: "매수 신호 기준 (음수)", min: -150, max: -80, step: 5, default: -100 },
    upper: { label: "과매수 수준", description: "매도 신호 기준 (양수)", min: 80, max: 150, step: 5, default: 100 },
  },
  williams_r_signal: {
    period: { label: "기간", description: "%R 산출 기간", min: 7, max: 28, step: 1, default: 14 },
    oversold: { label: "과매도", description: "매수 기준 (예: -80)", min: -90, max: -75, step: 1, default: -80 },
    overbought: { label: "과매수", description: "매도 기준 (예: -20)", min: -25, max: -10, step: 1, default: -20 },
  },
  mfi_signal: {
    period: { label: "MFI 기간", description: "자금흐름지수 산출 기간", min: 7, max: 21, step: 1, default: 14 },
    oversold: { label: "과매도", description: "매수 신호 기준", min: 15, max: 30, step: 1, default: 20 },
    overbought: { label: "과매수", description: "매도 신호 기준", min: 70, max: 85, step: 1, default: 80 },
  },
  roc_momentum: {
    period: { label: "ROC 기간", description: "변화율 산출 기간 (일)", min: 5, max: 30, step: 1, default: 12 },
    threshold: { label: "임계값", description: "매수 신호 기준 변화율 (%)", min: 0.5, max: 5.0, step: 0.1, default: 2.0 },
  },
  bb_bounce: {
    period: { label: "볼린저 기간", description: "이동평균 기간", min: 10, max: 30, step: 1, default: 20 },
    std_dev: { label: "표준편차", description: "밴드 폭 (표준편차 배수)", min: 1.5, max: 3.0, step: 0.1, default: 2.0 },
  },
  bb_width_breakout: {
    period: { label: "볼린저 기간", description: "이동평균 기간", min: 15, max: 30, step: 1, default: 20 },
    std_dev: { label: "표준편차", description: "밴드 폭 배수", min: 1.5, max: 2.5, step: 0.1, default: 2.0 },
    width_percentile: { label: "폭 백분위", description: "스퀴즈 판단 기준 (%ile)", min: 5, max: 20, step: 1, default: 10 },
  },
  keltner_breakout: {
    ema_period: { label: "EMA 기간", description: "중심선 EMA 기간", min: 10, max: 30, step: 1, default: 20 },
    atr_period: { label: "ATR 기간", description: "변동성 기간", min: 7, max: 20, step: 1, default: 10 },
    multiplier: { label: "배수", description: "ATR 밴드 폭 배수", min: 1.0, max: 3.0, step: 0.1, default: 2.0 },
  },
  squeeze_momentum: {
    bb_period: { label: "볼린저 기간", description: "볼린저 밴드 기간", min: 15, max: 25, step: 1, default: 20 },
    bb_std: { label: "볼린저 표준편차", description: "볼린저 밴드 폭", min: 1.5, max: 2.5, step: 0.1, default: 2.0 },
    kc_period: { label: "켈트너 기간", description: "켈트너 채널 기간", min: 15, max: 25, step: 1, default: 20 },
    kc_mult: { label: "켈트너 배수", description: "켈트너 ATR 배수", min: 1.0, max: 2.0, step: 0.1, default: 1.5 },
  },
  atr_trailing_stop: {
    atr_period: { label: "ATR 기간", description: "변동성 산출 기간", min: 7, max: 21, step: 1, default: 14 },
    multiplier: { label: "배수", description: "ATR 손절선 배수", min: 2.0, max: 4.0, step: 0.1, default: 3.0 },
    entry_lookback: { label: "진입 기간", description: "최고가 돌파 기간", min: 10, max: 30, step: 1, default: 20 },
  },
  volume_spike: {
    lookback: { label: "평균 기간", description: "평균 거래량 산출 기간 (일)", min: 10, max: 100, step: 5, default: 50 },
    rvol_threshold: { label: "RVOL 임계값", description: "평균 대비 거래량 배수", min: 1.5, max: 5.0, step: 0.1, default: 2.0 },
  },
  vwap_deviation: {
    band_mult: { label: "밴드 배수", description: "VWAP 기준 이탈 배수", min: 1.0, max: 3.0, step: 0.1, default: 2.0 },
  },
  volume_breakout: {
    price_lookback: { label: "가격 기간", description: "최고가 돌파 기준 기간", min: 10, max: 60, step: 5, default: 20 },
    rvol_threshold: { label: "RVOL 임계값", description: "평균 대비 거래량 배수", min: 1.5, max: 5.0, step: 0.1, default: 2.0 },
  },
  elder_impulse: {
    ema_period: { label: "EMA 기간", description: "추세 방향 기준 EMA", min: 10, max: 20, step: 1, default: 13 },
    macd_fast: { label: "MACD 빠른", description: "MACD 단기 기간", min: 10, max: 14, step: 1, default: 12 },
    macd_slow: { label: "MACD 느린", description: "MACD 장기 기간", min: 24, max: 30, step: 1, default: 26 },
    macd_signal: { label: "MACD 시그널", description: "MACD 시그널 기간", min: 7, max: 11, step: 1, default: 9 },
  },
  multi_ma_vote: {
    fast: { label: "단기 이평", description: "단기 이동평균 기간", min: 5, max: 15, step: 1, default: 10 },
    medium: { label: "중기 이평", description: "중기 이동평균 기간", min: 20, max: 50, step: 5, default: 30 },
    slow: { label: "장기 이평", description: "장기 이동평균 기간", min: 50, max: 200, step: 10, default: 100 },
  },
  rsi_macd_combo: {
    rsi_period: { label: "RSI 기간", description: "RSI 산출 기간", min: 7, max: 21, step: 1, default: 14 },
    rsi_threshold: { label: "RSI 기준", description: "과매도 탈출 기준", min: 30, max: 50, step: 1, default: 40 },
    macd_fast: { label: "MACD 빠른", description: "MACD 단기 기간", min: 8, max: 14, step: 1, default: 12 },
    macd_slow: { label: "MACD 느린", description: "MACD 장기 기간", min: 20, max: 30, step: 1, default: 26 },
  },
  obv_trend: {
    obv_period: { label: "OBV 기간", description: "OBV 이동평균 기간", min: 10, max: 30, step: 1, default: 20 },
    price_period: { label: "가격 기간", description: "가격 추세 기간", min: 10, max: 30, step: 1, default: 20 },
  },
};

// ── Helpers ───────────────────────────────────────────────────────────

export function getSignalLabel(name: string): string {
  return SIGNAL_INFO[name]?.label ?? name;
}

export function getSignalCategory(name: string): string | undefined {
  return SIGNAL_INFO[name]?.category;
}
