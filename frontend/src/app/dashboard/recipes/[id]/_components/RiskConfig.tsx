"use client";

import { useState } from "react";
import api from "@/lib/api";

interface RiskConfigProps {
  recipeId: string | null;
  riskConfig: Record<string, number>;
  stockCodes: string[];
  onRiskChange: (config: Record<string, number>) => void;
}

interface BacktestResult {
  composite_score: number | null;
  grade: string | null;
  metrics: {
    total_return: number;
    annual_return: number;
    sharpe_ratio: number;
    max_drawdown: number;
    win_rate: number;
    total_trades: number;
  };
}

export default function RiskConfig({
  recipeId,
  riskConfig,
  stockCodes,
  onRiskChange,
}: RiskConfigProps) {
  const [backtesting, setBacktesting] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const updateRisk = (key: string, value: number) => {
    onRiskChange({ ...riskConfig, [key]: value });
  };

  const runBacktest = async () => {
    if (!recipeId || stockCodes.length === 0) {
      setError("레시피를 먼저 저장하고 종목을 추가하세요");
      return;
    }

    setBacktesting(true);
    setError(null);
    setResult(null);

    try {
      const { data } = await api.post(`/recipes/${recipeId}/backtest`, {
        stock_code: stockCodes[0],
      });
      setResult(data);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "백테스트 실패";
      setError(msg);
    } finally {
      setBacktesting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-white mb-1">리스크 설정 + 백테스트</h3>
        <p className="text-gray-400 text-sm">리스크 관리 파라미터를 설정하고 백테스트로 검증하세요</p>
      </div>

      {/* Risk Parameters */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <label className="text-xs text-gray-400 block mb-2">손절 (%)</label>
          <input
            type="number"
            min={0.5}
            max={20}
            step={0.5}
            value={riskConfig.stop_loss ?? 3}
            onChange={(e) => updateRisk("stop_loss", Number(e.target.value))}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-red-400 text-lg font-mono"
          />
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <label className="text-xs text-gray-400 block mb-2">익절 (%)</label>
          <input
            type="number"
            min={0.5}
            max={50}
            step={0.5}
            value={riskConfig.take_profit ?? 5}
            onChange={(e) => updateRisk("take_profit", Number(e.target.value))}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-green-400 text-lg font-mono"
          />
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <label className="text-xs text-gray-400 block mb-2">포지션 크기 (% of 자산)</label>
          <input
            type="number"
            min={1}
            max={100}
            step={1}
            value={riskConfig.position_size ?? 10}
            onChange={(e) => updateRisk("position_size", Number(e.target.value))}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-blue-400 text-lg font-mono"
          />
        </div>
      </div>

      {/* Backtest Button */}
      <button
        onClick={runBacktest}
        disabled={backtesting || !recipeId}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white py-3 rounded-xl text-sm font-medium transition-colors"
      >
        {backtesting ? "백테스트 실행 중..." : "백테스트 실행"}
      </button>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <div className="flex items-center justify-between mb-4">
            <h4 className="text-white font-semibold">백테스트 결과</h4>
            <div className="flex items-center gap-3">
              {result.composite_score != null && (
                <span className="text-2xl font-bold text-blue-400">
                  {result.composite_score.toFixed(1)}점
                </span>
              )}
              {result.grade && (
                <span className={`text-xl font-bold px-3 py-1 rounded-lg ${
                  result.grade.startsWith("A") ? "bg-green-500/20 text-green-400" :
                  result.grade.startsWith("B") ? "bg-blue-500/20 text-blue-400" :
                  result.grade.startsWith("C") ? "bg-yellow-500/20 text-yellow-400" :
                  "bg-red-500/20 text-red-400"
                }`}>
                  {result.grade}
                </span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <div className="bg-gray-900 rounded-lg p-3">
              <p className="text-xs text-gray-500">수익률</p>
              <p className={`text-lg font-bold ${result.metrics.total_return >= 0 ? "text-green-400" : "text-red-400"}`}>
                {result.metrics.total_return >= 0 ? "+" : ""}{result.metrics.total_return.toFixed(1)}%
              </p>
            </div>
            <div className="bg-gray-900 rounded-lg p-3">
              <p className="text-xs text-gray-500">샤프 비율</p>
              <p className="text-lg font-bold text-white">{result.metrics.sharpe_ratio.toFixed(2)}</p>
            </div>
            <div className="bg-gray-900 rounded-lg p-3">
              <p className="text-xs text-gray-500">MDD</p>
              <p className="text-lg font-bold text-red-400">{result.metrics.max_drawdown.toFixed(1)}%</p>
            </div>
            <div className="bg-gray-900 rounded-lg p-3">
              <p className="text-xs text-gray-500">승률</p>
              <p className="text-lg font-bold text-white">{result.metrics.win_rate.toFixed(1)}%</p>
            </div>
            <div className="bg-gray-900 rounded-lg p-3">
              <p className="text-xs text-gray-500">총 거래</p>
              <p className="text-lg font-bold text-white">{result.metrics.total_trades}회</p>
            </div>
            <div className="bg-gray-900 rounded-lg p-3">
              <p className="text-xs text-gray-500">연수익률</p>
              <p className={`text-lg font-bold ${result.metrics.annual_return >= 0 ? "text-green-400" : "text-red-400"}`}>
                {result.metrics.annual_return >= 0 ? "+" : ""}{result.metrics.annual_return.toFixed(1)}%
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
