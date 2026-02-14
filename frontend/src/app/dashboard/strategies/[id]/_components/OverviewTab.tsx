"use client";

import MetricCard from "./MetricCard";
import ScoreGauge from "./ScoreGauge";

interface OverviewTabProps {
  metrics: Record<string, number>;
  validation: {
    wfa_score: number;
    mc_score: number;
    oos_score: number;
  } | null;
  compositeScore: number | null;
}

function qualityLabel(value: number | null, type: string): string {
  if (value === null || value === undefined) return "";
  switch (type) {
    case "return":
      if (value >= 100) return "탁월";
      if (value >= 30) return "우수";
      if (value >= 10) return "양호";
      if (value >= 0) return "보통";
      return "부진";
    case "sharpe":
      if (value >= 2) return "우수";
      if (value >= 1) return "양호";
      if (value >= 0.5) return "보통";
      return "부진";
    case "mdd":
      if (value >= -10) return "우수";
      if (value >= -20) return "양호";
      if (value >= -30) return "보통";
      return "위험";
    case "annual":
      if (value >= 30) return "탁월";
      if (value >= 15) return "우수";
      if (value >= 5) return "양호";
      if (value >= 0) return "보통";
      return "부진";
    default:
      return "";
  }
}

export default function OverviewTab({
  metrics: m,
  validation: v,
  compositeScore,
}: OverviewTabProps) {
  return (
    <div className="space-y-6">
      {/* Section 1: Backtest Performance */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <h4 className="text-sm font-semibold text-gray-400 mb-4 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
          백테스트 성과
        </h4>

        {/* Hero metrics - 4 large cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
          <div className="bg-gray-800 rounded-lg p-4 bg-gradient-to-br from-gray-800 to-gray-800/50">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-gray-500">총 수익률</span>
              <span className="text-[10px] text-gray-600 bg-gray-700/50 px-1.5 py-0.5 rounded">
                {qualityLabel(m.total_return, "return")}
              </span>
            </div>
            <span
              className={`text-xl font-bold ${m.total_return >= 0 ? "text-green-400" : "text-red-400"}`}
            >
              {m.total_return != null
                ? `${m.total_return > 0 ? "+" : ""}${m.total_return.toFixed(2)}%`
                : "N/A"}
            </span>
          </div>

          <div className="bg-gray-800 rounded-lg p-4 bg-gradient-to-br from-gray-800 to-gray-800/50">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-gray-500">연 수익률</span>
              <span className="text-[10px] text-gray-600 bg-gray-700/50 px-1.5 py-0.5 rounded">
                {qualityLabel(m.annual_return, "annual")}
              </span>
            </div>
            <span
              className={`text-xl font-bold ${(m.annual_return ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}
            >
              {m.annual_return != null
                ? `${m.annual_return > 0 ? "+" : ""}${m.annual_return.toFixed(2)}%`
                : "N/A"}
            </span>
          </div>

          <div className="bg-gray-800 rounded-lg p-4 bg-gradient-to-br from-gray-800 to-gray-800/50">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-gray-500">샤프 비율</span>
              <span className="text-[10px] text-gray-600 bg-gray-700/50 px-1.5 py-0.5 rounded">
                {qualityLabel(m.sharpe_ratio, "sharpe")}
              </span>
            </div>
            <span
              className={`text-xl font-bold ${(m.sharpe_ratio ?? 0) >= 1 ? "text-green-400" : (m.sharpe_ratio ?? 0) >= 0 ? "text-white" : "text-red-400"}`}
            >
              {m.sharpe_ratio != null ? m.sharpe_ratio.toFixed(2) : "N/A"}
            </span>
          </div>

          <div className="bg-gray-800 rounded-lg p-4 bg-gradient-to-br from-gray-800 to-gray-800/50">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-gray-500">최대 낙폭 (MDD)</span>
              <span className="text-[10px] text-gray-600 bg-gray-700/50 px-1.5 py-0.5 rounded">
                {qualityLabel(m.max_drawdown, "mdd")}
              </span>
            </div>
            <span
              className={`text-xl font-bold ${(m.max_drawdown ?? 0) >= -20 ? "text-green-400" : "text-red-400"}`}
            >
              {m.max_drawdown != null
                ? `${m.max_drawdown.toFixed(2)}%`
                : "N/A"}
            </span>
          </div>
        </div>

        {/* Secondary metrics - smaller */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
          <MetricCard
            label="소르티노 비율"
            value={m.sortino_ratio}
            suffix=""
            size="sm"
          />
          <MetricCard
            label="승률"
            value={m.win_rate}
            suffix="%"
            color="text-white"
            size="sm"
          />
          <MetricCard
            label="수익 팩터"
            value={m.profit_factor}
            suffix="x"
            color="text-white"
            size="sm"
          />
          <MetricCard
            label="총 거래수"
            value={m.total_trades}
            suffix=" trades"
            color="text-white"
            size="sm"
          />
        </div>

        {/* Info banner */}
        <div className="bg-gray-800/50 rounded-lg px-4 py-2.5 border border-gray-700/50">
          <p className="text-xs text-gray-500">
            샤프 비율: 1 이상 양호, 2 이상 우수 | 승률: 50% 이상 권장 | MDD:
            -20% 이내 권장 | 수익팩터: 1.5 이상 권장
          </p>
        </div>
      </div>

      {/* Section 2: Strategy Reliability */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <h4 className="text-sm font-semibold text-gray-400 mb-4 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
          전략 신뢰도
        </h4>

        {/* Score gauges in a row */}
        <div className="flex items-center justify-around mb-4 py-2">
          <ScoreGauge
            value={compositeScore}
            label="종합"
            size={90}
          />
          <ScoreGauge
            value={v?.wfa_score ?? null}
            label="WFA"
            size={76}
          />
          <ScoreGauge
            value={v?.mc_score ?? null}
            label="MC"
            size={76}
          />
          <ScoreGauge
            value={v?.oos_score ?? null}
            label="OOS"
            size={76}
          />
        </div>

        {/* Calmar ratio */}
        <div className="mb-3">
          <MetricCard
            label="칼마 비율"
            value={m.calmar_ratio}
            suffix=""
            tooltip="연 수익률 / 최대 낙폭. 높을수록 위험 대비 수익이 좋음"
          />
        </div>

        {/* Info banner */}
        <div className="bg-gray-800/50 rounded-lg px-4 py-2.5 border border-gray-700/50">
          <p className="text-xs text-gray-500">
            WFA: 다양한 구간에서의 안정성 | MC: 운이 아닌 실력 확률 | OOS:
            미래 데이터 적응력
          </p>
        </div>
      </div>
    </div>
  );
}
