"use client";

const SIGNAL_CATEGORIES = {
  trend: {
    label: "추세 추종",
    signals: [
      { name: "sma_crossover", label: "SMA 크로스오버" },
      { name: "ema_crossover", label: "EMA 크로스오버" },
      { name: "macd_crossover", label: "MACD 크로스오버" },
      { name: "macd_histogram", label: "MACD 히스토그램" },
      { name: "adx_trend", label: "ADX 추세" },
      { name: "ichimoku_cloud", label: "일목균형표" },
      { name: "supertrend", label: "슈퍼트렌드" },
      { name: "donchian_breakout", label: "돈치안 돌파" },
      { name: "psar_trend", label: "파라볼릭 SAR" },
    ],
  },
  momentum: {
    label: "모멘텀",
    signals: [
      { name: "rsi_mean_reversion", label: "RSI 평균회귀" },
      { name: "stochastic_crossover", label: "스토캐스틱 크로스" },
      { name: "cci_reversal", label: "CCI 반전" },
      { name: "williams_r", label: "윌리엄스 %R" },
      { name: "roc_momentum", label: "ROC 모멘텀" },
    ],
  },
  volatility: {
    label: "변동성",
    signals: [
      { name: "bollinger_bounce", label: "볼린저 밴드 반등" },
      { name: "bollinger_squeeze", label: "볼린저 스퀴즈" },
      { name: "keltner_breakout", label: "켈트너 돌파" },
      { name: "atr_breakout", label: "ATR 돌파" },
      { name: "volatility_contraction", label: "변동성 수축" },
    ],
  },
  volume: {
    label: "거래량",
    signals: [
      { name: "volume_spike", label: "거래량 폭증 (RVOL)" },
      { name: "vwap_deviation", label: "VWAP 이탈" },
      { name: "volume_breakout", label: "거래량+가격 돌파" },
    ],
  },
  composite: {
    label: "복합",
    signals: [
      { name: "trend_momentum_composite", label: "추세+모멘텀 복합" },
      { name: "mean_reversion_composite", label: "평균회귀 복합" },
      { name: "breakout_composite", label: "돌파 복합" },
      { name: "multi_timeframe_trend", label: "멀티 타임프레임" },
      { name: "adaptive_regime", label: "적응형 체제" },
    ],
  },
};

type Combinator = "AND" | "OR" | "MIN_AGREE";

interface SignalEntry {
  type: string;
  strategy_type?: string;
  params: Record<string, unknown>;
  weight: number;
}

interface SignalSelectorProps {
  selectedSignals: SignalEntry[];
  combinator: Combinator;
  minAgree: number;
  onSignalsChange: (signals: SignalEntry[]) => void;
  onCombinatorChange: (c: Combinator) => void;
  onMinAgreeChange: (n: number) => void;
}

export default function SignalSelector({
  selectedSignals,
  combinator,
  minAgree,
  onSignalsChange,
  onCombinatorChange,
  onMinAgreeChange,
}: SignalSelectorProps) {
  const selectedNames = new Set(selectedSignals.map((s) => s.strategy_type || s.type));

  const toggleSignal = (name: string) => {
    if (selectedNames.has(name)) {
      onSignalsChange(selectedSignals.filter((s) => (s.strategy_type || s.type) !== name));
    } else {
      onSignalsChange([
        ...selectedSignals,
        { type: "recommended", strategy_type: name, params: {}, weight: 1.0 },
      ]);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-white mb-1">시그널 선택</h3>
        <p className="text-gray-400 text-sm">조합할 알고리즘을 선택하세요</p>
      </div>

      {Object.entries(SIGNAL_CATEGORIES).map(([key, category]) => (
        <div key={key}>
          <h4 className="text-sm font-medium text-gray-300 mb-2">{category.label}</h4>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {category.signals.map((sig) => {
              const isSelected = selectedNames.has(sig.name);
              return (
                <button
                  key={sig.name}
                  onClick={() => toggleSignal(sig.name)}
                  className={`text-left px-3 py-2.5 rounded-lg text-sm transition-all border ${
                    isSelected
                      ? "bg-blue-600/20 border-blue-500 text-blue-300"
                      : "bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600"
                  }`}
                >
                  <span className="mr-2">{isSelected ? "✓" : "○"}</span>
                  {sig.label}
                </button>
              );
            })}
          </div>
        </div>
      ))}

      {/* Combinator selection */}
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <h4 className="text-sm font-medium text-gray-300 mb-3">조합 로직</h4>
        <div className="flex gap-3">
          {(["AND", "OR", "MIN_AGREE"] as Combinator[]).map((c) => (
            <button
              key={c}
              onClick={() => onCombinatorChange(c)}
              className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                combinator === c
                  ? "bg-blue-600 text-white"
                  : "bg-gray-700 text-gray-400 hover:text-white"
              }`}
            >
              {c === "AND" ? "AND (모두 충족)" : c === "OR" ? "OR (하나라도)" : `${minAgree}개 이상`}
            </button>
          ))}
        </div>
        {combinator === "MIN_AGREE" && (
          <div className="mt-3 flex items-center gap-3">
            <label className="text-sm text-gray-400">최소 동의 수:</label>
            <input
              type="number"
              min={1}
              max={selectedSignals.length || 1}
              value={minAgree}
              onChange={(e) => onMinAgreeChange(Number(e.target.value))}
              className="w-20 bg-gray-700 border border-gray-600 rounded-lg px-3 py-1.5 text-white text-sm"
            />
            <span className="text-xs text-gray-500">/ {selectedSignals.length}개 시그널</span>
          </div>
        )}
      </div>

      <div className="text-sm text-gray-500">
        {selectedSignals.length}개 시그널 선택됨
      </div>
    </div>
  );
}
