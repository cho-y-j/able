"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import api from "@/lib/api";
import SignalSelector from "./_components/SignalSelector";
import ParamTuner from "./_components/ParamTuner";
import FilterBuilder from "./_components/FilterBuilder";
import RiskConfig from "./_components/RiskConfig";
import ExecutionPanel from "./_components/ExecutionPanel";
import PerformancePanel from "./_components/PerformancePanel";
import type { SignalEntry, Combinator } from "../types";

const STEPS = [
  { key: "signals", label: "시그널 선택" },
  { key: "params", label: "파라미터 조정" },
  { key: "filters", label: "필터 + 종목" },
  { key: "risk", label: "리스크 + 백테스트" },
  { key: "execution", label: "실행 현황" },
  { key: "performance", label: "성과" },
] as const;

export default function RecipeBuilderPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const recipeId = params.id === "new" ? null : (params.id as string);
  const fromStrategyId = searchParams.get("from_strategy");

  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [signals, setSignals] = useState<SignalEntry[]>([]);
  const [combinator, setCombinator] = useState<Combinator>("AND");
  const [minAgree, setMinAgree] = useState(2);
  const [customFilters, setCustomFilters] = useState<Record<string, unknown>>({});
  const [stockCodes, setStockCodes] = useState<string[]>([]);
  const [riskConfig, setRiskConfig] = useState<Record<string, number>>({
    stop_loss: 3,
    take_profit: 5,
    position_size: 10,
  });
  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState<string | null>(recipeId);
  const [isActive, setIsActive] = useState(false);
  const [loading, setLoading] = useState(!!recipeId);
  const [alert, setAlert] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    if (recipeId) {
      loadRecipe();
    } else if (fromStrategyId) {
      loadFromStrategy(fromStrategyId);
    }
  }, [recipeId, fromStrategyId]);

  const loadFromStrategy = async (strategyId: string) => {
    try {
      const { data } = await api.get(`/strategies/${strategyId}/detail`);
      setName(`${data.name} 레시피`);
      setSignals([{
        type: "recommended",
        strategy_type: data.strategy_type,
        params: data.parameters || {},
        weight: 1.0,
      }]);
      setStockCodes(data.stock_code ? [data.stock_code] : []);
      if (data.risk_params) {
        setRiskConfig({
          stop_loss: data.risk_params.stop_loss ?? 3,
          take_profit: data.risk_params.take_profit ?? 5,
          position_size: data.risk_params.position_size ?? 10,
        });
      }
    } catch {
      setAlert({ type: "error", message: "전략 정보를 불러오지 못했습니다" });
    }
  };

  useEffect(() => {
    if (alert) {
      const timer = setTimeout(() => setAlert(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [alert]);

  const loadRecipe = async () => {
    try {
      const { data } = await api.get(`/recipes/${recipeId}`);
      setName(data.name);
      setDescription(data.description || "");
      setSignals(data.signal_config?.signals || []);
      setCombinator(data.signal_config?.combinator || "AND");
      setMinAgree(data.signal_config?.min_agree || 2);
      setCustomFilters(data.custom_filters || {});
      setStockCodes(data.stock_codes || []);
      setRiskConfig(data.risk_config || { stop_loss: 3, take_profit: 5, position_size: 10 });
      setSavedId(data.id);
      setIsActive(data.is_active || false);
    } catch {
      setAlert({ type: "error", message: "레시피를 불러오지 못했습니다" });
    } finally {
      setLoading(false);
    }
  };

  const saveRecipe = async () => {
    if (!name.trim()) return;
    setSaving(true);

    const payload = {
      name: name.trim(),
      description: description.trim() || null,
      signal_config: {
        combinator,
        min_agree: minAgree,
        signals,
      },
      custom_filters: customFilters,
      stock_codes: stockCodes,
      risk_config: riskConfig,
    };

    try {
      if (savedId) {
        await api.put(`/recipes/${savedId}`, payload);
        setAlert({ type: "success", message: "레시피가 저장되었습니다" });
      } else {
        const { data } = await api.post("/recipes", payload);
        setSavedId(data.id);
        router.replace(`/dashboard/recipes/${data.id}`);
        setAlert({ type: "success", message: "레시피가 생성되었습니다" });
      }
    } catch {
      setAlert({ type: "error", message: "저장에 실패했습니다" });
    } finally {
      setSaving(false);
    }
  };

  const activateRecipe = async () => {
    if (!savedId) return;
    try {
      await api.post(`/recipes/${savedId}/activate`);
      setAlert({ type: "success", message: "자동매매가 활성화되었습니다" });
      setTimeout(() => router.push("/dashboard/recipes"), 1000);
    } catch {
      setAlert({ type: "error", message: "활성화에 실패했습니다" });
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 bg-gray-800 rounded w-1/3" />
        <div className="h-64 bg-gray-800 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Alert */}
      {alert && (
        <div
          className={`px-4 py-3 rounded-lg text-sm font-medium ${
            alert.type === "success"
              ? "bg-green-500/10 border border-green-500/30 text-green-400"
              : "bg-red-500/10 border border-red-500/30 text-red-400"
          }`}
        >
          {alert.message}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => router.push("/dashboard/recipes")}
            className="text-gray-400 hover:text-white text-sm mb-2 inline-block"
          >
            &larr; 레시피 목록
          </button>
          <h1 className="text-2xl font-bold text-white">
            {recipeId ? "레시피 편집" : "새 레시피 만들기"}
          </h1>
        </div>
        <div className="flex gap-2">
          <button
            onClick={saveRecipe}
            disabled={saving || !name.trim()}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            {saving ? "저장 중..." : "저장"}
          </button>
          {savedId && (
            <button
              onClick={activateRecipe}
              className="bg-green-600 hover:bg-green-700 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
            >
              자동매매 활성화
            </button>
          )}
        </div>
      </div>

      {/* Name + Description */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="text-xs text-gray-400 block mb-1">레시피 이름</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="예: MACD + RSI 보수적 전략"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="text-xs text-gray-400 block mb-1">설명 (선택)</label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="레시피에 대한 간단한 설명"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Step Navigation */}
      <div className="flex gap-1 bg-gray-800 p-1 rounded-xl">
        {STEPS.map((s, i) => (
          <button
            key={s.key}
            onClick={() => setStep(i)}
            className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              step === i
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-white"
            }`}
          >
            <span className="mr-1.5 text-xs opacity-60">{i + 1}</span>
            {s.label}
          </button>
        ))}
      </div>

      {/* Step Content */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        {step === 0 && (
          <SignalSelector
            selectedSignals={signals}
            combinator={combinator}
            minAgree={minAgree}
            onSignalsChange={setSignals}
            onCombinatorChange={setCombinator}
            onMinAgreeChange={setMinAgree}
          />
        )}
        {step === 1 && (
          <ParamTuner signals={signals} onSignalsChange={setSignals} />
        )}
        {step === 2 && (
          <FilterBuilder
            customFilters={customFilters}
            stockCodes={stockCodes}
            onFiltersChange={setCustomFilters}
            onStockCodesChange={setStockCodes}
          />
        )}
        {step === 3 && (
          <RiskConfig
            recipeId={savedId}
            riskConfig={riskConfig}
            stockCodes={stockCodes}
            onRiskChange={setRiskConfig}
          />
        )}
        {step === 4 && (
          <ExecutionPanel
            recipeId={savedId}
            isActive={isActive}
            stockCodes={stockCodes}
          />
        )}
        {step === 5 && (
          <PerformancePanel recipeId={savedId} />
        )}
      </div>

      {/* Step Navigation Buttons */}
      <div className="flex justify-between">
        <button
          onClick={() => setStep(Math.max(0, step - 1))}
          disabled={step === 0}
          className="text-gray-400 hover:text-white disabled:text-gray-600 text-sm transition-colors"
        >
          &larr; 이전
        </button>
        <button
          onClick={() => setStep(Math.min(STEPS.length - 1, step + 1))}
          disabled={step === STEPS.length - 1}
          className="text-blue-400 hover:text-blue-300 disabled:text-gray-600 text-sm transition-colors"
        >
          다음 &rarr;
        </button>
      </div>
    </div>
  );
}
