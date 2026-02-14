"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { useI18n } from "@/i18n";

interface Strategy {
  id: string;
  name: string;
  stock_code: string;
  stock_name: string | null;
  strategy_type: string;
  composite_score: number | null;
  validation_results: {
    wfa?: { wfa_score: number };
    mc?: { mc_score: number };
    oos?: { oos_score: number };
    backtest?: Record<string, number>;
  } | null;
  status: string;
  is_auto_trading: boolean;
  created_at: string;
}

interface SearchJob {
  job_id: string;
  status: string;
  progress: number;
  step: string;
  result: { strategies_found: number; strategies: { id: string; name: string; score: number; grade: string; total_return: number; sharpe_ratio: number }[] } | null;
  error: string | null;
}

const STRATEGY_TYPE_LABELS: Record<string, string> = {
  elder_impulse: "엘더 임펄스",
  roc_momentum: "ROC 모멘텀",
  atr_trailing_stop: "ATR 추세추종",
  multi_ma_vote: "다중 이동평균",
  macd_crossover: "MACD 크로스",
  rsi_mean_reversion: "RSI 평균회귀",
  bb_width_breakout: "볼린저 돌파",
  cci_reversal: "CCI 반전",
  stochastic_crossover: "스토캐스틱",
  squeeze_momentum: "스퀴즈 모멘텀",
  sma_crossover: "SMA 크로스",
  ema_crossover: "EMA 크로스",
  mfi_signal: "MFI 시그널",
  williams_r_signal: "윌리엄스 %R",
  rsi_macd_combo: "RSI+MACD 콤보",
};

function gradeInfo(score: number | null): { grade: string; bg: string; label: string } {
  if (!score) return { grade: "-", bg: "bg-gray-600", label: "미평가" };
  if (score >= 90) return { grade: "A+", bg: "bg-green-600", label: "최우수 - 실전 투입 강력 추천" };
  if (score >= 80) return { grade: "A", bg: "bg-green-500", label: "우수 - 실전 투입 추천" };
  if (score >= 70) return { grade: "B+", bg: "bg-blue-500", label: "양호 - 조건부 추천" };
  if (score >= 60) return { grade: "B", bg: "bg-blue-400", label: "보통 - 추가 검토 필요" };
  if (score >= 50) return { grade: "C+", bg: "bg-yellow-500", label: "미흡 - 개선 필요" };
  if (score >= 40) return { grade: "C", bg: "bg-yellow-600", label: "부족 - 사용 비추천" };
  return { grade: "D", bg: "bg-red-500", label: "위험 - 사용 금지" };
}

function GradeBadge({ score }: { score: number | null }) {
  const { grade, bg } = gradeInfo(score);
  if (!score) return null;
  return <span className={`${bg} text-white text-xs font-bold px-2 py-0.5 rounded-full`}>{grade}</span>;
}

function statusLabel(status: string) {
  switch (status) {
    case "active": return "자동매매 중";
    case "validated": return "검증 완료";
    case "draft": return "초안";
    case "paused": return "일시정지";
    default: return status;
  }
}

export default function StrategiesPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [searchCode, setSearchCode] = useState("");
  const [searchJob, setSearchJob] = useState<SearchJob | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [dateStart, setDateStart] = useState("2024-01-01");
  const [dateEnd, setDateEnd] = useState("2025-12-31");
  const [method, setMethod] = useState("grid");
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetchStrategies();
    return () => { if (pollingRef.current) clearInterval(pollingRef.current); };
  }, []);

  const fetchStrategies = async () => {
    try {
      const { data } = await api.get("/strategies");
      setStrategies(data);
    } catch { /* */ }
  };

  const startSearch = async () => {
    if (!searchCode.trim()) return;
    setSearchLoading(true);
    setSearchJob(null);
    try {
      const { data } = await api.post("/strategies/search", {
        stock_code: searchCode.trim(),
        date_range_start: dateStart,
        date_range_end: dateEnd,
        optimization_method: method,
      });
      const jobId = data.job_id;
      setSearchJob({ job_id: jobId, status: "running", progress: 0, step: "initializing", result: null, error: null });

      pollingRef.current = setInterval(async () => {
        try {
          const { data: job } = await api.get(`/strategies/search-jobs/${jobId}`);
          setSearchJob(job);
          if (job.status === "complete" || job.status === "error") {
            if (pollingRef.current) clearInterval(pollingRef.current);
            pollingRef.current = null;
            setSearchLoading(false);
            if (job.status === "complete") fetchStrategies();
          }
        } catch {
          if (pollingRef.current) clearInterval(pollingRef.current);
          pollingRef.current = null;
          setSearchLoading(false);
        }
      }, 2000);
    } catch {
      alert(t.strategies.searchFailed);
      setSearchLoading(false);
    }
  };

  const toggleAutoTrading = async (e: React.MouseEvent, id: string, isActive: boolean) => {
    e.stopPropagation();
    try {
      if (isActive) await api.post(`/strategies/${id}/deactivate`);
      else await api.post(`/strategies/${id}/activate`);
      fetchStrategies();
    } catch { alert(t.strategies.toggleFailed); }
  };

  const deleteStrategy = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm("이 전략을 삭제하시겠습니까?")) return;
    try {
      await api.delete(`/strategies/${id}`);
      fetchStrategies();
    } catch { /* */ }
  };

  const stepLabel = (step: string) => {
    if (step.startsWith("optimizing:")) {
      const name = step.split(":")[1];
      return `최적화 중: ${STRATEGY_TYPE_LABELS[name] || name} 전략 파라미터 조합 탐색...`;
    }
    if (step.startsWith("validating:")) {
      const name = step.split(":")[1];
      return `검증 중: ${STRATEGY_TYPE_LABELS[name] || name} 안정성 테스트...`;
    }
    if (step === "fetching_data") return "주가 데이터 수집 중...";
    if (step === "optimizing") return "23개 매매 전략 최적화 시작...";
    if (step === "validating") return "상위 전략 신뢰성 검증 중...";
    if (step === "done") return "완료!";
    if (step === "initializing") return "탐색 준비 중...";
    return step;
  };

  const typeName = (t: string) => STRATEGY_TYPE_LABELS[t] || t;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">{t.strategies.title}</h2>

      {/* Strategy Search */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <h3 className="text-lg font-semibold mb-1">{t.strategies.aiSearch}</h3>
        <p className="text-sm text-gray-500 mb-4">{t.strategies.aiSearchDesc}</p>

        {/* How it works - collapsed guide */}
        <details className="mb-4 bg-gray-800/50 rounded-lg">
          <summary className="px-4 py-2 text-sm text-blue-400 cursor-pointer hover:text-blue-300">
            사용법 안내 (클릭하여 펼치기)
          </summary>
          <div className="px-4 pb-4 text-sm text-gray-400 space-y-2">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-2">
              <div className="bg-gray-800 rounded-lg p-3">
                <div className="text-blue-400 font-bold mb-1">1단계: 종목 입력</div>
                <p>종목코드(005930) 또는 종목명(삼성전자)을 입력합니다. 분석할 기간과 최적화 방법을 선택하세요.</p>
              </div>
              <div className="bg-gray-800 rounded-lg p-3">
                <div className="text-blue-400 font-bold mb-1">2단계: AI 탐색</div>
                <p>23개 매매 전략을 자동으로 테스트하고, 최적의 파라미터를 찾은 뒤 Walk-Forward, Monte Carlo, OOS 검증을 수행합니다.</p>
              </div>
              <div className="bg-gray-800 rounded-lg p-3">
                <div className="text-blue-400 font-bold mb-1">3단계: 결과 확인</div>
                <p>각 전략을 클릭하면 상세 성과, 에쿼티 커브, 거래 내역, 검증 결과를 확인할 수 있습니다. 마음에 드는 전략은 자동매매를 활성화하세요.</p>
              </div>
            </div>
            <div className="mt-2 p-3 bg-gray-800 rounded-lg">
              <div className="text-white font-bold mb-1">등급 기준</div>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
                <span><span className="text-green-400 font-bold">A+</span> (90+) 최우수</span>
                <span><span className="text-green-400 font-bold">A</span> (80+) 우수</span>
                <span><span className="text-blue-400 font-bold">B+</span> (70+) 양호</span>
                <span><span className="text-blue-400 font-bold">B</span> (60+) 보통</span>
                <span><span className="text-yellow-400 font-bold">C+</span> (50+) 미흡</span>
                <span><span className="text-yellow-400 font-bold">C</span> (40+) 부족</span>
                <span><span className="text-red-400 font-bold">D</span> (&lt;40) 위험</span>
              </div>
            </div>
          </div>
        </details>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mb-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">종목</label>
            <input type="text" value={searchCode} onChange={(e) => setSearchCode(e.target.value)}
              placeholder={t.strategies.stockCodePlaceholder}
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">시작일</label>
            <input type="date" value={dateStart} onChange={(e) => setDateStart(e.target.value)}
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">종료일</label>
            <input type="date" value={dateEnd} onChange={(e) => setDateEnd(e.target.value)}
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">최적화 방법</label>
            <select value={method} onChange={(e) => setMethod(e.target.value)}
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500">
              <option value="grid">Grid Search (빠름, 기본)</option>
              <option value="genetic">Genetic (정확, 느림)</option>
              <option value="bayesian">Bayesian (최적, 느림)</option>
            </select>
          </div>
        </div>
        <button onClick={startSearch} disabled={searchLoading || !searchCode.trim()}
          className="w-full sm:w-auto px-8 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg text-sm font-medium transition-colors">
          {searchLoading ? t.strategies.searching : t.strategies.searchStrategy}
        </button>

        {/* Progress */}
        {searchJob && searchJob.status === "running" && (
          <div className="mt-4">
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-400">{stepLabel(searchJob.step)}</span>
              <span className="text-blue-400">{searchJob.progress}%</span>
            </div>
            <div className="w-full bg-gray-800 rounded-full h-2">
              <div className="bg-blue-600 h-2 rounded-full transition-all duration-500" style={{ width: `${searchJob.progress}%` }} />
            </div>
            <p className="text-xs text-gray-600 mt-1">
              {searchJob.progress < 60 ? "23개 전략의 파라미터를 최적화하고 있습니다. 약 30초~1분 소요됩니다." : "상위 전략의 안정성을 검증하고 있습니다. 거의 완료되었습니다."}
            </p>
          </div>
        )}

        {/* Results */}
        {searchJob?.status === "complete" && searchJob.result && (
          <div className="mt-4 p-4 bg-green-900/20 border border-green-800 rounded-lg">
            <div className="text-green-400 font-medium mb-3">
              {searchJob.result.strategies_found}개 전략을 찾았습니다! 아래 목록에서 클릭하면 상세 분석을 볼 수 있습니다.
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs border-b border-gray-700">
                    <th className="text-left py-1 pr-3">순위</th>
                    <th className="text-left py-1 pr-3">전략</th>
                    <th className="text-center py-1 pr-3">등급</th>
                    <th className="text-right py-1 pr-3" title="종합 점수 (100점 만점)">종합점수</th>
                    <th className="text-right py-1 pr-3" title="백테스트 기간 총 수익률">수익률</th>
                    <th className="text-right py-1" title="위험 대비 수익 비율. 1 이상이면 양호, 2 이상이면 우수">샤프비율</th>
                  </tr>
                </thead>
                <tbody>
                  {searchJob.result.strategies.map((s, i) => {
                    const { grade, bg } = gradeInfo(s.score);
                    return (
                      <tr key={s.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 cursor-pointer"
                        onClick={() => router.push(`/dashboard/strategies/${s.id}`)}>
                        <td className="py-2 pr-3 text-gray-500">#{i + 1}</td>
                        <td className="py-2 pr-3 text-gray-300">{typeName(s.name.split("_")[0])}</td>
                        <td className="py-2 pr-3 text-center"><span className={`${bg} text-white text-xs font-bold px-2 py-0.5 rounded-full`}>{grade}</span></td>
                        <td className="py-2 pr-3 text-right font-mono text-white">{s.score.toFixed(1)}</td>
                        <td className={`py-2 pr-3 text-right font-mono font-medium ${s.total_return >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {s.total_return >= 0 ? "+" : ""}{s.total_return.toFixed(1)}%
                        </td>
                        <td className={`py-2 text-right font-mono ${s.sharpe_ratio >= 2 ? "text-green-400" : s.sharpe_ratio >= 1 ? "text-blue-400" : "text-gray-400"}`}>
                          {s.sharpe_ratio.toFixed(2)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              각 행을 클릭하면 에쿼티 커브, 거래 내역, 검증 결과를 상세히 볼 수 있습니다.
            </p>
          </div>
        )}

        {searchJob?.status === "error" && (
          <div className="mt-4 p-4 bg-red-900/20 border border-red-800 rounded-lg text-red-400 text-sm">
            {searchJob.error}
          </div>
        )}
      </div>

      {/* Strategy List */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">{t.strategies.myStrategies} ({strategies.length})</h3>
          {strategies.length > 0 && (
            <p className="text-xs text-gray-500">클릭하면 상세 분석 페이지로 이동합니다</p>
          )}
        </div>
        {strategies.length === 0 ? (
          <div className="text-center py-8">
            <div className="text-gray-600 text-4xl mb-3">&#x1F50D;</div>
            <p className="text-gray-500 text-sm">{t.strategies.noStrategies}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {strategies.map((s) => {
              const vr = s.validation_results;
              const bt = vr?.backtest;
              const gi = gradeInfo(s.composite_score);
              return (
                <div key={s.id}
                  onClick={() => router.push(`/dashboard/strategies/${s.id}`)}
                  className="flex items-center justify-between p-4 bg-gray-800 rounded-lg hover:bg-gray-750 cursor-pointer transition-colors border border-transparent hover:border-gray-700">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-medium truncate">{typeName(s.strategy_type)}</h4>
                      <GradeBadge score={s.composite_score} />
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        s.status === "active" ? "bg-green-900/50 text-green-400" :
                        s.status === "validated" ? "bg-blue-900/50 text-blue-400" :
                        s.status === "paused" ? "bg-yellow-900/50 text-yellow-400" :
                        "bg-gray-700 text-gray-400"
                      }`}>{statusLabel(s.status)}</span>
                      {s.stock_name && <span className="text-xs text-gray-500">{s.stock_name}</span>}
                    </div>
                    <div className="flex items-center gap-4 text-xs text-gray-500">
                      <span>{s.stock_code}</span>
                      {bt && (
                        <>
                          <span className={`font-medium ${(bt.total_return || 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                            수익률 {(bt.total_return || 0) >= 0 ? "+" : ""}{(bt.total_return || 0).toFixed(1)}%
                          </span>
                          <span title="위험 대비 수익 비율">샤프 {(bt.sharpe_ratio || 0).toFixed(2)}</span>
                          <span title="최대 낙폭 (최고점 대비 최대 하락)">MDD {(bt.max_drawdown || 0).toFixed(1)}%</span>
                        </>
                      )}
                      {s.composite_score && !bt && (
                        <span className="font-medium text-blue-400">종합점수 {s.composite_score.toFixed(1)}점</span>
                      )}
                      {s.composite_score && <span className="text-gray-600">{gi.label}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <button onClick={(e) => toggleAutoTrading(e, s.id, s.is_auto_trading)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                        s.is_auto_trading
                          ? "bg-red-600/20 text-red-400 hover:bg-red-600/30"
                          : "bg-green-600/20 text-green-400 hover:bg-green-600/30"
                      }`}>
                      {s.is_auto_trading ? "매매 중지" : "자동매매 시작"}
                    </button>
                    <button onClick={(e) => deleteStrategy(e, s.id)}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-700 text-gray-400 hover:bg-red-600/20 hover:text-red-400 transition-colors">
                      삭제
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
