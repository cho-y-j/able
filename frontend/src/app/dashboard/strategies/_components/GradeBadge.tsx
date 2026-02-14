"use client";

export function gradeInfo(score: number | null): {
  grade: string;
  bg: string;
  label: string;
  textColor: string;
} {
  if (score === null || score === undefined)
    return { grade: "-", bg: "bg-gray-600", label: "미평가", textColor: "text-gray-300" };
  if (score >= 90)
    return { grade: "A+", bg: "bg-green-600", label: "최우수 - 실전 투입 강력 추천", textColor: "text-green-400" };
  if (score >= 80)
    return { grade: "A", bg: "bg-green-500", label: "우수 - 실전 투입 추천", textColor: "text-green-400" };
  if (score >= 70)
    return { grade: "B+", bg: "bg-blue-500", label: "양호 - 조건부 추천", textColor: "text-blue-400" };
  if (score >= 60)
    return { grade: "B", bg: "bg-blue-400", label: "보통 - 추가 검토 필요", textColor: "text-blue-400" };
  if (score >= 50)
    return { grade: "C+", bg: "bg-yellow-500", label: "미흡 - 개선 필요", textColor: "text-yellow-400" };
  if (score >= 40)
    return { grade: "C", bg: "bg-yellow-600", label: "부족 - 사용 비추천", textColor: "text-yellow-400" };
  return { grade: "D", bg: "bg-red-500", label: "위험 - 사용 금지", textColor: "text-red-400" };
}

interface GradeBadgeProps {
  score: number | null;
  size?: "sm" | "md" | "lg";
}

export function GradeBadge({ score, size = "sm" }: GradeBadgeProps) {
  const { grade, bg } = gradeInfo(score);

  if (size === "lg") {
    return (
      <div
        className={`${bg} text-white w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold shrink-0`}
      >
        {grade}
      </div>
    );
  }

  if (size === "md") {
    return (
      <span className={`${bg} text-white text-sm font-bold px-3 py-1 rounded-full`}>
        {grade}
      </span>
    );
  }

  // sm (default)
  return (
    <span className={`${bg} text-white text-xs font-bold px-2 py-0.5 rounded-full`}>
      {grade}
    </span>
  );
}
