"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import api from "@/lib/api";
import ScoreGauge from "./ScoreGauge";

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
    day_of_week?: Record<
      string,
      { win_rate: number; avg_return: number; sample_count: number }
    >;
    summary?: {
      best_day: string;
      worst_day: string;
      overall_win_rate: number;
    };
    streaks?: Record<string, { reversal_rate: number; sample_count: number }>;
  };
  current_signals: Record<string, { signal: string; accuracy: number }>;
  indicator_accuracy?: {
    ranking_overall?: {
      name: string;
      buy_accuracy: number;
      sell_accuracy: number;
      combined_accuracy: number;
    }[];
  };
}

interface SavedReport {
  id: string;
  stock_code: string;
  stock_name: string | null;
  decision: string;
  confidence: number;
  news_sentiment: string | null;
  full_result: AIAnalysis;
  created_at: string | null;
}

interface AiAnalysisTabProps {
  stockCode: string;
  stockName: string | null;
  dateRangeStart: string;
  dateRangeEnd: string;
}

function formatDateTime(iso: string | null): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString("ko-KR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function AiAnalysisTab({
  stockCode,
  stockName,
  dateRangeStart,
  dateRangeEnd,
}: AiAnalysisTabProps) {
  const [aiResult, setAiResult] = useState<AIAnalysis | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [savedReports, setSavedReports] = useState<SavedReport[]>([]);
  const [loadingSaved, setLoadingSaved] = useState(true);
  const [activeReportIdx, setActiveReportIdx] = useState(0);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  // Load saved reports on mount
  useEffect(() => {
    loadSavedReports();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [stockCode]);

  const loadSavedReports = async () => {
    setLoadingSaved(true);
    try {
      const { data } = await api.get("/analysis/ai-reports", {
        params: { stock_code: stockCode, limit: 10 },
      });
      setSavedReports(data);
      if (data.length > 0) {
        setAiResult(data[0].full_result);
        setActiveReportIdx(0);
      }
    } catch {
      // No saved reports or endpoint not available
    } finally {
      setLoadingSaved(false);
    }
  };

  const startAiAnalysis = useCallback(async () => {
    setAiLoading(true);
    setAiResult(null);
    setAiError(null);
    try {
      const { data: job } = await api.post("/analysis/ai-report", {
        stock_code: stockCode,
        date_range_start: dateRangeStart || "2024-01-01",
        date_range_end: dateRangeEnd || "2025-12-31",
        include_macro: true,
      });
      pollAiJob(job.job_id);
    } catch (e: any) {
      setAiError(
        `AI 분석 시작 실패: ${e.response?.data?.detail || e.message}`
      );
      setAiLoading(false);
    }
  }, [stockCode, dateRangeStart, dateRangeEnd]);

  const pollAiJob = (jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const { data: job } = await api.get(`/analysis/ai-report/${jobId}`);
        if (job.status === "complete") {
          if (pollRef.current) clearInterval(pollRef.current);
          setAiResult(job.result);
          setAiLoading(false);
          // Reload saved reports to include newly saved one
          loadSavedReports();
        } else if (job.status === "error") {
          if (pollRef.current) clearInterval(pollRef.current);
          setAiError(`AI 분석 실패: ${job.error}`);
          setAiLoading(false);
        }
      } catch {
        if (pollRef.current) clearInterval(pollRef.current);
        setAiError("AI 분석 상태 확인 실패");
        setAiLoading(false);
      }
    }, 2000);
  };

  // Switch to a saved report
  const switchToReport = (idx: number) => {
    setActiveReportIdx(idx);
    setAiResult(savedReports[idx].full_result);
  };

  // Count buy vs sell signals
  const signalCounts =
    aiResult?.current_signals
      ? Object.values(aiResult.current_signals).reduce(
          (acc, s) => {
            if (s.signal === "buy") acc.buy++;
            else acc.sell++;
            return acc;
          },
          { buy: 0, sell: 0 }
        )
      : { buy: 0, sell: 0 };
  const totalSignals = signalCounts.buy + signalCounts.sell;

  // Currently active saved report metadata
  const activeReport = savedReports[activeReportIdx] ?? null;

  return (
    <div className="space-y-6">
      {/* Saved report history bar */}
      {savedReports.length > 0 && !aiLoading && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-semibold text-gray-400">
              저장된 분석 이력 ({savedReports.length}건)
            </h4>
            <button
              onClick={startAiAnalysis}
              className="px-4 py-1.5 bg-purple-600 hover:bg-purple-700 rounded-lg text-xs font-medium transition-colors"
            >
              재분석
            </button>
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {savedReports.map((report, idx) => (
              <button
                key={report.id}
                onClick={() => switchToReport(idx)}
                className={`flex-shrink-0 px-3 py-2 rounded-lg text-xs font-medium transition-colors border ${
                  idx === activeReportIdx
                    ? "bg-purple-600/20 border-purple-700 text-purple-300"
                    : "bg-gray-800 border-gray-700 text-gray-400 hover:text-white"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`font-bold ${
                      report.decision === "매수"
                        ? "text-green-400"
                        : report.decision === "매도"
                          ? "text-red-400"
                          : "text-yellow-400"
                    }`}
                  >
                    {report.decision}
                  </span>
                  <span className="text-gray-600">|</span>
                  <span>확신 {report.confidence}/10</span>
                </div>
                <div className="text-[10px] text-gray-600 mt-0.5">
                  {formatDateTime(report.created_at)}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Initial state - no saved reports */}
      {!aiResult && !aiLoading && !aiError && !loadingSaved && savedReports.length === 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-8 text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-purple-900/30 border border-purple-700/50 flex items-center justify-center">
            <svg
              className="w-8 h-8 text-purple-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5"
              />
            </svg>
          </div>
          <h3 className="text-lg font-semibold mb-2">AI 하이브리드 분석</h3>
          <p className="text-sm text-gray-500 mb-1">
            {stockCode} {stockName && `(${stockName})`}
          </p>
          <p className="text-sm text-gray-500 mb-4">
            통계 엔진이 시간패턴, 지표 적중률, 매크로 상관관계를 분석하고,
            <br />
            DeepSeek AI가 뉴스 감성과 함께 종합 매매 판단을 내립니다.
          </p>
          <button
            onClick={startAiAnalysis}
            className="px-8 py-3 bg-purple-600 hover:bg-purple-700 rounded-lg text-sm font-medium transition-colors"
          >
            AI 분석 시작
          </button>
        </div>
      )}

      {/* Loading saved reports */}
      {loadingSaved && !aiResult && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 text-center">
          <div className="flex items-center justify-center gap-2 text-gray-400 text-sm">
            <div className="w-4 h-4 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
            저장된 분석 결과 불러오는 중...
          </div>
        </div>
      )}

      {/* Error state */}
      {aiError && !aiLoading && (
        <div className="bg-red-900/20 rounded-xl border border-red-800 p-6 text-center">
          <div className="text-red-400 text-sm mb-3">{aiError}</div>
          <button
            onClick={startAiAnalysis}
            className="px-6 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg text-sm font-medium transition-colors"
          >
            다시 시도
          </button>
        </div>
      )}

      {/* Loading state - skeleton cards */}
      {aiLoading && (
        <div className="space-y-4">
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-gray-400 text-sm">
                통계 분석 + AI 판단 생성 중... (약 15-30초)
              </span>
            </div>
            <p className="text-xs text-gray-600">
              Layer 1 (통계) → Layer 2 (팩트시트) → Layer 3 (DeepSeek AI)
            </p>
          </div>
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-gray-900 rounded-xl border border-gray-800 p-6 animate-pulse"
            >
              <div className="h-4 bg-gray-800 rounded w-1/3 mb-4" />
              <div className="space-y-3">
                <div className="h-3 bg-gray-800 rounded w-full" />
                <div className="h-3 bg-gray-800 rounded w-5/6" />
                <div className="h-3 bg-gray-800 rounded w-4/6" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Results */}
      {aiResult && !aiLoading && (
        <>
          {/* Analysis date badge */}
          {activeReport?.created_at && (
            <div className="text-xs text-gray-600 text-right">
              분석 일시: {formatDateTime(activeReport.created_at)}
            </div>
          )}

          {/* AI Decision Card */}
          <div
            className={`rounded-xl border p-6 ${
              aiResult.ai_analysis.decision === "매수"
                ? "bg-green-900/20 border-green-800"
                : aiResult.ai_analysis.decision === "매도"
                  ? "bg-red-900/20 border-red-800"
                  : "bg-gray-900 border-gray-800"
            }`}
          >
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-4">
                <div className="flex flex-col items-center">
                  <span
                    className={`text-3xl font-bold ${
                      aiResult.ai_analysis.decision === "매수"
                        ? "text-green-400"
                        : aiResult.ai_analysis.decision === "매도"
                          ? "text-red-400"
                          : "text-yellow-400"
                    }`}
                  >
                    {aiResult.ai_analysis.decision}
                  </span>
                </div>
                <ScoreGauge
                  value={aiResult.ai_analysis.confidence * 10}
                  label="확신도"
                  size={72}
                />
              </div>
              <span
                className={`px-3 py-1 rounded-full text-xs font-medium ${
                  aiResult.ai_analysis.news_sentiment === "긍정"
                    ? "bg-green-900/50 text-green-400"
                    : aiResult.ai_analysis.news_sentiment === "부정"
                      ? "bg-red-900/50 text-red-400"
                      : "bg-gray-700 text-gray-400"
                }`}
              >
                뉴스: {aiResult.ai_analysis.news_sentiment}
              </span>
            </div>

            {/* Signal strength meter */}
            {totalSignals > 0 && (
              <div className="mb-4 bg-black/20 rounded-lg p-3">
                <div className="flex items-center justify-between text-xs text-gray-500 mb-1.5">
                  <span>매수 시그널 {signalCounts.buy}개</span>
                  <span>매도 시그널 {signalCounts.sell}개</span>
                </div>
                <div className="flex h-2.5 rounded-full overflow-hidden">
                  <div
                    className="bg-green-500 transition-all"
                    style={{
                      width: `${(signalCounts.buy / totalSignals) * 100}%`,
                    }}
                  />
                  <div
                    className="bg-red-500 transition-all"
                    style={{
                      width: `${(signalCounts.sell / totalSignals) * 100}%`,
                    }}
                  />
                </div>
              </div>
            )}

            <div className="bg-black/20 rounded-lg p-4 text-sm whitespace-pre-wrap">
              {aiResult.ai_analysis.raw_response}
            </div>

            <div className="text-xs text-gray-600 mt-3">
              모델: DeepSeek | 토큰:{" "}
              {aiResult.ai_analysis.tokens_used?.total || 0}
            </div>
          </div>

          {/* Current Signals */}
          {Object.keys(aiResult.current_signals || {}).length > 0 && (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
              <h4 className="text-sm font-semibold text-gray-400 mb-3">
                현재 활성 시그널
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {Object.entries(aiResult.current_signals).map(
                  ([name, info]) => (
                    <div
                      key={name}
                      className={`rounded-lg p-3 ${info.signal === "buy" ? "bg-green-900/20 border border-green-800" : "bg-red-900/20 border border-red-800"}`}
                    >
                      <div className="text-xs text-gray-400">{name}</div>
                      <div
                        className={`text-sm font-bold ${info.signal === "buy" ? "text-green-400" : "text-red-400"}`}
                      >
                        {info.signal === "buy" ? "매수" : "매도"} (적중률{" "}
                        {info.accuracy}%)
                      </div>
                    </div>
                  )
                )}
              </div>
            </div>
          )}

          {/* Time Patterns */}
          {aiResult.time_patterns?.day_of_week && (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
              <h4 className="text-sm font-semibold text-gray-400 mb-3">
                요일별 승률 패턴
              </h4>
              <div className="flex gap-2">
                {Object.entries(aiResult.time_patterns.day_of_week).map(
                  ([day, stats]) => (
                    <div key={day} className="flex-1 text-center">
                      <div className="text-xs text-gray-500 mb-1">{day}</div>
                      <div
                        className={`text-lg font-bold ${stats.win_rate >= 55 ? "text-green-400" : stats.win_rate <= 45 ? "text-red-400" : "text-gray-300"}`}
                      >
                        {stats.win_rate}%
                      </div>
                      <div className="w-full bg-gray-800 rounded-full h-2 mt-1">
                        <div
                          className={`h-2 rounded-full ${stats.win_rate >= 50 ? "bg-green-500" : "bg-red-500"}`}
                          style={{ width: `${stats.win_rate}%` }}
                        />
                      </div>
                      <div className="text-[10px] text-gray-600 mt-1">
                        {stats.sample_count}일
                      </div>
                    </div>
                  )
                )}
              </div>
              {aiResult.time_patterns.summary && (
                <p className="text-xs text-gray-600 mt-3">
                  최고: {aiResult.time_patterns.summary.best_day} | 최저:{" "}
                  {aiResult.time_patterns.summary.worst_day} | 전체 승률:{" "}
                  {aiResult.time_patterns.summary.overall_win_rate}%
                </p>
              )}
            </div>
          )}

          {/* Indicator Accuracy */}
          {aiResult.indicator_accuracy?.ranking_overall && (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
              <h4 className="text-sm font-semibold text-gray-400 mb-3">
                지표 적중률 랭킹
              </h4>
              <div className="space-y-2">
                {aiResult.indicator_accuracy.ranking_overall
                  .slice(0, 8)
                  .map((ind, i) => (
                    <div key={ind.name} className="flex items-center gap-3">
                      <span className="text-xs text-gray-600 w-6">
                        #{i + 1}
                      </span>
                      <span className="text-sm text-gray-300 w-40 truncate">
                        {ind.name}
                      </span>
                      <div className="flex-1 flex items-center gap-2">
                        <div className="flex-1 bg-gray-800 rounded-full h-2">
                          <div
                            className="bg-blue-500 h-2 rounded-full"
                            style={{
                              width: `${ind.combined_accuracy}%`,
                            }}
                          />
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
              <h4 className="text-sm font-semibold text-gray-400 mb-3">
                최근 뉴스
              </h4>
              <div className="space-y-2">
                {aiResult.news.map((n, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm">
                    <span className="text-gray-600">{i + 1}.</span>
                    <div>
                      <div className="text-gray-300">{n.title}</div>
                      <div className="text-xs text-gray-600">
                        {n.source} {n.date && `| ${n.date}`}
                      </div>
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
  );
}
