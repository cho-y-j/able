"use client";

import {
  SIGNAL_INFO,
  SIGNAL_CATEGORIES_ORDERED,
  CATEGORY_COLORS,
  getSignalLabel,
} from "@/lib/signalMetadata";
import type { SignalEntry, Combinator } from "../../types";

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
        <p className="text-gray-400 text-sm">조합할 알고리즘을 선택하세요. 각 시그널의 설명을 참고해서 선택합니다.</p>
      </div>

      {Object.entries(SIGNAL_CATEGORIES_ORDERED).map(([key, category]) => (
        <div key={key}>
          <h4 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
            {category.label}
            <span className="text-xs text-gray-600">({category.signals.length}개)</span>
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {category.signals.map((sigName) => {
              const info = SIGNAL_INFO[sigName];
              if (!info) return null;
              const isSelected = selectedNames.has(sigName);
              const catColor = CATEGORY_COLORS[info.category] || "bg-gray-700 text-gray-400";
              return (
                <button
                  key={sigName}
                  onClick={() => toggleSignal(sigName)}
                  className={`text-left p-3 rounded-lg transition-all border ${
                    isSelected
                      ? "bg-blue-600/15 border-blue-500 ring-1 ring-blue-500/50"
                      : "bg-gray-800 border-gray-700 hover:border-gray-600"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs w-4 h-4 flex items-center justify-center rounded ${isSelected ? "bg-blue-500 text-white" : "bg-gray-700 text-gray-500"}`}>
                      {isSelected ? "✓" : ""}
                    </span>
                    <span className={`text-sm font-medium ${isSelected ? "text-blue-300" : "text-gray-300"}`}>
                      {info.label}
                    </span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${catColor}`}>
                      {info.category}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 leading-relaxed ml-6 line-clamp-2">
                    {info.description}
                  </p>
                </button>
              );
            })}
          </div>
        </div>
      ))}

      {/* Combinator selection */}
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <h4 className="text-sm font-medium text-gray-300 mb-1">조합 로직</h4>
        <p className="text-xs text-gray-500 mb-3">선택한 시그널들을 어떻게 결합할지 정합니다</p>
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
        {combinator === "AND" && (
          <p className="text-xs text-gray-500 mt-2">모든 시그널이 동시에 매수 신호를 보낼 때만 진입합니다. 신중한 전략에 적합.</p>
        )}
        {combinator === "OR" && (
          <p className="text-xs text-gray-500 mt-2">어느 하나라도 매수 신호를 보내면 진입합니다. 적극적인 전략에 적합.</p>
        )}
        {combinator === "MIN_AGREE" && (
          <>
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
            <p className="text-xs text-gray-500 mt-2">{selectedSignals.length}개 중 {minAgree}개 이상이 매수 신호를 보내면 진입합니다.</p>
          </>
        )}
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-500">
          {selectedSignals.length}개 시그널 선택됨
        </span>
        {selectedSignals.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {selectedSignals.map((s) => {
              const name = s.strategy_type || s.type;
              return (
                <span key={name} className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300">
                  {getSignalLabel(name)}
                </span>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
