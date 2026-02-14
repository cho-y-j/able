"use client";

import { useState, useEffect } from "react";
import api from "@/lib/api";
import { useI18n } from "@/i18n";

interface AgentStatus {
  session_id: string;
  status: string;
  session_type: string;
  current_agent: string | null;
  market_regime: string | null;
  iteration_count: number;
  started_at: string;
  recent_actions: Array<{ agent: string; action: string; timestamp: string }>;
}

const AGENTS = [
  { name: "Market Analyst", key: "market_analyst", desc: "Analyzes market regime and conditions", color: "blue" },
  { name: "Strategy Search", key: "strategy_search", desc: "Finds optimal trading strategies", color: "green" },
  { name: "Risk Manager", key: "risk_manager", desc: "Evaluates risk and approves trades", color: "yellow" },
  { name: "Execution", key: "execution", desc: "Executes orders via KIS API", color: "orange" },
  { name: "Monitor", key: "monitor", desc: "Monitors positions in real-time", color: "purple" },
];

export default function AgentsPage() {
  const { t } = useI18n();
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [polling, setPolling] = useState(false);

  const fetchStatus = async () => {
    try {
      const { data } = await api.get("/agents/status");
      setStatus(data);
    } catch {
      setStatus(null);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  useEffect(() => {
    if (!polling) return;
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, [polling]);

  const startSession = async () => {
    setLoading(true);
    try {
      const { data } = await api.post("/agents/start", { session_type: "full_cycle" });
      setStatus(data);
      setPolling(true);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      alert(error.response?.data?.detail || "Failed to start agent session");
    } finally {
      setLoading(false);
    }
  };

  const stopSession = async () => {
    if (!status) return;
    try {
      await api.post("/agents/stop", { session_id: status.session_id });
      setPolling(false);
      fetchStatus();
    } catch {
      // handle error
    }
  };

  const isActive = status?.status === "active";

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">{t.agents.title}</h2>
          <p className="text-gray-500 text-sm mt-1">
            Team Leader coordinates 5 specialized agents for automated trading
          </p>
        </div>
        {isActive ? (
          <button onClick={stopSession}
            className="px-6 py-2 bg-red-600 hover:bg-red-700 rounded-lg font-medium transition-colors">
            {t.agents.stopAgent}
          </button>
        ) : (
          <button onClick={startSession} disabled={loading}
            className="px-6 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-700 rounded-lg font-medium transition-colors">
            {loading ? t.common.loading : t.agents.startAgent}
          </button>
        )}
      </div>

      {/* Status Banner */}
      {status && (
        <div className={`p-4 rounded-xl border mb-6 ${
          isActive ? "bg-green-900/20 border-green-700" : "bg-gray-900 border-gray-800"
        }`}>
          <div className="flex items-center gap-4">
            <div className={`w-3 h-3 rounded-full ${isActive ? "bg-green-400 animate-pulse" : "bg-gray-600"}`} />
            <div>
              <p className="font-medium">{isActive ? "Session Active" : `Session ${status.status}`}</p>
              <p className="text-sm text-gray-500">
                Type: {status.session_type} | Iterations: {status.iteration_count}
                {status.market_regime && ` | Regime: ${status.market_regime}`}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Agent Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {AGENTS.map((agent) => {
          const isCurrent = status?.current_agent === agent.key;
          return (
            <div key={agent.key}
              className={`p-5 rounded-xl border transition-all ${
                isCurrent
                  ? "bg-blue-900/20 border-blue-500"
                  : "bg-gray-900 border-gray-800"
              }`}>
              <div className="flex items-center gap-2 mb-2">
                <div className={`w-2 h-2 rounded-full ${
                  isCurrent ? "bg-blue-400 animate-pulse" : isActive ? "bg-green-400" : "bg-gray-600"
                }`} />
                <h3 className="font-semibold">{agent.name}</h3>
              </div>
              <p className="text-sm text-gray-500">{agent.desc}</p>
              {isCurrent && (
                <p className="text-xs text-blue-400 mt-2 animate-pulse">Currently active...</p>
              )}
            </div>
          );
        })}
      </div>

      {/* Activity Log */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <h3 className="text-lg font-semibold mb-4">{t.agents.activityLog}</h3>
        {(status?.recent_actions?.length || 0) > 0 ? (
          <div className="space-y-2 font-mono text-sm">
            {status?.recent_actions.map((action, i) => (
              <div key={i} className="flex items-center gap-3 text-gray-400">
                <span className="text-gray-600 text-xs">{new Date(action.timestamp).toLocaleTimeString()}</span>
                <span className="text-blue-400">[{action.agent}]</span>
                <span>{action.action}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-600 text-sm">{t.agents.noActivity}</p>
        )}
      </div>
    </div>
  );
}
