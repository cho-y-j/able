"use client";

interface ScoreGaugeProps {
  value: number | null;
  max?: number;
  label: string;
  size?: number;
}

function getGrade(value: number, max: number): string {
  const pct = (value / max) * 100;
  if (pct >= 90) return "A+";
  if (pct >= 80) return "A";
  if (pct >= 70) return "B+";
  if (pct >= 60) return "B";
  if (pct >= 50) return "C+";
  if (pct >= 40) return "C";
  return "D";
}

function getColor(value: number, max: number): string {
  const pct = (value / max) * 100;
  if (pct >= 80) return "#4ade80"; // green-400
  if (pct >= 60) return "#60a5fa"; // blue-400
  if (pct >= 40) return "#facc15"; // yellow-400
  return "#f87171"; // red-400
}

export default function ScoreGauge({
  value,
  max = 100,
  label,
  size = 80,
}: ScoreGaugeProps) {
  const strokeWidth = size * 0.08;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const center = size / 2;

  const hasValue = value !== null && value !== undefined;
  const pct = hasValue ? Math.max(0, Math.min(1, value / max)) : 0;
  const offset = circumference - pct * circumference;
  const color = hasValue ? getColor(value, max) : "#6b7280";
  const grade = hasValue ? getGrade(value, max) : "";

  // Font sizes proportional to gauge size
  const gradeFontSize = size * 0.13;
  const valueFontSize = size * 0.22;
  const labelFontSize = size * 0.12;

  return (
    <div className="flex flex-col items-center">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="transform -rotate-90"
      >
        {/* Background circle */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="#374151"
          strokeWidth={strokeWidth}
        />
        {/* Foreground arc */}
        {hasValue && (
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className="transition-all duration-700 ease-out"
          />
        )}
      </svg>
      {/* Center text overlay */}
      <div
        className="flex flex-col items-center justify-center"
        style={{
          marginTop: -size,
          width: size,
          height: size,
        }}
      >
        {hasValue ? (
          <>
            <span
              className="font-bold"
              style={{ fontSize: gradeFontSize, color }}
            >
              {grade}
            </span>
            <span
              className="font-bold text-white leading-none"
              style={{ fontSize: valueFontSize }}
            >
              {value.toFixed(0)}
            </span>
            <span
              className="text-gray-400 leading-tight"
              style={{ fontSize: labelFontSize }}
            >
              {label}
            </span>
          </>
        ) : (
          <>
            <span
              className="font-bold text-gray-500"
              style={{ fontSize: valueFontSize }}
            >
              N/A
            </span>
            <span
              className="text-gray-500 leading-tight"
              style={{ fontSize: labelFontSize }}
            >
              {label}
            </span>
          </>
        )}
      </div>
    </div>
  );
}
