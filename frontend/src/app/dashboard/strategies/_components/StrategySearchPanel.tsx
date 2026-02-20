"use client";

import { useState, useRef } from "react";
import api from "@/lib/api";
import { useI18n } from "@/i18n";
import { GradeBadge, gradeInfo } from "./GradeBadge";
import { STRATEGY_TYPE_LABELS, STRATEGY_TYPE_INFO } from "./StrategyCard";
import { StockAutocomplete } from "@/components/StockAutocomplete";

interface SearchJob {
  job_id: string;
  status: string;
  progress: number;
  step: string;
  result: {
    strategies_found: number;
    strategies: {
      id: string;
      name: string;
      score: number;
      grade: string;
      total_return: number;
      sharpe_ratio: number;
    }[];
  } | null;
  error: string | null;
}

interface StrategySearchPanelProps {
  onSearchComplete: (stockCode: string) => void;
  onNavigate: (strategyId: string) => void;
}

function stepLabel(step: string): string {
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
}

function typeName(t: string): string {
  return STRATEGY_TYPE_LABELS[t] || t;
}

export function StrategySearchPanel({
  onSearchComplete,
  onNavigate,
}: StrategySearchPanelProps) {
  const { t } = useI18n();
  const [searchCode, setSearchCode] = useState("");
  const [market, setMarket] = useState("kr");
  const [dateStart, setDateStart] = useState("2024-01-01");
  const [dateEnd, setDateEnd] = useState("2025-12-31");
  const [method, setMethod] = useState("grid");
  const [searchJob, setSearchJob] = useState<SearchJob | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
        market,
      });
      const jobId = data.job_id;
      setSearchJob({
        job_id: jobId,
        status: "running",
        progress: 0,
        step: "initializing",
        result: null,
        error: null,
      });

      pollingRef.current = setInterval(async () => {
        try {
          const { data: job } = await api.get(
            `/strategies/search-jobs/${jobId}`
          );
          setSearchJob(job);
          if (job.status === "complete" || job.status === "error") {
            if (pollingRef.current) clearInterval(pollingRef.current);
            pollingRef.current = null;
            setSearchLoading(false);
            if (job.status === "complete") {
              onSearchComplete(searchCode.trim());
            }
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

  return (
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
              <p>
                종목코드(005930) 또는 종목명(삼성전자)을 입력합니다. 분석할
                기간과 최적화 방법을 선택하세요.
              </p>
            </div>
            <div className="bg-gray-800 rounded-lg p-3">
              <div className="text-blue-400 font-bold mb-1">2단계: AI 탐색</div>
              <p>
                23개 매매 전략을 자동으로 테스트하고, 최적의 파라미터를 찾은 뒤
                Walk-Forward, Monte Carlo, OOS 검증을 수행합니다.
              </p>
            </div>
            <div className="bg-gray-800 rounded-lg p-3">
              <div className="text-blue-400 font-bold mb-1">
                3단계: 결과 확인
              </div>
              <p>
                각 전략을 클릭하면 상세 성과, 에쿼티 커브, 거래 내역, 검증
                결과를 확인할 수 있습니다. 마음에 드는 전략은 자동매매를
                활성화하세요.
              </p>
            </div>
          </div>
          <div className="mt-2 p-3 bg-gray-800 rounded-lg">
            <div className="text-white font-bold mb-1">등급 기준</div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
              <span>
                <span className="text-green-400 font-bold">A+</span> (90+) 최우수
              </span>
              <span>
                <span className="text-green-400 font-bold">A</span> (80+) 우수
              </span>
              <span>
                <span className="text-blue-400 font-bold">B+</span> (70+) 양호
              </span>
              <span>
                <span className="text-blue-400 font-bold">B</span> (60+) 보통
              </span>
              <span>
                <span className="text-yellow-400 font-bold">C+</span> (50+) 미흡
              </span>
              <span>
                <span className="text-yellow-400 font-bold">C</span> (40+) 부족
              </span>
              <span>
                <span className="text-red-400 font-bold">D</span> (&lt;40) 위험
              </span>
            </div>
          </div>
        </div>
      </details>

      {/* Market toggle */}
      <div className="flex gap-2 mb-3">
        <button
          type="button"
          onClick={() => setMarket("kr")}
          className={`px-4 py-1.5 rounded-full text-xs font-medium transition-colors ${
            market === "kr"
              ? "bg-blue-600 text-white"
              : "bg-gray-800 text-gray-400 hover:bg-gray-700"
          }`}
        >
          {t.market?.marketKr || "한국"}
        </button>
        <button
          type="button"
          onClick={() => setMarket("us")}
          className={`px-4 py-1.5 rounded-full text-xs font-medium transition-colors ${
            market === "us"
              ? "bg-blue-600 text-white"
              : "bg-gray-800 text-gray-400 hover:bg-gray-700"
          }`}
        >
          {t.market?.marketUs || "해외"}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mb-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">{t.market?.stockSearch || "종목"}</label>
          <StockAutocomplete
            value={searchCode}
            onChange={setSearchCode}
            onSelect={(code) => setSearchCode(code)}
            placeholder={t.strategies.stockCodePlaceholder}
            market={market}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">시작일</label>
          <input
            type="date"
            value={dateStart}
            onChange={(e) => setDateStart(e.target.value)}
            className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">종료일</label>
          <input
            type="date"
            value={dateEnd}
            onChange={(e) => setDateEnd(e.target.value)}
            className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">
            최적화 방법
          </label>
          <select
            value={method}
            onChange={(e) => setMethod(e.target.value)}
            className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
          >
            <option value="grid">Grid Search (빠름, 기본)</option>
            <option value="genetic">Genetic (정확, 느림)</option>
            <option value="bayesian">Bayesian (최적, 느림)</option>
          </select>
        </div>
      </div>
      <button
        onClick={startSearch}
        disabled={searchLoading || !searchCode.trim()}
        className="w-full sm:w-auto px-8 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 rounded-lg text-sm font-medium transition-colors"
      >
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
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-500"
              style={{ width: `${searchJob.progress}%` }}
            />
          </div>
          <p className="text-xs text-gray-600 mt-1">
            {searchJob.progress < 60
              ? "23개 전략의 파라미터를 최적화하고 있습니다. 약 30초~1분 소요됩니다."
              : "상위 전략의 안정성을 검증하고 있습니다. 거의 완료되었습니다."}
          </p>
        </div>
      )}

      {/* Results */}
      {searchJob?.status === "complete" && searchJob.result && (
        <div className="mt-4 p-4 bg-green-900/20 border border-green-800 rounded-lg">
          <div className="text-green-400 font-medium mb-3">
            {searchJob.result.strategies_found}개 전략을 찾았습니다! 아래
            목록에서 클릭하면 상세 분석을 볼 수 있습니다.
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs border-b border-gray-700">
                  <th className="text-left py-1 pr-3">순위</th>
                  <th className="text-left py-1 pr-3">전략</th>
                  <th className="text-center py-1 pr-3">등급</th>
                  <th
                    className="text-right py-1 pr-3"
                    title="종합 점수 (100점 만점)"
                  >
                    종합점수
                  </th>
                  <th
                    className="text-right py-1 pr-3"
                    title="백테스트 기간 총 수익률"
                  >
                    수익률
                  </th>
                  <th
                    className="text-right py-1"
                    title="위험 대비 수익 비율. 1 이상이면 양호, 2 이상이면 우수"
                  >
                    샤프비율
                  </th>
                </tr>
              </thead>
              <tbody>
                {searchJob.result.strategies.map((s, i) => {
                  const { grade, bg } = gradeInfo(s.score);
                  return (
                    <tr
                      key={`${s.id}-${i}`}
                      className="border-b border-gray-800/50 hover:bg-gray-800/30 cursor-pointer"
                      onClick={() => onNavigate(s.id)}
                    >
                      <td className="py-2 pr-3 text-gray-500">#{i + 1}</td>
                      <td className="py-2 pr-3">
                        <div className="flex items-center gap-2">
                          <span className="text-gray-300">{typeName(s.name.split("_")[0])}</span>
                          {(() => {
                            const sType = s.name.split("_").slice(0, -1).join("_") || s.name.split("_")[0];
                            const info = STRATEGY_TYPE_INFO[sType] || STRATEGY_TYPE_INFO[s.name.split("_")[0]];
                            return info ? (
                              <span className={`text-xs px-1 py-0.5 rounded ${
                                ({ "추세추종": "bg-blue-500/20 text-blue-300", "모멘텀": "bg-purple-500/20 text-purple-300", "변동성": "bg-orange-500/20 text-orange-300", "거래량": "bg-cyan-500/20 text-cyan-300", "복합": "bg-emerald-500/20 text-emerald-300" } as Record<string, string>)[info.category] || "bg-gray-700 text-gray-400"
                              }`}>{info.category}</span>
                            ) : null;
                          })()}
                        </div>
                        {(() => {
                          const sType = s.name.split("_").slice(0, -1).join("_") || s.name.split("_")[0];
                          const info = STRATEGY_TYPE_INFO[sType] || STRATEGY_TYPE_INFO[s.name.split("_")[0]];
                          return info ? (
                            <p className="text-xs text-gray-600 mt-0.5 line-clamp-1">{info.description}</p>
                          ) : null;
                        })()}
                      </td>
                      <td className="py-2 pr-3 text-center">
                        <span
                          className={`${bg} text-white text-xs font-bold px-2 py-0.5 rounded-full`}
                        >
                          {grade}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-right font-mono text-white">
                        {s.score.toFixed(1)}
                      </td>
                      <td
                        className={`py-2 pr-3 text-right font-mono font-medium ${
                          s.total_return >= 0 ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        {s.total_return >= 0 ? "+" : ""}
                        {s.total_return.toFixed(1)}%
                      </td>
                      <td
                        className={`py-2 text-right font-mono ${
                          s.sharpe_ratio >= 2
                            ? "text-green-400"
                            : s.sharpe_ratio >= 1
                              ? "text-blue-400"
                              : "text-gray-400"
                        }`}
                      >
                        {s.sharpe_ratio.toFixed(2)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            각 행을 클릭하면 에쿼티 커브, 거래 내역, 검증 결과를 상세히 볼 수
            있습니다.
          </p>
        </div>
      )}

      {searchJob?.status === "error" && (
        <div className="mt-4 p-4 bg-red-900/20 border border-red-800 rounded-lg text-red-400 text-sm">
          {searchJob.error}
        </div>
      )}
    </div>
  );
}
