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

interface ParamRange {
  type: string;
  current: number | string | null;
  min: number | null;
  max: number | null;
  choices: string[] | null;
}

interface AIAnalysis {
  ai_analysis: {
    decision: string;
    confidence: number;
    reasoning: string;
    risks: string;
    news_sentiment: string;
    raw_response: string;
    tokens_used: { total: number };
  };
  fact_sheet: string;
  news: { title: string; source: string; date: string }[];
  time_patterns: {
    day_of_week?: Record<string, { win_rate: number; avg_return: number; sample_count: number }>;
    summary?: { best_day: string; worst_day: string; overall_win_rate: number };
    streaks?: Record<string, { reversal_rate: number; sample_count: number }>;
  };
  current_signals: Record<string, { signal: string; accuracy: number }>;
  indicator_accuracy?: {
    ranking_overall?: { name: string; buy_accuracy: number; sell_accuracy: number; combined_accuracy: number }[];
  };
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
  const [tab, setTab] = useState<"overview" | "equity" | "trades" | "validation" | "params" | "ai">("overview");
  const chartRef = useRef<HTMLDivElement>(null);

  // Parameter editing
  const [paramRanges, setParamRanges] = useState<Record<string, ParamRange>>({});
  const [editParams, setEditParams] = useState<Record<string, number | string>>({});
  const [rebacktesting, setRebacktesting] = useState(false);

  // AI Analysis
  const [aiResult, setAiResult] = useState<AIAnalysis | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiJobId, setAiJobId] = useState<string | null>(null);

  useEffect(() => {
    if (params.id) fetchDetail(params.id as string);
  }, [params.id]);

  const fetchDetail = async (id: string) => {
    try {
      const { data: d } = await api.get(`/strategies/${id}/detail`);
      setData(d);
      setEditParams(d.parameters || {});
      // Fetch param ranges
      try {
        const { data: ranges } = await api.get(`/analysis/strategies/${id}/param-ranges`);
        setParamRanges(ranges.parameters || {});
      } catch { /* param ranges optional */ }
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

  // Parameter editing
  const handleRebacktest = async () => {
    if (!data) return;
    setRebacktesting(true);
    try {
      const { data: result } = await api.post(`/analysis/strategies/${data.id}/rebacktest`, {
        parameters: editParams,
        risk_params: data.risk_params,
      });
      // Refresh the page data
      await fetchDetail(data.id);
      alert(`재백테스트 완료! 새 점수: ${result.composite_score?.toFixed(1)} (${result.grade})`);
    } catch (e: any) {
      alert(`재백테스트 실패: ${e.response?.data?.detail || e.message}`);
    } finally {
      setRebacktesting(false);
    }
  };

  // AI Analysis
  const startAiAnalysis = async () => {
    if (!data) return;
    setAiLoading(true);
    setAiResult(null);
    try {
      const { data: job } = await api.post("/analysis/ai-report", {
        stock_code: data.stock_code,
        date_range_start: data.backtest?.date_range_start || "2024-01-01",
        date_range_end: data.backtest?.date_range_end || "2025-12-31",
        include_macro: true,
      });
      setAiJobId(job.job_id);
      pollAiJob(job.job_id);
    } catch (e: any) {
      alert(`AI 분석 시작 실패: ${e.response?.data?.detail || e.message}`);
      setAiLoading(false);
    }
  };

  const pollAiJob = (jobId: string) => {
    const interval = setInterval(async () => {
      try {
        const { data: job } = await api.get(`/analysis/ai-report/${jobId}`);
        if (job.status === "complete") {
          clearInterval(interval);
          setAiResult(job.result);
          setAiLoading(false);
        } else if (job.status === "error") {
          clearInterval(interval);
          alert(`AI 분석 실패: ${job.error}`);
          setAiLoading(false);
        }
      } catch {
        clearInterval(interval);
        setAiLoading(false);
      }
    }, 2000);
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
        <div className="flex items-center gap-3">
          <button onClick={startAiAnalysis} disabled={aiLoading}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-700 rounded-lg text-sm font-medium transition-colors">
            {aiLoading ? "AI 분석 중..." : "🤖 AI 분석"}
          </button>
          <div className={`px-4 py-2 rounded-lg text-sm font-medium ${data.is_auto_trading ? "bg-green-600/20 text-green-400" : "bg-gray-700 text-gray-400"}`}>
            {data.is_auto_trading ? "자동매매 활성" : "비활성"}
          </div>
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
      <div className="flex gap-1 mb-6 bg-gray-900 rounded-lg p-1 border border-gray-800 overflow-x-auto">
        {(["overview", "equity", "trades", "validation", "params", "ai"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors whitespace-nowrap ${tab === t ? "bg-blue-600 text-white" : "text-gray-400 hover:text-white"}`}>
            {t === "overview" ? "성과 지표" : t === "equity" ? "에쿼티 커브" : t === "trades" ? "거래 내역" : t === "validation" ? "검증 결과" : t === "params" ? "파라미터 조정" : "AI 분석"}
          </button>
        ))}
      </div>

      {/* Tab: Overview */}
      {tab === "overview" && m && (
        <div className="space-y-6">
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h4 className="text-sm font-semibold text-gray-400 mb-3">백테스트 성과</h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <MetricCard label="총 수익률" value={m.total_return} suffix="%" />
              <MetricCard label="연 수익률" value={m.annual_return} suffix="%" />
              <MetricCard label="샤프 비율" value={m.sharpe_ratio} suffix="" />
              <MetricCard label="소르티노 비율" value={m.sortino_ratio} suffix="" />
              <MetricCard label="최대 낙폭 (MDD)" value={m.max_drawdown} suffix="%" />
              <MetricCard label="승률" value={m.win_rate} suffix="%" color="text-white" />
              <MetricCard label="수익 팩터" value={m.profit_factor} suffix="x" color="text-white" />
              <MetricCard label="총 거래수" value={m.total_trades} suffix=" trades" color="text-white" />
            </div>
            <p className="text-xs text-gray-600 mt-3">
              샤프 비율: 1 이상 양호, 2 이상 우수 | 승률: 50% 이상 권장 | MDD: -20% 이내 권장 | 수익팩터: 1.5 이상 권장
            </p>
          </div>
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <h4 className="text-sm font-semibold text-gray-400 mb-3">검증 점수 (전략 신뢰도)</h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <MetricCard label="칼마 비율" value={m.calmar_ratio} suffix="" />
              <MetricCard label="WFA 점수" value={v?.wfa_score ?? null} suffix="" color="text-blue-400" />
              <MetricCard label="MC 수익 확률" value={v?.mc_score ?? null} suffix="%" color="text-purple-400" />
              <MetricCard label="OOS 점수" value={v?.oos_score ?? null} suffix="" color="text-cyan-400" />
            </div>
            <p className="text-xs text-gray-600 mt-3">
              WFA: 다양한 구간에서의 안정성 | MC: 운이 아닌 실력 확률 | OOS: 미래 데이터 적응력
            </p>
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
            <h3 className="text-lg font-semibold mb-1">Walk-Forward Analysis (전진 분석)</h3>
            <p className="text-xs text-gray-500 mb-4">데이터를 여러 구간으로 나눠 각각 훈련/검증을 반복합니다. 점수가 높을수록 다양한 시장 상황에서 안정적입니다.</p>
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
            <h3 className="text-lg font-semibold mb-1">Monte Carlo Simulation (몬테카를로 시뮬레이션)</h3>
            <p className="text-xs text-gray-500 mb-4">거래 순서를 1,000번 무작위로 섞어 운이 아닌 실력인지 검증합니다. 수익 확률이 50% 이상이면 통계적으로 유의미합니다.</p>
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
            <h3 className="text-lg font-semibold mb-1">Out-of-Sample 검증 (미래 데이터 테스트)</h3>
            <p className="text-xs text-gray-500 mb-4">전략을 만든 데이터(훈련)와 처음 보는 데이터(검증)를 비교합니다. 유지율이 100%에 가까울수록 과적합 위험이 낮습니다.</p>
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

      {/* Tab: Parameter Adjustment */}
      {tab === "params" && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="text-lg font-semibold mb-2">파라미터 조정</h3>
          <p className="text-xs text-gray-500 mb-4">파라미터를 조정하고 재백테스트를 실행하면 변경된 파라미터로 새로운 성과를 확인할 수 있습니다.</p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            {Object.entries(editParams).map(([key, val]) => {
              const range = paramRanges[key];
              return (
                <div key={key} className="bg-gray-800 rounded-lg p-4">
                  <label className="block text-sm text-gray-400 mb-2">{key}</label>
                  {range?.choices ? (
                    <select value={String(val)} onChange={(e) => setEditParams(p => ({ ...p, [key]: e.target.value }))}
                      className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm">
                      {range.choices.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  ) : (
                    <div className="space-y-2">
                      <input type="number" value={val} onChange={(e) => setEditParams(p => ({ ...p, [key]: Number(e.target.value) }))}
                        min={range?.min ?? undefined} max={range?.max ?? undefined}
                        step={range?.type === "float" ? 0.1 : 1}
                        className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm font-mono" />
                      {range && (
                        <div className="flex justify-between text-xs text-gray-600">
                          <span>최소: {range.min}</span>
                          <span className="text-blue-400">현재: {range.current}</span>
                          <span>최대: {range.max}</span>
                        </div>
                      )}
                      {range?.min != null && range?.max != null && (
                        <input type="range" value={Number(val)} onChange={(e) => setEditParams(p => ({ ...p, [key]: Number(e.target.value) }))}
                          min={range.min} max={range.max} step={range.type === "float" ? 0.1 : 1}
                          className="w-full accent-blue-500" />
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="flex items-center gap-4">
            <button onClick={handleRebacktest} disabled={rebacktesting}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 rounded-lg text-sm font-medium transition-colors">
              {rebacktesting ? "재백테스트 실행 중..." : "재백테스트 실행"}
            </button>
            <button onClick={() => data && setEditParams(data.parameters)}
              className="px-6 py-3 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm font-medium transition-colors text-gray-300">
              원래값 복원
            </button>
          </div>
        </div>
      )}

      {/* Tab: AI Analysis */}
      {tab === "ai" && (
        <div className="space-y-6">
          {!aiResult && !aiLoading && (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-8 text-center">
              <div className="text-4xl mb-3">🤖</div>
              <h3 className="text-lg font-semibold mb-2">AI 하이브리드 분석</h3>
              <p className="text-sm text-gray-500 mb-4">
                통계 엔진이 시간패턴, 지표 적중률, 매크로 상관관계를 분석하고,<br />
                DeepSeek AI가 뉴스 감성과 함께 종합 매매 판단을 내립니다.
              </p>
              <button onClick={startAiAnalysis}
                className="px-8 py-3 bg-purple-600 hover:bg-purple-700 rounded-lg text-sm font-medium transition-colors">
                AI 분석 시작
              </button>
            </div>
          )}

          {aiLoading && (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-8 text-center">
              <div className="animate-spin text-4xl mb-3">⚙️</div>
              <p className="text-gray-400">통계 분석 + AI 판단 생성 중... (약 15-30초)</p>
              <p className="text-xs text-gray-600 mt-2">Layer 1 (통계) → Layer 2 (팩트시트) → Layer 3 (DeepSeek AI)</p>
            </div>
          )}

          {aiResult && (
            <>
              {/* AI Decision Card */}
              <div className={`rounded-xl border p-6 ${
                aiResult.ai_analysis.decision === "매수" ? "bg-green-900/20 border-green-800" :
                aiResult.ai_analysis.decision === "매도" ? "bg-red-900/20 border-red-800" :
                "bg-gray-900 border-gray-800"
              }`}>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <span className={`text-3xl font-bold ${
                      aiResult.ai_analysis.decision === "매수" ? "text-green-400" :
                      aiResult.ai_analysis.decision === "매도" ? "text-red-400" : "text-yellow-400"
                    }`}>
                      {aiResult.ai_analysis.decision}
                    </span>
                    <div className="flex items-center gap-1">
                      {Array.from({ length: 10 }, (_, i) => (
                        <div key={i} className={`w-3 h-3 rounded-sm ${i < aiResult.ai_analysis.confidence ? "bg-blue-500" : "bg-gray-700"}`} />
                      ))}
                      <span className="text-sm text-gray-400 ml-2">확신도 {aiResult.ai_analysis.confidence}/10</span>
                    </div>
                  </div>
                  <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                    aiResult.ai_analysis.news_sentiment === "긍정" ? "bg-green-900/50 text-green-400" :
                    aiResult.ai_analysis.news_sentiment === "부정" ? "bg-red-900/50 text-red-400" :
                    "bg-gray-700 text-gray-400"
                  }`}>
                    뉴스: {aiResult.ai_analysis.news_sentiment}
                  </span>
                </div>

                <div className="bg-black/20 rounded-lg p-4 text-sm whitespace-pre-wrap">
                  {aiResult.ai_analysis.raw_response}
                </div>

                <div className="text-xs text-gray-600 mt-3">
                  모델: DeepSeek | 토큰: {aiResult.ai_analysis.tokens_used?.total || 0}
                </div>
              </div>

              {/* Current Signals */}
              {Object.keys(aiResult.current_signals).length > 0 && (
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                  <h4 className="text-sm font-semibold text-gray-400 mb-3">현재 활성 시그널</h4>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {Object.entries(aiResult.current_signals).map(([name, info]) => (
                      <div key={name} className={`rounded-lg p-3 ${info.signal === "buy" ? "bg-green-900/20 border border-green-800" : "bg-red-900/20 border border-red-800"}`}>
                        <div className="text-xs text-gray-400">{name}</div>
                        <div className={`text-sm font-bold ${info.signal === "buy" ? "text-green-400" : "text-red-400"}`}>
                          {info.signal === "buy" ? "매수" : "매도"} (적중률 {info.accuracy}%)
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Time Patterns */}
              {aiResult.time_patterns?.day_of_week && (
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                  <h4 className="text-sm font-semibold text-gray-400 mb-3">요일별 승률 패턴</h4>
                  <div className="flex gap-2">
                    {Object.entries(aiResult.time_patterns.day_of_week).map(([day, stats]) => (
                      <div key={day} className="flex-1 text-center">
                        <div className="text-xs text-gray-500 mb-1">{day}</div>
                        <div className={`text-lg font-bold ${stats.win_rate >= 55 ? "text-green-400" : stats.win_rate <= 45 ? "text-red-400" : "text-gray-300"}`}>
                          {stats.win_rate}%
                        </div>
                        <div className="w-full bg-gray-800 rounded-full h-2 mt-1">
                          <div className={`h-2 rounded-full ${stats.win_rate >= 50 ? "bg-green-500" : "bg-red-500"}`} style={{ width: `${stats.win_rate}%` }} />
                        </div>
                        <div className="text-[10px] text-gray-600 mt-1">{stats.sample_count}일</div>
                      </div>
                    ))}
                  </div>
                  {aiResult.time_patterns.summary && (
                    <p className="text-xs text-gray-600 mt-3">
                      최고: {aiResult.time_patterns.summary.best_day} | 최저: {aiResult.time_patterns.summary.worst_day} | 전체 승률: {aiResult.time_patterns.summary.overall_win_rate}%
                    </p>
                  )}
                </div>
              )}

              {/* Indicator Accuracy */}
              {aiResult.indicator_accuracy?.ranking_overall && (
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                  <h4 className="text-sm font-semibold text-gray-400 mb-3">지표 적중률 랭킹</h4>
                  <div className="space-y-2">
                    {aiResult.indicator_accuracy.ranking_overall.slice(0, 8).map((ind, i) => (
                      <div key={ind.name} className="flex items-center gap-3">
                        <span className="text-xs text-gray-600 w-6">#{i + 1}</span>
                        <span className="text-sm text-gray-300 w-40 truncate">{ind.name}</span>
                        <div className="flex-1 flex items-center gap-2">
                          <div className="flex-1 bg-gray-800 rounded-full h-2">
                            <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${ind.combined_accuracy}%` }} />
                          </div>
                          <span className="text-xs text-gray-400 w-20">
                            매수 {ind.buy_accuracy}%
                          </span>
                          <span className="text-xs text-gray-400 w-20">
                            매도 {ind.sell_accuracy}%
                          </span>
                          <span className="text-sm font-mono font-bold text-white w-12 text-right">
                            {ind.combined_accuracy}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* News */}
              {aiResult.news && aiResult.news.length > 0 && (
                <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
                  <h4 className="text-sm font-semibold text-gray-400 mb-3">최근 뉴스</h4>
                  <div className="space-y-2">
                    {aiResult.news.map((n, i) => (
                      <div key={i} className="flex items-start gap-2 text-sm">
                        <span className="text-gray-600">{i + 1}.</span>
                        <div>
                          <div className="text-gray-300">{n.title}</div>
                          <div className="text-xs text-gray-600">{n.source} {n.date && `| ${n.date}`}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Fact Sheet (collapsible) */}
              <details className="bg-gray-900 rounded-xl border border-gray-800">
                <summary className="p-4 text-sm text-gray-500 cursor-pointer hover:text-gray-300">
                  팩트시트 원문 보기 (AI에 입력된 통계 요약)
                </summary>
                <pre className="px-4 pb-4 text-xs text-gray-600 whitespace-pre-wrap font-mono">
                  {aiResult.fact_sheet}
                </pre>
              </details>
            </>
          )}
        </div>
      )}
    </div>
  );
}
