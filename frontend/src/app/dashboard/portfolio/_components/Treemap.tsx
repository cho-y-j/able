"use client";

import { useMemo } from "react";
import { formatPct } from "@/lib/charts";

export interface TreemapItem {
  code: string;
  name: string | null;
  value: number;
  weight: number;
  pnl_pct: number;
}

interface TreemapProps {
  items: TreemapItem[];
}

interface LayoutRect {
  item: TreemapItem;
  x: number;
  y: number;
  w: number;
  h: number;
}

function pnlColor(pct: number): string {
  if (pct >= 5) return "bg-green-600";
  if (pct >= 2) return "bg-green-700";
  if (pct > 0) return "bg-green-800";
  if (pct === 0) return "bg-gray-700";
  if (pct > -2) return "bg-red-800";
  if (pct > -5) return "bg-red-700";
  return "bg-red-600";
}

function pnlTextColor(pct: number): string {
  if (pct > 0) return "text-green-200";
  if (pct < 0) return "text-red-200";
  return "text-gray-300";
}

// Squarified treemap layout algorithm
function squarify(
  items: TreemapItem[],
  containerW: number,
  containerH: number,
): LayoutRect[] {
  if (items.length === 0) return [];

  const totalValue = items.reduce((s, i) => s + i.value, 0);
  if (totalValue <= 0) return [];

  // Normalize values to fill the container area
  const totalArea = containerW * containerH;
  const normalized = items
    .filter((i) => i.value > 0)
    .sort((a, b) => b.value - a.value)
    .map((item) => ({
      item,
      area: (item.value / totalValue) * totalArea,
    }));

  const rects: LayoutRect[] = [];
  let x = 0;
  let y = 0;
  let w = containerW;
  let h = containerH;

  let i = 0;
  while (i < normalized.length) {
    // Determine the shorter side
    const shorter = Math.min(w, h);
    const isVertical = h <= w;

    // Greedily add items to current row until aspect ratio worsens
    const row: { item: TreemapItem; area: number }[] = [];
    let rowArea = 0;

    const worstRatio = (areas: number[], side: number): number => {
      const sum = areas.reduce((a, b) => a + b, 0);
      let worst = 0;
      for (const a of areas) {
        const rowH = sum / side;
        const rowW = a / rowH;
        const ratio = Math.max(rowW / rowH, rowH / rowW);
        worst = Math.max(worst, ratio);
      }
      return worst;
    };

    while (i < normalized.length) {
      const next = normalized[i];
      const testAreas = [...row.map((r) => r.area), next.area];
      const currentAreas = row.map((r) => r.area);

      if (
        row.length > 0 &&
        worstRatio(testAreas, shorter) > worstRatio(currentAreas, shorter)
      ) {
        break;
      }

      row.push(next);
      rowArea += next.area;
      i++;
    }

    // Layout the row
    const rowSpan = rowArea / shorter;

    let offset = 0;
    for (const { item, area } of row) {
      const cellSpan = area / rowSpan;

      if (isVertical) {
        rects.push({ item, x: x + offset, y, w: rowSpan, h: cellSpan });
        offset += cellSpan;
      } else {
        rects.push({ item, x, y: y + offset, w: cellSpan, h: rowSpan });
        offset += cellSpan;
      }
    }

    // Reduce remaining space
    if (isVertical) {
      x += rowSpan;
      w -= rowSpan;
    } else {
      y += rowSpan;
      h -= rowSpan;
    }
  }

  return rects;
}

export default function Treemap({ items }: TreemapProps) {
  const validItems = items.filter((i) => i.value > 0);

  const rects = useMemo(
    () => squarify(validItems, 100, 100),
    [validItems],
  );

  if (rects.length === 0) return null;

  return (
    <div
      className="relative w-full overflow-hidden rounded-lg"
      style={{ paddingBottom: "60%" }}
    >
      <div className="absolute inset-0">
        {rects.map((r) => {
          const isSmall = r.w < 15 || r.h < 15;
          const isTiny = r.w < 10 || r.h < 10;

          return (
            <div
              key={r.item.code}
              className={`absolute border border-gray-900/50 ${pnlColor(r.item.pnl_pct)} flex flex-col items-center justify-center overflow-hidden transition-opacity hover:opacity-80 cursor-default group`}
              style={{
                left: `${r.x}%`,
                top: `${r.y}%`,
                width: `${r.w}%`,
                height: `${r.h}%`,
              }}
              title={`${r.item.code}${r.item.name ? ` ${r.item.name}` : ""}\n${formatPct(r.item.pnl_pct)}\n${r.item.weight.toFixed(1)}%`}
            >
              {!isTiny && (
                <>
                  <span className="text-white font-bold text-xs leading-tight truncate max-w-full px-1">
                    {r.item.code}
                  </span>
                  {!isSmall && r.item.name && (
                    <span className="text-white/70 text-[10px] leading-tight truncate max-w-full px-1">
                      {r.item.name}
                    </span>
                  )}
                  <span
                    className={`text-xs font-semibold leading-tight ${pnlTextColor(r.item.pnl_pct)}`}
                  >
                    {formatPct(r.item.pnl_pct)}
                  </span>
                  {!isSmall && (
                    <span className="text-white/50 text-[10px] leading-tight">
                      {r.item.weight.toFixed(1)}%
                    </span>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
