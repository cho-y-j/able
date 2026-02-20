"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
import { useI18n } from "@/i18n";

interface Pattern {
  id: string;
  name: string;
  description: string | null;
  pattern_type: string;
  feature_importance: Record<string, number>;
  model_metrics: Record<string, number>;
  rule_description: string | null;
  rule_config: Record<string, unknown>;
  status: string;
  sample_count: number;
  event_count: number;
}

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-500/20 text-gray-400 border-gray-500/30",
  validated: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  active: "bg-green-500/20 text-green-400 border-green-500/30",
  deprecated: "bg-red-500/20 text-red-400 border-red-500/30",
};

const STATUS_LABELS: Record<string, string> = {
  draft: "초안",
  validated: "검증됨",
  active: "활성",
  deprecated: "비활성",
};

function GradeLabel({ f1 }: { f1: number }) {
  let grade = "D";
  let color = "text-gray-500";
  if (f1 >= 0.7) {
    grade = "A";
    color = "text-green-400";
  } else if (f1 >= 0.5) {
    grade = "B";
    color = "text-yellow-400";
  } else if (f1 >= 0.3) {
    grade = "C";
    color = "text-orange-400";
  }
  return <span className={`text-lg font-bold ${color}`}>{grade}</span>;
}

export default function PatternsPage() {
  const { t } = useI18n();
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [discovering, setDiscovering] = useState(false);

  const fetchPatterns = useCallback(async () => {
    setLoading(true);
    try {
      const params = statusFilter !== "all" ? `?status=${statusFilter}` : "";
      const resp = await api.get(`/patterns${params}`);
      setPatterns(resp.data);
    } catch {
      setPatterns([]);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchPatterns();
  }, [fetchPatterns]);

  const handleDiscover = async () => {
    setDiscovering(true);
    try {
      await api.post("/patterns/discover", {
        pattern_type: "rise_5pct_5day",
        threshold_pct: 5.0,
        window_days: 5,
      });
      // Refresh list after a short delay
      setTimeout(fetchPatterns, 1000);
    } catch {
      // ignore
    } finally {
      setDiscovering(false);
    }
  };

  const handleActivate = async (id: string) => {
    try {
      await api.post(`/patterns/${id}/activate`);
      fetchPatterns();
    } catch {
      // ignore
    }
  };

  const selected = patterns.find((p) => p.id === selectedId);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t.patterns?.title || "Pattern Discovery"}</h1>
          <p className="text-sm text-gray-400 mt-1">
            {t.patterns?.description || "ML-discovered multi-factor trading patterns"}
          </p>
        </div>
        <button
          onClick={handleDiscover}
          disabled={discovering}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 rounded-lg text-sm font-medium transition-colors"
        >
          {discovering ? "Discovering..." : t.patterns?.discover || "Discover New"}
        </button>
      </div>

      {/* Status filter */}
      <div className="flex gap-2">
        {["all", "draft", "validated", "active", "deprecated"].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              statusFilter === s
                ? "bg-indigo-600 border-indigo-500 text-white"
                : "bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600"
            }`}
          >
            {s === "all" ? "All" : STATUS_LABELS[s] || s}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading...</div>
      ) : patterns.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <div className="text-4xl mb-4">P</div>
          <p>No patterns discovered yet. Click &quot;Discover New&quot; to start.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Pattern list */}
          <div className="lg:col-span-1 space-y-2">
            {patterns.map((p) => (
              <div
                key={p.id}
                onClick={() => setSelectedId(p.id)}
                className={`p-4 rounded-xl border cursor-pointer transition-colors ${
                  selectedId === p.id
                    ? "bg-gray-800 border-indigo-500"
                    : "bg-gray-900 border-gray-800 hover:border-gray-700"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold truncate">{p.name}</h3>
                  <span className={`px-2 py-0.5 text-[10px] rounded border ${STATUS_COLORS[p.status] || ""}`}>
                    {STATUS_LABELS[p.status] || p.status}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-gray-500">
                  <span>{p.pattern_type}</span>
                  <span>{p.sample_count} samples</span>
                  <GradeLabel f1={p.model_metrics?.f1 || 0} />
                </div>
              </div>
            ))}
          </div>

          {/* Pattern detail */}
          <div className="lg:col-span-2">
            {selected ? (
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 space-y-5">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-bold">{selected.name}</h2>
                  {selected.status === "validated" && (
                    <button
                      onClick={() => handleActivate(selected.id)}
                      className="px-4 py-1.5 bg-green-600 hover:bg-green-500 rounded-lg text-sm"
                    >
                      Activate
                    </button>
                  )}
                </div>

                {selected.description && (
                  <p className="text-sm text-gray-400">{selected.description}</p>
                )}

                {/* Metrics */}
                <div>
                  <h3 className="text-xs text-gray-500 uppercase mb-2">Model Metrics</h3>
                  <div className="grid grid-cols-4 gap-3">
                    {Object.entries(selected.model_metrics || {}).map(([k, v]) => (
                      <div key={k} className="bg-gray-800/50 rounded-lg p-3 text-center">
                        <div className="text-lg font-mono font-bold">{(v as number).toFixed(2)}</div>
                        <div className="text-[10px] text-gray-500 uppercase">{k}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Feature Importance */}
                <div>
                  <h3 className="text-xs text-gray-500 uppercase mb-2">Feature Importance</h3>
                  <div className="space-y-2">
                    {Object.entries(selected.feature_importance || {})
                      .sort(([, a], [, b]) => (b as number) - (a as number))
                      .map(([k, v]) => (
                        <div key={k} className="flex items-center gap-3">
                          <span className="text-sm font-mono w-40 truncate">{k}</span>
                          <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-indigo-500 rounded-full"
                              style={{ width: `${Math.min((v as number) * 100 * 3, 100)}%` }}
                            />
                          </div>
                          <span className="text-xs text-gray-400 w-12 text-right">
                            {((v as number) * 100).toFixed(1)}%
                          </span>
                        </div>
                      ))}
                  </div>
                </div>

                {/* Rule description */}
                {selected.rule_description && (
                  <div>
                    <h3 className="text-xs text-gray-500 uppercase mb-2">Rule Description</h3>
                    <p className="text-sm text-gray-300 bg-gray-800/50 rounded-lg p-3">
                      {selected.rule_description}
                    </p>
                  </div>
                )}

                {/* Stats */}
                <div className="flex gap-6 text-sm text-gray-500 border-t border-gray-800 pt-4">
                  <span>Samples: {selected.sample_count}</span>
                  <span>Events: {selected.event_count}</span>
                  <span>Event rate: {selected.sample_count > 0 ? ((selected.event_count / selected.sample_count) * 100).toFixed(1) : 0}%</span>
                </div>
              </div>
            ) : (
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-12 text-center text-gray-500">
                Select a pattern to view details
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
