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

function GradeBadge({ score }: { score: number | null }) {
  if (!score) return null;
  let grade: string, bg: string;
  if (score >= 90) { grade = "A+"; bg = "bg-green-600"; }
  else if (score >= 80) { grade = "A"; bg = "bg-green-500"; }
  else if (score >= 70) { grade = "B+"; bg = "bg-blue-500"; }
  else if (score >= 60) { grade = "B"; bg = "bg-blue-400"; }
  else if (score >= 50) { grade = "C+"; bg = "bg-yellow-500"; }
  else if (score >= 40) { grade = "C"; bg = "bg-yellow-600"; }
  else { grade = "D"; bg = "bg-red-500"; }
  return <span className={`${bg} text-white text-xs font-bold px-2 py-0.5 rounded-full`}>{grade}</span>;
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
      // Start polling
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
    if (step.startsWith("optimizing:")) return `최적화: ${step.split(":")[1]}`;
    if (step.startsWith("validating:")) return `검증: ${step.split(":")[1]}`;
    if (step === "fetching_data") return "데이터 수집 중...";
    if (step === "optimizing") return "전략 최적화 시작...";
    if (step === "validating") return "전략 검증 중...";
    if (step === "done") return "완료!";
    return step;
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">{t.strategies.title}</h2>

      {/* Strategy Search */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <h3 className="text-lg font-semibold mb-2">{t.strategies.aiSearch}</h3>
        <p className="text-sm text-gray-500 mb-4">{t.strategies.aiSearchDesc}</p>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mb-3">
          <input type="text" value={searchCode} onChange={(e) => setSearchCode(e.target.value)}
            placeholder={t.strategies.stockCodePlaceholder}
            className="px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500" />
          <input type="date" value={dateStart} onChange={(e) => setDateStart(e.target.value)}
            className="px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500" />
          <input type="date" value={dateEnd} onChange={(e) => setDateEnd(e.target.value)}
            className="px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500" />
          <select value={method} onChange={(e) => setMethod(e.target.value)}
            className="px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500">
            <option value="grid">Grid Search</option>
            <option value="genetic">Genetic Algorithm</option>
            <option value="bayesian">Bayesian (Optuna)</option>
          </select>
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
          </div>
        )}

        {/* Results */}
        {searchJob?.status === "complete" && searchJob.result && (
          <div className="mt-4 p-4 bg-green-900/20 border border-green-800 rounded-lg">
            <div className="text-green-400 font-medium mb-2">
              {searchJob.result.strategies_found}개 전략을 찾았습니다!
            </div>
            <div className="space-y-2">
              {searchJob.result.strategies.map((s, i) => (
                <div key={s.id} className="flex items-center justify-between text-sm">
                  <span className="text-gray-300">#{i + 1} {s.name}</span>
                  <span className="flex items-center gap-2">
                    <span className="text-gray-400">Score: {s.score.toFixed(1)}</span>
                    <span className={s.total_return >= 0 ? "text-green-400" : "text-red-400"}>
                      {s.total_return >= 0 ? "+" : ""}{s.total_return.toFixed(1)}%
                    </span>
                    <span className="text-gray-400">Sharpe: {s.sharpe_ratio.toFixed(2)}</span>
                  </span>
                </div>
              ))}
            </div>
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
        <h3 className="text-lg font-semibold mb-4">{t.strategies.myStrategies} ({strategies.length})</h3>
        {strategies.length === 0 ? (
          <p className="text-gray-600 text-sm">{t.strategies.noStrategies}</p>
        ) : (
          <div className="space-y-2">
            {strategies.map((s) => {
              const vr = s.validation_results;
              const bt = vr?.backtest;
              return (
                <div key={s.id}
                  onClick={() => router.push(`/dashboard/strategies/${s.id}`)}
                  className="flex items-center justify-between p-4 bg-gray-800 rounded-lg hover:bg-gray-750 cursor-pointer transition-colors border border-transparent hover:border-gray-700">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-medium truncate">{s.name}</h4>
                      <GradeBadge score={s.composite_score} />
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        s.status === "active" ? "bg-green-900/50 text-green-400" :
                        s.status === "validated" ? "bg-blue-900/50 text-blue-400" :
                        "bg-gray-700 text-gray-400"
                      }`}>{s.status}</span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-gray-500">
                      <span>{s.stock_code}</span>
                      <span>{s.strategy_type}</span>
                      {bt && (
                        <>
                          <span className={`font-medium ${(bt.total_return || 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                            {(bt.total_return || 0) >= 0 ? "+" : ""}{(bt.total_return || 0).toFixed(1)}%
                          </span>
                          <span>Sharpe: {(bt.sharpe_ratio || 0).toFixed(2)}</span>
                          <span>MDD: {(bt.max_drawdown || 0).toFixed(1)}%</span>
                        </>
                      )}
                      {s.composite_score && !bt && (
                        <span className="font-medium text-blue-400">Score: {s.composite_score.toFixed(1)}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <button onClick={(e) => toggleAutoTrading(e, s.id, s.is_auto_trading)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                        s.is_auto_trading
                          ? "bg-red-600/20 text-red-400 hover:bg-red-600/30"
                          : "bg-green-600/20 text-green-400 hover:bg-green-600/30"
                      }`}>
                      {s.is_auto_trading ? t.common.stop : t.common.activate}
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
