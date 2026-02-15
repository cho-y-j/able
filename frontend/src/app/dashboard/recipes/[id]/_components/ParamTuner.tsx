"use client";

interface SignalEntry {
  type: string;
  strategy_type?: string;
  params: Record<string, unknown>;
  weight: number;
}

// Default param ranges by signal type
const PARAM_RANGES: Record<string, Record<string, { label: string; min: number; max: number; step: number; default: number }>> = {
  sma_crossover: {
    fast_period: { label: "빠른 이평선", min: 5, max: 30, step: 1, default: 10 },
    slow_period: { label: "느린 이평선", min: 30, max: 200, step: 5, default: 50 },
  },
  rsi_mean_reversion: {
    period: { label: "RSI 기간", min: 5, max: 30, step: 1, default: 14 },
    oversold: { label: "과매도", min: 15, max: 40, step: 1, default: 30 },
    overbought: { label: "과매수", min: 60, max: 85, step: 1, default: 70 },
  },
  macd_crossover: {
    fast_period: { label: "빠른 기간", min: 5, max: 20, step: 1, default: 12 },
    slow_period: { label: "느린 기간", min: 20, max: 50, step: 1, default: 26 },
    signal_period: { label: "시그널 기간", min: 5, max: 15, step: 1, default: 9 },
  },
  volume_spike: {
    lookback: { label: "평균 기간", min: 10, max: 100, step: 5, default: 50 },
    rvol_threshold: { label: "RVOL 임계값", min: 1.5, max: 5.0, step: 0.1, default: 2.0 },
  },
  vwap_deviation: {
    band_mult: { label: "밴드 배수", min: 1.0, max: 3.0, step: 0.1, default: 2.0 },
  },
  volume_breakout: {
    price_lookback: { label: "가격 기간", min: 10, max: 60, step: 5, default: 20 },
    rvol_threshold: { label: "RVOL 임계값", min: 1.5, max: 5.0, step: 0.1, default: 2.0 },
  },
};

interface ParamTunerProps {
  signals: SignalEntry[];
  onSignalsChange: (signals: SignalEntry[]) => void;
}

export default function ParamTuner({ signals, onSignalsChange }: ParamTunerProps) {
  const updateParam = (index: number, paramName: string, value: number) => {
    const updated = [...signals];
    updated[index] = {
      ...updated[index],
      params: { ...updated[index].params, [paramName]: value },
    };
    onSignalsChange(updated);
  };

  const updateWeight = (index: number, weight: number) => {
    const updated = [...signals];
    updated[index] = { ...updated[index], weight };
    onSignalsChange(updated);
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-white mb-1">파라미터 조정</h3>
        <p className="text-gray-400 text-sm">각 시그널의 파라미터를 조정하세요</p>
      </div>

      {signals.length === 0 ? (
        <p className="text-gray-500 text-center py-8">선택된 시그널이 없습니다</p>
      ) : (
        signals.map((signal, idx) => {
          const sigName = signal.strategy_type || signal.type;
          const ranges = PARAM_RANGES[sigName] || {};
          return (
            <div key={idx} className="bg-gray-800 rounded-xl p-4 border border-gray-700">
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-sm font-medium text-white">{sigName}</h4>
                <div className="flex items-center gap-2">
                  <label className="text-xs text-gray-400">가중치:</label>
                  <input
                    type="number"
                    min={0.1}
                    max={2.0}
                    step={0.1}
                    value={signal.weight}
                    onChange={(e) => updateWeight(idx, Number(e.target.value))}
                    className="w-16 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-white text-xs text-center"
                  />
                </div>
              </div>

              {Object.keys(ranges).length === 0 ? (
                <p className="text-gray-500 text-xs">기본 파라미터 사용</p>
              ) : (
                <div className="space-y-3">
                  {Object.entries(ranges).map(([paramName, range]) => {
                    const currentVal = (signal.params[paramName] as number) ?? range.default;
                    return (
                      <div key={paramName}>
                        <div className="flex items-center justify-between mb-1">
                          <label className="text-xs text-gray-400">{range.label}</label>
                          <span className="text-xs text-blue-400 font-mono">{currentVal}</span>
                        </div>
                        <input
                          type="range"
                          min={range.min}
                          max={range.max}
                          step={range.step}
                          value={currentVal}
                          onChange={(e) => updateParam(idx, paramName, Number(e.target.value))}
                          className="w-full h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                        />
                        <div className="flex justify-between text-[10px] text-gray-600 mt-0.5">
                          <span>{range.min}</span>
                          <span>{range.max}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}
