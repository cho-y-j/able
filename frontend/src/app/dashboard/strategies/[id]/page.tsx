"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import api from "@/lib/api";
import { BarChart3, TrendingUp, List, Shield, Settings, Bot } from "lucide-react";
import { GradeBadge } from "../_components/GradeBadge";
import ScoreGauge from "./_components/ScoreGauge";
import OverviewTab from "./_components/OverviewTab";
import EquityCurveTab from "./_components/EquityCurveTab";
import TradeLogTab from "./_components/TradeLogTab";
import ValidationTab from "./_components/ValidationTab";
import ParamAdjustTab from "./_components/ParamAdjustTab";
import AiAnalysisTab from "./_components/AiAnalysisTab";

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
    oos_detail?: { in_sample?: Record<string, unknown>; out_of_sample?: Record<string, unknown>; degradation?: Record<string, number> };
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
  type: string; current: number | string | null;
  min: number | null; max: number | null; choices: string[] | null;
}

type TabKey = "overview" | "equity" | "trades" | "validation" | "params" | "ai";

const TABS: { key: TabKey; label: string; icon: typeof BarChart3 }[] = [
  { key: "overview", label: "성과 지표", icon: BarChart3 },
  { key: "equity", label: "에쿼티 커브", icon: TrendingUp },
  { key: "trades", label: "거래 내역", icon: List },
  { key: "validation", label: "검증 결과", icon: Shield },
  { key: "params", label: "파라미터 조정", icon: Settings },
  { key: "ai", label: "AI 분석", icon: Bot },
];

export default function StrategyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [data, setData] = useState<StrategyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabKey>("overview");
  const [paramRanges, setParamRanges] = useState<Record<string, ParamRange>>({});

  useEffect(() => {
    if (params.id) fetchDetail(params.id as string);
  }, [params.id]);

  const fetchDetail = async (id: string) => {
    try {
      const { data: d } = await api.get(`/strategies/${id}/detail`);
      setData(d);
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

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
  if (!data) return <div className="text-red-500 text-center py-12">전략을 찾을 수 없습니다.</div>;

  const bt = data.backtest;
  const m = bt?.metrics;
  const v = bt?.validation;

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <button onClick={() => router.push("/dashboard/strategies")}
            className="text-sm text-gray-500 hover:text-white mb-2 flex items-center gap-1 transition-colors">
            &larr; 전략 목록
          </button>
          <div className="flex items-center gap-3 mb-1">
            <ScoreGauge value={data.composite_score} label="종합" size={60} />
            <div>
              <h2 className="text-2xl font-bold flex items-center gap-3">
                {data.name}
                <GradeBadge score={data.composite_score} size="md" />
              </h2>
              <p className="text-gray-500 text-sm mt-0.5">
                {data.stock_code} {data.stock_name && `(${data.stock_name})`} | {data.strategy_type} | {data.status}
              </p>
            </div>
          </div>
          {/* Key metrics badges */}
          {m && (
            <div className="flex items-center gap-2 mt-2">
              <span className={`text-xs px-2.5 py-1 rounded-full font-mono font-medium ${(m.total_return ?? 0) >= 0 ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"}`}>
                수익 {m.total_return != null ? `${m.total_return > 0 ? "+" : ""}${m.total_return.toFixed(1)}%` : "N/A"}
              </span>
              <span className="text-xs px-2.5 py-1 rounded-full font-mono font-medium bg-blue-500/10 text-blue-400">
                샤프 {m.sharpe_ratio?.toFixed(2) ?? "N/A"}
              </span>
              <span className={`text-xs px-2.5 py-1 rounded-full font-mono font-medium ${(m.max_drawdown ?? 0) >= -20 ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"}`}>
                MDD {m.max_drawdown?.toFixed(1) ?? "N/A"}%
              </span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-3 mt-1">
          <button onClick={() => setTab("ai")}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5">
            <Bot className="w-4 h-4" /> AI 분석
          </button>
          <div className={`px-4 py-2 rounded-lg text-sm font-medium ${data.is_auto_trading ? "bg-green-600/20 text-green-400 border border-green-800/50" : "bg-gray-700 text-gray-400"}`}>
            {data.is_auto_trading ? "자동매매 활성" : "비활성"}
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 mb-6 bg-gray-900 rounded-lg p-1 border border-gray-800 overflow-x-auto">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setTab(key)}
            className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors whitespace-nowrap flex items-center justify-center gap-1.5 ${
              tab === key ? "bg-blue-600 text-white" : "text-gray-400 hover:text-white"
            }`}>
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "overview" && m && (
        <OverviewTab metrics={m} validation={v ?? null} compositeScore={data.composite_score} />
      )}

      {tab === "equity" && (
        <EquityCurveTab
          equityCurve={bt?.equity_curve ?? null}
          dateRangeStart={bt?.date_range_start ?? ""}
          dateRangeEnd={bt?.date_range_end ?? ""}
          totalReturn={m?.total_return ?? 0}
        />
      )}

      {tab === "trades" && (
        <TradeLogTab tradeLog={bt?.trade_log ?? []} />
      )}

      {tab === "validation" && data.validation_results && (
        <ValidationTab validationResults={data.validation_results} />
      )}

      {tab === "params" && (
        <ParamAdjustTab
          strategyId={data.id}
          parameters={data.parameters}
          riskParams={data.risk_params}
          paramRanges={paramRanges}
          onRebacktestComplete={() => fetchDetail(data.id)}
        />
      )}

      {tab === "ai" && (
        <AiAnalysisTab
          stockCode={data.stock_code}
          stockName={data.stock_name}
          dateRangeStart={bt?.date_range_start ?? "2024-01-01"}
          dateRangeEnd={bt?.date_range_end ?? "2025-12-31"}
        />
      )}
    </div>
  );
}
