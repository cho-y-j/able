"use client";

import { useState, useRef } from "react";
import api from "@/lib/api";
import { Loader2 } from "lucide-react";

interface ParamRange {
  type: string;
  current: number | string | null;
  min: number | null;
  max: number | null;
  choices: string[] | null;
}

interface RebacktestResult {
  composite_score: number | null;
  grade: string;
  metrics?: Record<string, number>;
}

interface ParamAdjustTabProps {
  strategyId: string;
  parameters: Record<string, number | string>;
  riskParams: Record<string, number>;
  paramRanges: Record<string, ParamRange>;
  onRebacktestComplete: () => void;
}

interface HistoryEntry {
  timestamp: string;
  params: Record<string, number | string>;
  result: RebacktestResult;
}

export default function ParamAdjustTab({
  strategyId,
  parameters,
  riskParams,
  paramRanges,
  onRebacktestComplete,
}: ParamAdjustTabProps) {
  const [editParams, setEditParams] = useState<Record<string, number | string>>(
    { ...parameters }
  );
  const [rebacktesting, setRebacktesting] = useState(false);
  const [lastResult, setLastResult] = useState<RebacktestResult | null>(null);
  const [resultError, setResultError] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const initialParams = useRef<Record<string, number | string>>({
    ...parameters,
  });

  // Check if a param has been changed from its original value
  const isChanged = (key: string) => {
    return String(editParams[key]) !== String(initialParams.current[key]);
  };

  const hasAnyChanges = Object.keys(editParams).some((k) => isChanged(k));

  // Preset: conservative (25% toward min)
  const applyConservative = () => {
    const newParams = { ...editParams };
    for (const [key, val] of Object.entries(newParams)) {
      const range = paramRanges[key];
      if (range && !range.choices && range.min != null && typeof val === "number") {
        const current = val;
        newParams[key] = current + (range.min - current) * 0.25;
        if (range.type !== "float") {
          newParams[key] = Math.round(newParams[key] as number);
        }
      }
    }
    setEditParams(newParams);
  };

  // Preset: aggressive (25% toward max)
  const applyAggressive = () => {
    const newParams = { ...editParams };
    for (const [key, val] of Object.entries(newParams)) {
      const range = paramRanges[key];
      if (range && !range.choices && range.max != null && typeof val === "number") {
        const current = val;
        newParams[key] = current + (range.max - current) * 0.25;
        if (range.type !== "float") {
          newParams[key] = Math.round(newParams[key] as number);
        }
      }
    }
    setEditParams(newParams);
  };

  // Reset to original
  const resetToOriginal = () => {
    setEditParams({ ...initialParams.current });
  };

  const handleRebacktest = async () => {
    setRebacktesting(true);
    setResultError(null);
    setLastResult(null);
    try {
      const { data: result } = await api.post(
        `/analysis/strategies/${strategyId}/rebacktest`,
        {
          parameters: editParams,
          risk_params: riskParams,
        }
      );
      const entry: HistoryEntry = {
        timestamp: new Date().toLocaleTimeString(),
        params: { ...editParams },
        result,
      };
      setHistory((h) => [entry, ...h].slice(0, 3));
      setLastResult(result);
      onRebacktestComplete();
    } catch (e: any) {
      setResultError(
        e.response?.data?.detail || e.message || "재백테스트 실패"
      );
    } finally {
      setRebacktesting(false);
    }
  };

  // Compute before/after comparison
  const beforeMetrics = initialParams.current;
  const afterResult = lastResult;

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
      <h3 className="text-lg font-semibold mb-2">파라미터 조정</h3>
      <p className="text-xs text-gray-500 mb-4">
        파라미터를 조정하고 재백테스트를 실행하면 변경된 파라미터로 새로운
        성과를 확인할 수 있습니다.
      </p>

      {/* Presets row */}
      <div className="flex gap-2 mb-5">
        <button
          onClick={applyConservative}
          className="px-4 py-2 bg-blue-900/30 hover:bg-blue-900/50 border border-blue-800/50 rounded-lg text-xs font-medium text-blue-400 transition-colors"
        >
          보수적
        </button>
        <button
          onClick={applyAggressive}
          className="px-4 py-2 bg-orange-900/30 hover:bg-orange-900/50 border border-orange-800/50 rounded-lg text-xs font-medium text-orange-400 transition-colors"
        >
          공격적
        </button>
        <button
          onClick={resetToOriginal}
          className="px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-xs font-medium text-gray-300 transition-colors"
        >
          원래값
        </button>
      </div>

      {/* Parameter inputs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        {Object.entries(editParams).map(([key, val]) => {
          const range = paramRanges[key];
          const changed = isChanged(key);
          return (
            <div
              key={key}
              className={`bg-gray-800 rounded-lg p-4 transition-colors ${changed ? "ring-1 ring-blue-500/30" : ""}`}
            >
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm text-gray-400">{key}</label>
                {changed && (
                  <span className="text-[10px] bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full font-medium">
                    변경됨
                  </span>
                )}
              </div>
              {range?.choices ? (
                <select
                  value={String(val)}
                  onChange={(e) =>
                    setEditParams((p) => ({ ...p, [key]: e.target.value }))
                  }
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                >
                  {range.choices.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              ) : (
                <div className="space-y-2">
                  <input
                    type="number"
                    value={val}
                    onChange={(e) =>
                      setEditParams((p) => ({
                        ...p,
                        [key]: Number(e.target.value),
                      }))
                    }
                    min={range?.min ?? undefined}
                    max={range?.max ?? undefined}
                    step={range?.type === "float" ? 0.1 : 1}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm font-mono focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                  />
                  {range && (
                    <div className="flex justify-between text-xs text-gray-600">
                      <span>최소: {range.min}</span>
                      <span className="text-blue-400">
                        원래: {range.current}
                      </span>
                      <span>최대: {range.max}</span>
                    </div>
                  )}
                  {range?.min != null && range?.max != null && (
                    <div className="relative">
                      <input
                        type="range"
                        value={Number(val)}
                        onChange={(e) =>
                          setEditParams((p) => ({
                            ...p,
                            [key]: Number(e.target.value),
                          }))
                        }
                        min={range.min}
                        max={range.max}
                        step={range.type === "float" ? 0.1 : 1}
                        className="w-full accent-blue-500"
                      />
                      {/* Original value marker */}
                      {range.current != null && (
                        <div
                          className="absolute top-0 w-0.5 h-3 bg-yellow-400/70 pointer-events-none"
                          style={{
                            left: `${((Number(range.current) - range.min) / (range.max - range.min)) * 100}%`,
                          }}
                          title={`원래값: ${range.current}`}
                        />
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Action buttons */}
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={handleRebacktest}
          disabled={rebacktesting}
          className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors"
        >
          {rebacktesting && (
            <Loader2 className="w-4 h-4 animate-spin" />
          )}
          {rebacktesting ? "재백테스트 실행 중..." : "재백테스트 실행"}
        </button>
        {hasAnyChanges && (
          <span className="text-xs text-gray-500">
            {Object.keys(editParams).filter((k) => isChanged(k)).length}개
            파라미터 변경됨
          </span>
        )}
      </div>

      {/* Inline result display */}
      {resultError && (
        <div className="mb-6 bg-red-900/20 border border-red-800 rounded-lg p-4">
          <div className="text-sm text-red-400 font-medium">
            재백테스트 실패
          </div>
          <div className="text-xs text-red-400/70 mt-1">{resultError}</div>
        </div>
      )}

      {/* Before/After comparison panel */}
      {afterResult && afterResult.metrics && (
        <div className="mb-6 bg-gray-800 rounded-lg p-5 border border-gray-700">
          <h4 className="text-sm font-semibold text-gray-400 mb-3">
            변경 전후 비교
          </h4>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <ComparisonCell
              label="종합 점수"
              after={afterResult.composite_score}
              suffix=""
            />
            <ComparisonCell
              label="총 수익률"
              after={afterResult.metrics?.total_return ?? null}
              suffix="%"
            />
            <ComparisonCell
              label="샤프 비율"
              after={afterResult.metrics?.sharpe_ratio ?? null}
              suffix=""
            />
            <ComparisonCell
              label="MDD"
              after={afterResult.metrics?.max_drawdown ?? null}
              suffix="%"
            />
          </div>
          <div className="mt-2 text-xs text-gray-500">
            등급: {afterResult.grade}
          </div>
        </div>
      )}

      {/* Rebacktest history */}
      {history.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <h4 className="text-sm font-semibold text-gray-400 mb-3">
            최근 재백테스트 기록
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-500 border-b border-gray-700">
                  <th className="text-left py-1.5 px-2">시간</th>
                  <th className="text-right py-1.5 px-2">점수</th>
                  <th className="text-right py-1.5 px-2">등급</th>
                  <th className="text-right py-1.5 px-2">수익률</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h, i) => (
                  <tr
                    key={i}
                    className="border-b border-gray-700/50"
                  >
                    <td className="py-1.5 px-2 text-gray-400">
                      {h.timestamp}
                    </td>
                    <td className="py-1.5 px-2 text-right font-mono">
                      {h.result.composite_score?.toFixed(1) ?? "N/A"}
                    </td>
                    <td className="py-1.5 px-2 text-right">
                      {h.result.grade}
                    </td>
                    <td className="py-1.5 px-2 text-right font-mono">
                      {h.result.metrics?.total_return != null
                        ? `${h.result.metrics.total_return > 0 ? "+" : ""}${h.result.metrics.total_return.toFixed(2)}%`
                        : "N/A"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function ComparisonCell({
  label,
  after,
  suffix,
}: {
  label: string;
  after: number | null;
  suffix: string;
}) {
  return (
    <div className="text-center">
      <div className="text-[10px] text-gray-500 mb-1">{label}</div>
      <div className="text-lg font-bold text-white">
        {after != null
          ? `${suffix === "%" && after > 0 ? "+" : ""}${after.toFixed(2)}${suffix}`
          : "N/A"}
      </div>
    </div>
  );
}
