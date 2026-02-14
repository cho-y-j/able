"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import api from "@/lib/api";
import { useI18n } from "@/i18n";

interface StrategyDetail {
  id: string;
  name: string;
  stock_code: string;
  stock_name: string | null;
  strategy_type: string;
  parameters: Record<string, number | string>;
  entry_rules: Record<string, string>;
  exit_rules: Record<string, string>;
  risk_params: Record<string, number>;
  composite_score: number | null;
  validation_results: {
    wfa?: { wfa_score: number; stability: number; mean_sharpe: number; mean_return: number };
    mc?: { mc_score: number; statistics?: Record<string, number>; drawdown_stats?: Record<string, number>; percentiles?: Record<string, number> };
    oos?: { oos_score: number };
    oos_detail?: {
      in_sample?: Record<string, unknown>;
      out_of_sample?: Record<string, unknown>;
      degradation?: Record<string, number>;
    };
  } | null;
  status: string;
  is_auto_trading: boolean;
  created_at: string;
  backtest: {
    id: string;
    date_range_start: string;
    date_range_end: string;
    metrics: Record<string, number>;
    validation: { wfa_score: number; mc_score: number; oos_score: number };
    equity_curve: { date: string; value: number }[];
    trade_log: { entry_date: string; exit_date: string; entry_price: number; exit_price: number; pnl_percent: number; hold_days: number }[];
  } | null;
}

function MetricCard({ label, value, suffix, color }: { label: string; value: number | null; suffix?: string; color?: string }) {
  const c = color || (value && value > 0 ? "text-green-400" : value && value < 0 ? "text-red-400" : "text-white");
  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-lg font-bold ${c}`}>
        {value !== null && value !== undefined ? `${value > 0 && !suffix?.includes("trades") ? "+" : ""}${value.toFixed(suffix === "%" ? 2 : suffix === "x" ? 2 : 1)}${suffix || ""}` : "N/A"}
      </div>
    </div>
  );
}

function GradeBadge({ score }: { score: number | null }) {
  if (!score) return <span className="text-gray-500">N/A</span>;
  let grade: string, bg: string;
  if (score >= 90) { grade = "A+"; bg = "bg-green-600"; }
  else if (score >= 80) { grade = "A"; bg = "bg-green-500"; }
  else if (score >= 70) { grade = "B+"; bg = "bg-blue-500"; }
  else if (score >= 60) { grade = "B"; bg = "bg-blue-400"; }
  else if (score >= 50) { grade = "C+"; bg = "bg-yellow-500"; }
  else if (score >= 40) { grade = "C"; bg = "bg-yellow-600"; }
  else { grade = "D"; bg = "bg-red-500"; }
  return (
    <span className={`${bg} text-white text-sm font-bold px-3 py-1 rounded-full`}>
      {grade} ({score.toFixed(1)})
    </span>
  );
}

export default function StrategyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { t } = useI18n();
  const [data, setData] = useState<StrategyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"overview" | "equity" | "trades" | "validation">("overview");
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (params.id) fetchDetail(params.id as string);
  }, [params.id]);

  const fetchDetail = async (id: string) => {
    try {
      const { data: d } = await api.get(`/strategies/${id}/detail`);
      setData(d);
    } catch {
      router.push("/dashboard/strategies");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (tab === "equity" && data?.backtest?.equity_curve && chartRef.current) {
      renderEquityChart();
    }
  }, [tab, data]);

  const renderEquityChart = async () => {
    if (!chartRef.current || !data?.backtest?.equity_curve) return;
    const lc = await import("lightweight-charts");
    chartRef.current.innerHTML = "";
    const chart = lc.createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 400,
      layout: { background: { color: "#1a1a2e" }, textColor: "#d1d5db" },
      grid: { vertLines: { color: "#374151" }, horzLines: { color: "#374151" } },
    });

    const curve = data.backtest.equity_curve;
    const series = chart.addSeries(lc.BaselineSeries, {
      baseValue: { type: "price", price: 10_000_000 },
      topLineColor: "#22c55e",
      bottomLineColor: "#ef4444",
      topFillColor1: "rgba(34,197,94,0.2)",
      topFillColor2: "rgba(34,197,94,0)",
      bottomFillColor1: "rgba(239,68,68,0)",
      bottomFillColor2: "rgba(239,68,68,0.2)",
    });

    const chartData = curve.map((p: { date: string; value: number }) => ({
      time: p.date.split(" ")[0].split("T")[0],
      value: p.value,
    }));
    series.setData(chartData as any);
    chart.timeScale().fitContent();

    return () => chart.remove();
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-gray-500">로딩 중...</div></div>;
  if (!data) return <div className="text-red-500">전략을 찾을 수 없습니다.</div>;

  const bt = data.backtest;
  const m = bt?.metrics;
  const v = bt?.validation;
  const vr = data.validation_results;

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <button onClick={() => router.push("/dashboard/strategies")} className="text-sm text-gray-500 hover:text-white mb-2 flex items-center gap-1">
            &larr; 전략 목록
          </button>
          <h2 className="text-2xl font-bold flex items-center gap-3">
            {data.name}
            <GradeBadge score={data.composite_score} />
          </h2>
          <p className="text-gray-500 text-sm mt-1">
            {data.stock_code} {data.stock_name && `(${data.stock_name})`} | {data.strategy_type} | {data.status}
          </p>
        </div>
        <div className={`px-4 py-2 rounded-lg text-sm font-medium ${data.is_auto_trading ? "bg-green-600/20 text-green-400" : "bg-gray-700 text-gray-400"}`}>
          {data.is_auto_trading ? "자동매매 활성" : "비활성"}
        </div>
      </div>

      {/* Parameters */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <h3 className="text-lg font-semibold mb-4">전략 파라미터</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {Object.entries(data.parameters).map(([k, val]) => (
            <div key={k} className="bg-gray-800 rounded-lg p-3">
              <div className="text-xs text-gray-500">{k}</div>
              <div className="text-white font-mono font-bold">{String(val)}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-900 rounded-lg p-1 border border-gray-800">
        {(["overview", "equity", "trades", "validation"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${tab === t ? "bg-blue-600 text-white" : "text-gray-400 hover:text-white"}`}>
            {t === "overview" ? "성과 지표" : t === "equity" ? "에쿼티 커브" : t === "trades" ? "거래 내역" : "검증 결과"}
          </button>
        ))}
      </div>

      {/* Tab: Overview */}
      {tab === "overview" && m && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <MetricCard label="총 수익률" value={m.total_return} suffix="%" />
            <MetricCard label="연 수익률" value={m.annual_return} suffix="%" />
            <MetricCard label="샤프 비율" value={m.sharpe_ratio} suffix="" />
            <MetricCard label="소르티노 비율" value={m.sortino_ratio} suffix="" />
            <MetricCard label="최대 낙폭" value={m.max_drawdown} suffix="%" />
            <MetricCard label="승률" value={m.win_rate} suffix="%" color="text-white" />
            <MetricCard label="수익 팩터" value={m.profit_factor} suffix="x" color="text-white" />
            <MetricCard label="총 거래수" value={m.total_trades} suffix=" trades" color="text-white" />
            <MetricCard label="칼마 비율" value={m.calmar_ratio} suffix="" />
            <MetricCard label="WFA 점수" value={v?.wfa_score ?? null} suffix="" color="text-blue-400" />
            <MetricCard label="MC 수익 확률" value={v?.mc_score ?? null} suffix="%" color="text-purple-400" />
            <MetricCard label="OOS 점수" value={v?.oos_score ?? null} suffix="" color="text-cyan-400" />
          </div>
        </div>
      )}

      {/* Tab: Equity Curve */}
      {tab === "equity" && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="text-lg font-semibold mb-4">에쿼티 커브</h3>
          {bt?.equity_curve ? (
            <div ref={chartRef} className="w-full" style={{ height: 400 }} />
          ) : (
            <p className="text-gray-500">에쿼티 커브 데이터가 없습니다.</p>
          )}
          {bt?.equity_curve && (
            <div className="grid grid-cols-3 gap-4 mt-4">
              <div className="text-center">
                <div className="text-xs text-gray-500">시작 자본</div>
                <div className="text-white font-bold">{(10_000_000).toLocaleString()}원</div>
              </div>
              <div className="text-center">
                <div className="text-xs text-gray-500">최종 자본</div>
                <div className={`font-bold ${(m?.total_return ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {bt.equity_curve.length > 0 ? Math.round(bt.equity_curve[bt.equity_curve.length - 1].value).toLocaleString() : "N/A"}원
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-gray-500">기간</div>
                <div className="text-white font-bold">{bt.date_range_start} ~ {bt.date_range_end}</div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab: Trade Log */}
      {tab === "trades" && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="text-lg font-semibold mb-4">거래 내역 ({bt?.trade_log?.length || 0}건)</h3>
          {bt?.trade_log && bt.trade_log.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 border-b border-gray-800">
                    <th className="text-left py-2 px-3">#</th>
                    <th className="text-left py-2 px-3">진입일</th>
                    <th className="text-left py-2 px-3">청산일</th>
                    <th className="text-right py-2 px-3">진입가</th>
                    <th className="text-right py-2 px-3">청산가</th>
                    <th className="text-right py-2 px-3">손익(%)</th>
                    <th className="text-right py-2 px-3">보유일</th>
                  </tr>
                </thead>
                <tbody>
                  {bt.trade_log.map((trade, i) => (
                    <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/50">
                      <td className="py-2 px-3 text-gray-500">{i + 1}</td>
                      <td className="py-2 px-3">{trade.entry_date?.split(" ")[0]}</td>
                      <td className="py-2 px-3">{trade.exit_date?.split(" ")[0]}</td>
                      <td className="py-2 px-3 text-right font-mono">{trade.entry_price?.toLocaleString()}</td>
                      <td className="py-2 px-3 text-right font-mono">{trade.exit_price?.toLocaleString()}</td>
                      <td className={`py-2 px-3 text-right font-mono font-bold ${trade.pnl_percent >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {trade.pnl_percent >= 0 ? "+" : ""}{trade.pnl_percent?.toFixed(2)}%
                      </td>
                      <td className="py-2 px-3 text-right text-gray-400">{trade.hold_days}일</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-gray-500">거래 내역이 없습니다.</p>
          )}
        </div>
      )}

      {/* Tab: Validation */}
      {tab === "validation" && vr && (
        <div className="space-y-6">
          {/* WFA */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h3 className="text-lg font-semibold mb-4">Walk-Forward Analysis</h3>
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-gray-800 rounded-lg p-4 text-center">
                <div className="text-xs text-gray-500 mb-1">WFA Score</div>
                <div className="text-2xl font-bold text-blue-400">{vr.wfa?.wfa_score?.toFixed(1) ?? "N/A"}</div>
              </div>
              <div className="bg-gray-800 rounded-lg p-4 text-center">
                <div className="text-xs text-gray-500 mb-1">안정성</div>
                <div className="text-2xl font-bold text-green-400">{vr.wfa?.stability?.toFixed(1) ?? "N/A"}</div>
              </div>
              <div className="bg-gray-800 rounded-lg p-4 text-center">
                <div className="text-xs text-gray-500 mb-1">평균 Sharpe</div>
                <div className="text-2xl font-bold">{vr.wfa?.mean_sharpe?.toFixed(2) ?? "N/A"}</div>
              </div>
              <div className="bg-gray-800 rounded-lg p-4 text-center">
                <div className="text-xs text-gray-500 mb-1">평균 수익률</div>
                <div className="text-2xl font-bold">{vr.wfa?.mean_return != null ? `${vr.wfa.mean_return > 0 ? "+" : ""}${vr.wfa.mean_return.toFixed(2)}%` : "N/A"}</div>
              </div>
            </div>
          </div>

          {/* Monte Carlo */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h3 className="text-lg font-semibold mb-4">Monte Carlo Simulation</h3>
            {vr.mc ? (
              <>
                <div className="grid grid-cols-4 gap-4 mb-4">
                  <div className="bg-gray-800 rounded-lg p-4 text-center">
                    <div className="text-xs text-gray-500 mb-1">수익 확률</div>
                    <div className={`text-2xl font-bold ${vr.mc.mc_score >= 50 ? "text-green-400" : "text-red-400"}`}>{vr.mc.mc_score?.toFixed(1)}%</div>
                  </div>
                  <div className="bg-gray-800 rounded-lg p-4 text-center">
                    <div className="text-xs text-gray-500 mb-1">평균 수익</div>
                    <div className="text-2xl font-bold">{vr.mc.statistics?.mean_return != null ? `${vr.mc.statistics.mean_return > 0 ? "+" : ""}${vr.mc.statistics.mean_return.toFixed(1)}%` : "N/A"}</div>
                  </div>
                  <div className="bg-gray-800 rounded-lg p-4 text-center">
                    <div className="text-xs text-gray-500 mb-1">최악 시나리오</div>
                    <div className="text-2xl font-bold text-red-400">{vr.mc.statistics?.worst_case != null ? `${vr.mc.statistics.worst_case.toFixed(1)}%` : "N/A"}</div>
                  </div>
                  <div className="bg-gray-800 rounded-lg p-4 text-center">
                    <div className="text-xs text-gray-500 mb-1">파산 위험</div>
                    <div className="text-2xl font-bold">{vr.mc.statistics?.risk_of_ruin_pct != null ? `${vr.mc.statistics.risk_of_ruin_pct.toFixed(1)}%` : "N/A"}</div>
                  </div>
                </div>
                {/* MC Distribution Bar */}
                {vr.mc.percentiles && (
                  <div className="bg-gray-800 rounded-lg p-4">
                    <div className="text-xs text-gray-500 mb-3">수익률 분포 (백분위)</div>
                    <div className="flex items-end gap-1 h-24">
                      {Object.entries(vr.mc.percentiles).map(([k, val]) => {
                        const height = Math.max(5, Math.min(100, ((val as number) + 50) / 100 * 80 + 10));
                        const isPositive = (val as number) >= 0;
                        return (
                          <div key={k} className="flex-1 flex flex-col items-center gap-1">
                            <div className={`w-full rounded-t ${isPositive ? "bg-green-500" : "bg-red-500"}`} style={{ height: `${height}%` }} />
                            <span className="text-[10px] text-gray-500">{k}</span>
                            <span className={`text-[10px] font-mono ${isPositive ? "text-green-400" : "text-red-400"}`}>{(val as number).toFixed(1)}%</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <p className="text-gray-500">Monte Carlo 데이터가 없습니다.</p>
            )}
          </div>

          {/* OOS */}
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h3 className="text-lg font-semibold mb-4">Out-of-Sample 검증</h3>
            <div className="grid grid-cols-4 gap-4 mb-4">
              <div className="bg-gray-800 rounded-lg p-4 text-center">
                <div className="text-xs text-gray-500 mb-1">OOS Score</div>
                <div className="text-2xl font-bold text-cyan-400">{vr.oos?.oos_score?.toFixed(1) ?? "N/A"}</div>
              </div>
              {vr.oos_detail?.degradation && (
                <>
                  <div className="bg-gray-800 rounded-lg p-4 text-center">
                    <div className="text-xs text-gray-500 mb-1">Sharpe 유지율</div>
                    <div className="text-2xl font-bold">{vr.oos_detail.degradation.sharpe_retention?.toFixed(1)}%</div>
                  </div>
                  <div className="bg-gray-800 rounded-lg p-4 text-center">
                    <div className="text-xs text-gray-500 mb-1">수익률 유지율</div>
                    <div className="text-2xl font-bold">{vr.oos_detail.degradation.return_retention?.toFixed(1)}%</div>
                  </div>
                  <div className="bg-gray-800 rounded-lg p-4 text-center">
                    <div className="text-xs text-gray-500 mb-1">승률 유지율</div>
                    <div className="text-2xl font-bold">{vr.oos_detail.degradation.winrate_retention?.toFixed(1)}%</div>
                  </div>
                </>
              )}
            </div>
            {/* IS vs OOS comparison */}
            {vr.oos_detail?.in_sample && vr.oos_detail?.out_of_sample && (
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-800 rounded-lg p-4">
                  <div className="text-sm font-medium text-gray-400 mb-2">In-Sample (훈련)</div>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between"><span className="text-gray-500">Sharpe</span><span>{(vr.oos_detail.in_sample.sharpe_ratio as number)?.toFixed(2)}</span></div>
                    <div className="flex justify-between"><span className="text-gray-500">수익률</span><span>{(vr.oos_detail.in_sample.total_return as number)?.toFixed(2)}%</span></div>
                    <div className="flex justify-between"><span className="text-gray-500">MDD</span><span>{(vr.oos_detail.in_sample.max_drawdown as number)?.toFixed(2)}%</span></div>
                    <div className="flex justify-between"><span className="text-gray-500">거래수</span><span>{vr.oos_detail.in_sample.total_trades as number}</span></div>
                  </div>
                </div>
                <div className="bg-gray-800 rounded-lg p-4">
                  <div className="text-sm font-medium text-cyan-400 mb-2">Out-of-Sample (검증)</div>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between"><span className="text-gray-500">Sharpe</span><span>{(vr.oos_detail.out_of_sample.sharpe_ratio as number)?.toFixed(2)}</span></div>
                    <div className="flex justify-between"><span className="text-gray-500">수익률</span><span>{(vr.oos_detail.out_of_sample.total_return as number)?.toFixed(2)}%</span></div>
                    <div className="flex justify-between"><span className="text-gray-500">MDD</span><span>{(vr.oos_detail.out_of_sample.max_drawdown as number)?.toFixed(2)}%</span></div>
                    <div className="flex justify-between"><span className="text-gray-500">거래수</span><span>{vr.oos_detail.out_of_sample.total_trades as number}</span></div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
