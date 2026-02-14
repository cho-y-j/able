"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import api from "@/lib/api";
import { formatPct, scoreColor, gradeFromScore } from "@/lib/charts";

interface BacktestSummary {
  id: string;
  strategy_id: string;
  strategy_name?: string;
  stock_code?: string;
  status: string;
  date_range_start: string;
  date_range_end: string;
  metrics: {
    total_return: number;
    sharpe_ratio: number;
    max_drawdown: number;
    win_rate: number;
    total_trades: number;
  };
  validation: {
    wfa_score: number;
    mc_score: number;
    oos_score: number;
  };
  composite_score?: number;
}

export default function BacktestsPage() {
  const [backtests, setBacktests] = useState<BacktestSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchBacktests();
  }, []);

  const fetchBacktests = async () => {
    try {
      const { data } = await api.get("/strategies");
      const allBacktests: BacktestSummary[] = [];

      // Fetch latest backtest for each strategy
      for (const strategy of data) {
        if (!strategy.backtests?.length) continue;
        const btId = strategy.backtests[0];
        try {
          const { data: bt } = await api.get(`/backtests/${btId}`);
          allBacktests.push({
            ...bt,
            strategy_name: strategy.name,
            stock_code: strategy.stock_code,
            composite_score: strategy.composite_score,
          });
        } catch {
          // skip
        }
      }

      setBacktests(allBacktests);
    } catch {
      // Fallback: try direct fetch
      setBacktests([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Backtests</h2>
      </div>

      {loading ? (
        <div className="text-center py-20 text-gray-500">Loading backtests...</div>
      ) : backtests.length === 0 ? (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-12 text-center">
          <p className="text-gray-500 mb-4">No backtests found.</p>
          <Link
            href="/dashboard/strategies"
            className="text-blue-400 hover:text-blue-300 text-sm"
          >
            Go to Strategies to run a backtest
          </Link>
        </div>
      ) : (
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400">
                <th className="text-left p-4">Strategy</th>
                <th className="text-left p-4">Stock</th>
                <th className="text-right p-4">Return</th>
                <th className="text-right p-4">Sharpe</th>
                <th className="text-right p-4">Max DD</th>
                <th className="text-right p-4">Win Rate</th>
                <th className="text-right p-4">Trades</th>
                <th className="text-center p-4">Grade</th>
                <th className="text-center p-4">MC</th>
                <th className="text-center p-4">OOS</th>
                <th className="text-right p-4">Period</th>
              </tr>
            </thead>
            <tbody>
              {backtests.map((bt) => (
                <tr
                  key={bt.id}
                  className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors"
                >
                  <td className="p-4">
                    <Link
                      href={`/dashboard/backtests/${bt.id}`}
                      className="text-blue-400 hover:text-blue-300 font-medium"
                    >
                      {bt.strategy_name || bt.strategy_id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="p-4 text-gray-300">{bt.stock_code || "-"}</td>
                  <td className={`p-4 text-right font-mono ${bt.metrics.total_return >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {formatPct(bt.metrics.total_return)}
                  </td>
                  <td className="p-4 text-right font-mono text-gray-300">
                    {bt.metrics.sharpe_ratio?.toFixed(2) ?? "-"}
                  </td>
                  <td className="p-4 text-right font-mono text-red-400">
                    {formatPct(bt.metrics.max_drawdown)}
                  </td>
                  <td className="p-4 text-right font-mono text-gray-300">
                    {bt.metrics.win_rate?.toFixed(1)}%
                  </td>
                  <td className="p-4 text-right text-gray-400">
                    {bt.metrics.total_trades}
                  </td>
                  <td className="p-4 text-center">
                    <span className={`font-bold ${scoreColor(bt.composite_score)}`}>
                      {gradeFromScore(bt.composite_score)}
                    </span>
                  </td>
                  <td className={`p-4 text-center ${scoreColor(bt.validation.mc_score)}`}>
                    {bt.validation.mc_score?.toFixed(0) ?? "-"}
                  </td>
                  <td className={`p-4 text-center ${scoreColor(bt.validation.oos_score)}`}>
                    {bt.validation.oos_score?.toFixed(0) ?? "-"}
                  </td>
                  <td className="p-4 text-right text-gray-500 text-xs">
                    {bt.date_range_start} ~ {bt.date_range_end}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
