/**
 * Chart utility functions for lightweight-charts.
 */

export const CHART_COLORS = {
  background: "#111827",
  text: "#9CA3AF",
  grid: "#1F2937",
  border: "#374151",
  up: "#10B981",
  down: "#EF4444",
  upAlpha: "rgba(16, 185, 129, 0.3)",
  downAlpha: "rgba(239, 68, 68, 0.3)",
  blue: "#3B82F6",
  blueAlpha: "rgba(59, 130, 246, 0.15)",
  yellow: "#F59E0B",
  yellowAlpha: "rgba(245, 158, 11, 0.15)",
  purple: "#8B5CF6",
  purpleAlpha: "rgba(139, 92, 246, 0.15)",
} as const;

export const DEFAULT_CHART_OPTIONS = {
  layout: {
    background: { color: CHART_COLORS.background },
    textColor: CHART_COLORS.text,
  },
  grid: {
    vertLines: { color: CHART_COLORS.grid },
    horzLines: { color: CHART_COLORS.grid },
  },
  crosshair: { mode: 0 as const },
  timeScale: { borderColor: CHART_COLORS.border },
  rightPriceScale: { borderColor: CHART_COLORS.border },
};

/** Format a number as Korean Won */
export function formatKRW(value: number): string {
  if (Math.abs(value) >= 1e8) return `₩${(value / 1e8).toFixed(1)}억`;
  if (Math.abs(value) >= 1e4) return `₩${(value / 1e4).toFixed(0)}만`;
  return `₩${value.toLocaleString()}`;
}

/** Format percentage */
export function formatPct(value: number | null | undefined, decimals = 2): string {
  if (value == null) return "-";
  return `${value >= 0 ? "+" : ""}${value.toFixed(decimals)}%`;
}

/** Score color based on value */
export function scoreColor(score: number | null | undefined): string {
  if (score == null) return "text-gray-500";
  if (score >= 80) return "text-green-400";
  if (score >= 60) return "text-blue-400";
  if (score >= 40) return "text-yellow-400";
  return "text-red-400";
}

/** Grade label from score */
export function gradeFromScore(score: number | null | undefined): string {
  if (score == null) return "-";
  if (score >= 80) return "A";
  if (score >= 60) return "B";
  if (score >= 40) return "C";
  if (score >= 20) return "D";
  return "F";
}

/** Metric color (positive = green, negative = red) */
export function metricColor(value: number | null | undefined): string {
  if (value == null) return "text-gray-500";
  return value >= 0 ? "text-green-400" : "text-red-400";
}
