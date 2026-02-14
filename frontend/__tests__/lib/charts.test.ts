import {
  CHART_COLORS,
  DEFAULT_CHART_OPTIONS,
  formatKRW,
  formatPct,
  scoreColor,
  gradeFromScore,
  metricColor,
} from "@/lib/charts";

describe("CHART_COLORS", () => {
  it("has all required color keys", () => {
    expect(CHART_COLORS.background).toBe("#111827");
    expect(CHART_COLORS.up).toBe("#10B981");
    expect(CHART_COLORS.down).toBe("#EF4444");
    expect(CHART_COLORS.blue).toBe("#3B82F6");
  });
});

describe("DEFAULT_CHART_OPTIONS", () => {
  it("uses dark theme background", () => {
    expect(DEFAULT_CHART_OPTIONS.layout.background.color).toBe("#111827");
  });

  it("sets crosshair mode to 0", () => {
    expect(DEFAULT_CHART_OPTIONS.crosshair.mode).toBe(0);
  });
});

describe("formatKRW", () => {
  it("formats billions as 억", () => {
    expect(formatKRW(150_000_000)).toBe("₩1.5억");
    expect(formatKRW(1_000_000_000)).toBe("₩10.0억");
  });

  it("formats ten-thousands as 만", () => {
    expect(formatKRW(50_000)).toBe("₩5만");
    expect(formatKRW(120_000)).toBe("₩12만");
  });

  it("formats small numbers with comma separator", () => {
    expect(formatKRW(9999)).toBe("₩9,999");
    expect(formatKRW(0)).toBe("₩0");
  });

  it("handles negative values", () => {
    expect(formatKRW(-200_000_000)).toBe("₩-2.0억");
    expect(formatKRW(-50_000)).toBe("₩-5만");
  });
});

describe("formatPct", () => {
  it("formats positive with + prefix", () => {
    expect(formatPct(5.23)).toBe("+5.23%");
    expect(formatPct(0)).toBe("+0.00%");
  });

  it("formats negative with - prefix", () => {
    expect(formatPct(-3.14)).toBe("-3.14%");
  });

  it("supports custom decimal places", () => {
    expect(formatPct(12.3456, 1)).toBe("+12.3%");
    expect(formatPct(-0.5, 0)).toBe("-1%");
  });

  it("returns dash for null/undefined", () => {
    expect(formatPct(null)).toBe("-");
    expect(formatPct(undefined)).toBe("-");
  });
});

describe("scoreColor", () => {
  it("returns green for high scores (>= 80)", () => {
    expect(scoreColor(80)).toBe("text-green-400");
    expect(scoreColor(100)).toBe("text-green-400");
  });

  it("returns blue for good scores (>= 60)", () => {
    expect(scoreColor(60)).toBe("text-blue-400");
    expect(scoreColor(79)).toBe("text-blue-400");
  });

  it("returns yellow for medium scores (>= 40)", () => {
    expect(scoreColor(40)).toBe("text-yellow-400");
    expect(scoreColor(59)).toBe("text-yellow-400");
  });

  it("returns red for low scores (< 40)", () => {
    expect(scoreColor(0)).toBe("text-red-400");
    expect(scoreColor(39)).toBe("text-red-400");
  });

  it("returns gray for null/undefined", () => {
    expect(scoreColor(null)).toBe("text-gray-500");
    expect(scoreColor(undefined)).toBe("text-gray-500");
  });
});

describe("gradeFromScore", () => {
  it("maps scores to letter grades", () => {
    expect(gradeFromScore(95)).toBe("A");
    expect(gradeFromScore(70)).toBe("B");
    expect(gradeFromScore(50)).toBe("C");
    expect(gradeFromScore(30)).toBe("D");
    expect(gradeFromScore(10)).toBe("F");
  });

  it("returns dash for null/undefined", () => {
    expect(gradeFromScore(null)).toBe("-");
    expect(gradeFromScore(undefined)).toBe("-");
  });
});

describe("metricColor", () => {
  it("returns green for positive values", () => {
    expect(metricColor(1)).toBe("text-green-400");
    expect(metricColor(0)).toBe("text-green-400");
  });

  it("returns red for negative values", () => {
    expect(metricColor(-1)).toBe("text-red-400");
  });

  it("returns gray for null/undefined", () => {
    expect(metricColor(null)).toBe("text-gray-500");
    expect(metricColor(undefined)).toBe("text-gray-500");
  });
});
