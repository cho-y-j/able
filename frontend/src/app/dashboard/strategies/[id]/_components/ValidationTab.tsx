"use client";

import ScoreGauge from "./ScoreGauge";

interface ValidationTabProps {
  validationResults: {
    wfa?: {
      wfa_score: number;
      stability: number;
      mean_sharpe: number;
      mean_return: number;
    };
    mc?: {
      mc_score: number;
      statistics?: Record<string, number>;
      drawdown_stats?: Record<string, number>;
      percentiles?: Record<string, number>;
    };
    oos?: { oos_score: number };
    oos_detail?: {
      in_sample?: Record<string, unknown>;
      out_of_sample?: Record<string, unknown>;
      degradation?: Record<string, number>;
    };
  };
}

function retentionColor(value: number | null | undefined): string {
  if (value == null) return "text-gray-500";
  if (value >= 80) return "text-green-400";
  if (value >= 60) return "text-yellow-400";
  return "text-red-400";
}

function retentionArrow(value: number | null | undefined): string {
  if (value == null) return "";
  if (value >= 80) return "\u2191"; // up arrow
  if (value >= 60) return "\u2192"; // right arrow
  return "\u2193"; // down arrow
}

export default function ValidationTab({
  validationResults: vr,
}: ValidationTabProps) {
  // Compute overall verdict
  const wfaScore = vr.wfa?.wfa_score ?? null;
  const mcScore = vr.mc?.mc_score ?? null;
  const oosScore = vr.oos?.oos_score ?? null;

  const scores = [wfaScore, mcScore, oosScore].filter(
    (s) => s !== null
  ) as number[];
  const minScore = scores.length > 0 ? Math.min(...scores) : null;

  let verdict: { label: string; color: string; bg: string };
  if (minScore === null) {
    verdict = {
      label: "미평가",
      color: "text-gray-400",
      bg: "bg-gray-800 border-gray-700",
    };
  } else if (minScore >= 70) {
    verdict = {
      label: "높음",
      color: "text-green-400",
      bg: "bg-green-900/20 border-green-800",
    };
  } else if (minScore >= 50) {
    verdict = {
      label: "보통",
      color: "text-yellow-400",
      bg: "bg-yellow-900/20 border-yellow-800",
    };
  } else {
    verdict = {
      label: "낮음",
      color: "text-red-400",
      bg: "bg-red-900/20 border-red-800",
    };
  }

  return (
    <div className="space-y-6">
      {/* Overall Verdict */}
      <div className={`rounded-xl border p-6 ${verdict.bg}`}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold mb-1">전략 신뢰도 종합</h3>
            <p className="text-xs text-gray-500">
              WFA, Monte Carlo, OOS 3가지 검증 결과를 종합한 신뢰도 판단
            </p>
          </div>
          <div className="text-right">
            <div className={`text-3xl font-bold ${verdict.color}`}>
              {verdict.label}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {scores.length > 0
                ? `최저 점수: ${minScore?.toFixed(1)}`
                : "검증 데이터 없음"}
            </div>
          </div>
        </div>
      </div>

      {/* WFA Section */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <h3 className="text-lg font-semibold mb-1">
          Walk-Forward Analysis (전진 분석)
        </h3>
        <p className="text-xs text-gray-500 mb-4">
          데이터를 여러 구간으로 나눠 각각 훈련/검증을 반복합니다. 점수가
          높을수록 다양한 시장 상황에서 안정적입니다.
        </p>
        <div className="flex items-start gap-6">
          <ScoreGauge
            value={vr.wfa?.wfa_score ?? null}
            label="WFA"
            size={100}
          />
          <div className="flex-1 grid grid-cols-3 gap-4">
            <div className="bg-gray-800 rounded-lg p-4 text-center">
              <div className="text-xs text-gray-500 mb-1">안정성</div>
              <div className="text-2xl font-bold text-green-400">
                {vr.wfa?.stability?.toFixed(1) ?? "N/A"}
              </div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 text-center">
              <div className="text-xs text-gray-500 mb-1">평균 Sharpe</div>
              <div className="text-2xl font-bold">
                {vr.wfa?.mean_sharpe?.toFixed(2) ?? "N/A"}
              </div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4 text-center">
              <div className="text-xs text-gray-500 mb-1">평균 수익률</div>
              <div className="text-2xl font-bold">
                {vr.wfa?.mean_return != null
                  ? `${vr.wfa.mean_return > 0 ? "+" : ""}${vr.wfa.mean_return.toFixed(2)}%`
                  : "N/A"}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Monte Carlo Section */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <h3 className="text-lg font-semibold mb-1">
          Monte Carlo Simulation (몬테카를로 시뮬레이션)
        </h3>
        <p className="text-xs text-gray-500 mb-4">
          거래 순서를 1,000번 무작위로 섞어 운이 아닌 실력인지 검증합니다. 수익
          확률이 50% 이상이면 통계적으로 유의미합니다.
        </p>
        {vr.mc ? (
          <div className="flex items-start gap-6">
            <ScoreGauge
              value={vr.mc.mc_score}
              label="MC"
              size={100}
            />
            <div className="flex-1 space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-gray-800 rounded-lg p-4 text-center">
                  <div className="text-xs text-gray-500 mb-1">수익 확률</div>
                  <div
                    className={`text-2xl font-bold ${vr.mc.mc_score >= 50 ? "text-green-400" : "text-red-400"}`}
                  >
                    {vr.mc.mc_score?.toFixed(1)}%
                  </div>
                </div>
                <div className="bg-gray-800 rounded-lg p-4 text-center">
                  <div className="text-xs text-gray-500 mb-1">평균 수익</div>
                  <div className="text-2xl font-bold">
                    {vr.mc.statistics?.mean_return != null
                      ? `${vr.mc.statistics.mean_return > 0 ? "+" : ""}${vr.mc.statistics.mean_return.toFixed(1)}%`
                      : "N/A"}
                  </div>
                </div>
                <div className="bg-gray-800 rounded-lg p-4 text-center">
                  <div className="text-xs text-gray-500 mb-1">
                    최악 시나리오
                  </div>
                  <div className="text-2xl font-bold text-red-400">
                    {vr.mc.statistics?.worst_case != null
                      ? `${vr.mc.statistics.worst_case.toFixed(1)}%`
                      : "N/A"}
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-1 gap-4">
                <div className="bg-gray-800 rounded-lg p-4 text-center">
                  <div className="text-xs text-gray-500 mb-1">파산 위험</div>
                  <div className="text-2xl font-bold">
                    {vr.mc.statistics?.risk_of_ruin_pct != null
                      ? `${vr.mc.statistics.risk_of_ruin_pct.toFixed(1)}%`
                      : "N/A"}
                  </div>
                </div>
              </div>

              {/* Percentile bar chart */}
              {vr.mc.percentiles && (
                <div className="bg-gray-800 rounded-lg p-4">
                  <div className="text-xs text-gray-500 mb-3">
                    수익률 분포 (백분위)
                  </div>
                  <div className="flex items-end gap-1.5 h-28">
                    {Object.entries(vr.mc.percentiles).map(([k, val]) => {
                      const height = Math.max(
                        5,
                        Math.min(
                          100,
                          (((val as number) + 50) / 100) * 80 + 10
                        )
                      );
                      const isPositive = (val as number) >= 0;
                      return (
                        <div
                          key={k}
                          className="flex-1 flex flex-col items-center gap-1"
                        >
                          <div
                            className={`w-full rounded-t transition-all ${isPositive ? "bg-green-500/80" : "bg-red-500/80"}`}
                            style={{ height: `${height}%` }}
                          />
                          <span className="text-[10px] text-gray-500">
                            {k}
                          </span>
                          <span
                            className={`text-[10px] font-mono ${isPositive ? "text-green-400" : "text-red-400"}`}
                          >
                            {(val as number).toFixed(1)}%
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <p className="text-gray-500">Monte Carlo 데이터가 없습니다.</p>
        )}
      </div>

      {/* OOS Section */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <h3 className="text-lg font-semibold mb-1">
          Out-of-Sample 검증 (미래 데이터 테스트)
        </h3>
        <p className="text-xs text-gray-500 mb-4">
          전략을 만든 데이터(훈련)와 처음 보는 데이터(검증)를 비교합니다.
          유지율이 100%에 가까울수록 과적합 위험이 낮습니다.
        </p>
        <div className="flex items-start gap-6">
          <ScoreGauge
            value={vr.oos?.oos_score ?? null}
            label="OOS"
            size={100}
          />
          <div className="flex-1 space-y-4">
            {/* Degradation arrows */}
            {vr.oos_detail?.degradation && (
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-gray-800 rounded-lg p-4 text-center">
                  <div className="text-xs text-gray-500 mb-1">
                    Sharpe 유지율
                  </div>
                  <div
                    className={`text-2xl font-bold ${retentionColor(vr.oos_detail.degradation.sharpe_retention)}`}
                  >
                    {retentionArrow(
                      vr.oos_detail.degradation.sharpe_retention
                    )}{" "}
                    {vr.oos_detail.degradation.sharpe_retention?.toFixed(1)}%
                  </div>
                </div>
                <div className="bg-gray-800 rounded-lg p-4 text-center">
                  <div className="text-xs text-gray-500 mb-1">
                    수익률 유지율
                  </div>
                  <div
                    className={`text-2xl font-bold ${retentionColor(vr.oos_detail.degradation.return_retention)}`}
                  >
                    {retentionArrow(
                      vr.oos_detail.degradation.return_retention
                    )}{" "}
                    {vr.oos_detail.degradation.return_retention?.toFixed(1)}%
                  </div>
                </div>
                <div className="bg-gray-800 rounded-lg p-4 text-center">
                  <div className="text-xs text-gray-500 mb-1">
                    승률 유지율
                  </div>
                  <div
                    className={`text-2xl font-bold ${retentionColor(vr.oos_detail.degradation.winrate_retention)}`}
                  >
                    {retentionArrow(
                      vr.oos_detail.degradation.winrate_retention
                    )}{" "}
                    {vr.oos_detail.degradation.winrate_retention?.toFixed(1)}%
                  </div>
                </div>
              </div>
            )}

            {/* In-sample vs Out-of-sample comparison */}
            {vr.oos_detail?.in_sample && vr.oos_detail?.out_of_sample && (
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-800 rounded-lg p-4">
                  <div className="text-sm font-medium text-gray-400 mb-2">
                    In-Sample (훈련)
                  </div>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-500">Sharpe</span>
                      <span>
                        {(
                          vr.oos_detail.in_sample.sharpe_ratio as number
                        )?.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">수익률</span>
                      <span>
                        {(
                          vr.oos_detail.in_sample.total_return as number
                        )?.toFixed(2)}
                        %
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">MDD</span>
                      <span>
                        {(
                          vr.oos_detail.in_sample.max_drawdown as number
                        )?.toFixed(2)}
                        %
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">거래수</span>
                      <span>
                        {vr.oos_detail.in_sample.total_trades as number}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="bg-gray-800 rounded-lg p-4">
                  <div className="text-sm font-medium text-cyan-400 mb-2">
                    Out-of-Sample (검증)
                  </div>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-500">Sharpe</span>
                      <span>
                        {(
                          vr.oos_detail.out_of_sample.sharpe_ratio as number
                        )?.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">수익률</span>
                      <span>
                        {(
                          vr.oos_detail.out_of_sample.total_return as number
                        )?.toFixed(2)}
                        %
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">MDD</span>
                      <span>
                        {(
                          vr.oos_detail.out_of_sample.max_drawdown as number
                        )?.toFixed(2)}
                        %
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">거래수</span>
                      <span>
                        {vr.oos_detail.out_of_sample.total_trades as number}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
