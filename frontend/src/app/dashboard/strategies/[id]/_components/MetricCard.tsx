"use client";

import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: number | null;
  suffix?: string;
  color?: string;
  trend?: "up" | "down" | "neutral";
  tooltip?: string;
  size?: "sm" | "md";
}

function formatValue(value: number, suffix?: string): string {
  const isTradeCount = suffix?.includes("trades");
  const prefix = value > 0 && !isTradeCount ? "+" : "";
  let decimals = 1;
  if (suffix === "%") decimals = 2;
  else if (suffix === "x") decimals = 2;
  return `${prefix}${value.toFixed(decimals)}${suffix || ""}`;
}

export default function MetricCard({
  label,
  value,
  suffix,
  color,
  trend,
  tooltip,
  size = "md",
}: MetricCardProps) {
  const hasValue = value !== null && value !== undefined;

  // Determine text color
  const textColor =
    color ||
    (hasValue && value > 0
      ? "text-green-400"
      : hasValue && value < 0
        ? "text-red-400"
        : "text-white");

  // Subtle background tint based on value sign
  const bgTint = hasValue
    ? value > 0
      ? "bg-green-500/5"
      : value < 0
        ? "bg-red-500/5"
        : ""
    : "";

  const isSm = size === "sm";

  return (
    <div
      className={`group relative bg-gray-800 rounded-lg ${bgTint} ${isSm ? "p-3" : "p-4"}`}
    >
      {/* Label row */}
      <div className="flex items-center gap-1 mb-1">
        <span
          className={`text-gray-500 ${isSm ? "text-[10px]" : "text-xs"}`}
        >
          {label}
        </span>
        {tooltip && (
          <span className="relative cursor-help">
            <span className="text-gray-600 text-[10px]">&#9432;</span>
            <span className="hidden group-hover:block absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-gray-700 text-gray-200 text-xs rounded-lg shadow-xl whitespace-nowrap z-50 pointer-events-none">
              {tooltip}
            </span>
          </span>
        )}
      </div>

      {/* Value row */}
      <div className="flex items-center gap-1.5">
        <span
          className={`font-bold ${textColor} ${isSm ? "text-sm" : "text-lg"}`}
        >
          {hasValue ? formatValue(value, suffix) : "N/A"}
        </span>
        {trend && hasValue && (
          <span className="flex-shrink-0">
            {trend === "up" && (
              <TrendingUp className="w-3.5 h-3.5 text-green-400" />
            )}
            {trend === "down" && (
              <TrendingDown className="w-3.5 h-3.5 text-red-400" />
            )}
            {trend === "neutral" && (
              <Minus className="w-3.5 h-3.5 text-gray-500" />
            )}
          </span>
        )}
      </div>
    </div>
  );
}
