"use client";

import {
  SIGNAL_INFO,
  FULL_PARAM_RANGES,
  CATEGORY_COLORS,
} from "@/lib/signalMetadata";
import type { SignalEntry } from "../../types";

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
        <p className="text-gray-400 text-sm">
          각 시그널의 파라미터를 조정하세요. 기본값은 일반적으로 잘 작동하는 설정입니다.
        </p>
      </div>

      {signals.length === 0 ? (
        <p className="text-gray-500 text-center py-8">선택된 시그널이 없습니다. 시그널 선택 단계로 돌아가세요.</p>
      ) : (
        signals.map((signal, idx) => {
          const sigName = signal.strategy_type || signal.type;
          const info = SIGNAL_INFO[sigName];
          const ranges = FULL_PARAM_RANGES[sigName] || {};
          const catColor = info ? (CATEGORY_COLORS[info.category] || "bg-gray-700 text-gray-400") : "";

          return (
            <div key={idx} className="bg-gray-800 rounded-xl p-4 border border-gray-700">
              {/* Signal header */}
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-medium text-white">{info?.label || sigName}</h4>
                  {info && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${catColor}`}>
                      {info.category}
                    </span>
                  )}
                </div>
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
              {info && (
                <p className="text-xs text-gray-500 mb-4">{info.description}</p>
              )}

              {Object.keys(ranges).length === 0 ? (
                <p className="text-gray-500 text-xs italic">이 시그널의 파라미터 정보가 없습니다. 기본값으로 실행됩니다.</p>
              ) : (
                <div className="space-y-3">
                  {Object.entries(ranges).map(([paramName, range]) => {
                    const currentVal = (signal.params[paramName] as number) ?? range.default;
                    const isDefault = currentVal === range.default;
                    return (
                      <div key={paramName}>
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <label className="text-xs text-gray-400">{range.label}</label>
                            {!isDefault && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                                AI 추천
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-blue-400 font-mono">{currentVal}</span>
                        </div>
                        <p className="text-[10px] text-gray-600 mb-1">{range.description}</p>
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
                          <span className="text-gray-700">기본: {range.default}</span>
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
