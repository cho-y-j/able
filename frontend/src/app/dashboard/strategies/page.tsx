"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";

interface Strategy {
  id: string;
  name: string;
  stock_code: string;
  stock_name: string | null;
  strategy_type: string;
  composite_score: number | null;
  status: string;
  is_auto_trading: boolean;
  created_at: string;
}

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [searchCode, setSearchCode] = useState("");
  const [searchLoading, setSearchLoading] = useState(false);

  useEffect(() => {
    fetchStrategies();
  }, []);

  const fetchStrategies = async () => {
    try {
      const { data } = await api.get("/strategies");
      setStrategies(data);
    } catch {
      // handle error
    }
  };

  const startSearch = async () => {
    if (!searchCode.trim()) return;
    setSearchLoading(true);
    try {
      await api.post("/strategies/search", {
        stock_code: searchCode.trim(),
        date_range_start: "2024-01-01",
        date_range_end: "2025-12-31",
        optimization_method: "grid",
      });
      alert(`Strategy search started for ${searchCode}`);
    } catch {
      alert("Failed to start strategy search");
    } finally {
      setSearchLoading(false);
    }
  };

  const toggleAutoTrading = async (id: string, isActive: boolean) => {
    try {
      if (isActive) {
        await api.post(`/strategies/${id}/deactivate`);
      } else {
        await api.post(`/strategies/${id}/activate`);
      }
      fetchStrategies();
    } catch {
      alert("Failed to toggle auto-trading");
    }
  };

  const gradeColor = (score: number | null) => {
    if (!score) return "text-gray-500";
    if (score >= 80) return "text-green-400";
    if (score >= 60) return "text-blue-400";
    if (score >= 40) return "text-yellow-400";
    return "text-red-400";
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Trading Strategies</h2>

      {/* Strategy Search */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 mb-6">
        <h3 className="text-lg font-semibold mb-4">AI Strategy Search</h3>
        <p className="text-sm text-gray-500 mb-4">
          Enter a stock code and let AI find the optimal trading strategy using backtesting and validation.
        </p>
        <div className="flex gap-3">
          <input
            type="text"
            value={searchCode}
            onChange={(e) => setSearchCode(e.target.value)}
            placeholder="Stock code (e.g., 005930 for Samsung)"
            className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
          />
          <button onClick={startSearch} disabled={searchLoading}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 rounded-lg text-sm font-medium whitespace-nowrap transition-colors">
            {searchLoading ? "Searching..." : "Search Strategy"}
          </button>
        </div>
      </div>

      {/* Strategy List */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <h3 className="text-lg font-semibold mb-4">My Strategies ({strategies.length})</h3>
        {strategies.length === 0 ? (
          <p className="text-gray-600 text-sm">
            No strategies yet. Use AI Strategy Search above to find optimal strategies.
          </p>
        ) : (
          <div className="space-y-3">
            {strategies.map((s) => (
              <div key={s.id} className="flex items-center justify-between p-4 bg-gray-800 rounded-lg">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h4 className="font-medium">{s.name}</h4>
                    <span className={`text-xs px-2 py-1 rounded ${
                      s.status === "active" ? "bg-green-900/50 text-green-400" :
                      s.status === "validated" ? "bg-blue-900/50 text-blue-400" :
                      "bg-gray-700 text-gray-400"
                    }`}>
                      {s.status}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 mt-1">
                    {s.stock_name || s.stock_code} | {s.strategy_type}
                    {s.composite_score !== null && (
                      <span className={`ml-2 font-medium ${gradeColor(s.composite_score)}`}>
                        Score: {s.composite_score.toFixed(1)}
                      </span>
                    )}
                  </p>
                </div>
                <button onClick={() => toggleAutoTrading(s.id, s.is_auto_trading)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    s.is_auto_trading
                      ? "bg-red-600/20 text-red-400 hover:bg-red-600/30"
                      : "bg-green-600/20 text-green-400 hover:bg-green-600/30"
                  }`}>
                  {s.is_auto_trading ? "Stop" : "Activate"}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
