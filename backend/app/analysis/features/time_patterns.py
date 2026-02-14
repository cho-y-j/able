"""Time-based pattern analysis: day-of-week, monthly, consecutive-day patterns."""

import pandas as pd
import numpy as np


def analyze_time_patterns(df: pd.DataFrame) -> dict:
    """Analyze time-based return patterns from OHLCV data.

    Args:
        df: DataFrame with DatetimeIndex and 'close' column.

    Returns:
        Dictionary with day-of-week, monthly, and streak patterns.
    """
    if df.empty or len(df) < 30:
        return {}

    close = df["close"]
    returns = close.pct_change().dropna()
    up = returns > 0

    result: dict = {}

    # ── Day of Week patterns ──────────────────────────────────
    dow_groups = returns.groupby(returns.index.dayofweek)
    dow_names = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금"}
    day_of_week = {}
    for day_num, grp in dow_groups:
        if len(grp) < 5:
            continue
        day_of_week[dow_names.get(day_num, str(day_num))] = {
            "win_rate": round(float((grp > 0).mean()) * 100, 1),
            "avg_return": round(float(grp.mean()) * 100, 3),
            "sample_count": int(len(grp)),
            "avg_up_return": round(float(grp[grp > 0].mean()) * 100, 3) if (grp > 0).any() else 0,
            "avg_down_return": round(float(grp[grp < 0].mean()) * 100, 3) if (grp < 0).any() else 0,
        }
    result["day_of_week"] = day_of_week

    # ── Monthly patterns ──────────────────────────────────────
    month_groups = returns.groupby(returns.index.month)
    month_names = {1: "1월", 2: "2월", 3: "3월", 4: "4월", 5: "5월", 6: "6월",
                   7: "7월", 8: "8월", 9: "9월", 10: "10월", 11: "11월", 12: "12월"}
    monthly = {}
    for month_num, grp in month_groups:
        if len(grp) < 5:
            continue
        monthly[month_names.get(month_num, str(month_num))] = {
            "win_rate": round(float((grp > 0).mean()) * 100, 1),
            "avg_return": round(float(grp.mean()) * 100, 3),
            "sample_count": int(len(grp)),
        }
    result["monthly"] = monthly

    # ── Week of month patterns (월초/월중/월말) ───────────────
    days_in_period = returns.copy()
    day_of_month = days_in_period.index.day
    week_of_month = {}
    for label, mask in [("월초(1-10일)", day_of_month <= 10),
                        ("월중(11-20일)", (day_of_month > 10) & (day_of_month <= 20)),
                        ("월말(21-31일)", day_of_month > 20)]:
        grp = days_in_period[mask]
        if len(grp) >= 5:
            week_of_month[label] = {
                "win_rate": round(float((grp > 0).mean()) * 100, 1),
                "avg_return": round(float(grp.mean()) * 100, 3),
                "sample_count": int(len(grp)),
            }
    result["week_of_month"] = week_of_month

    # ── Consecutive streak patterns ───────────────────────────
    streaks = _compute_streaks(up)
    streak_patterns = {}
    for streak_len in [2, 3, 4, 5]:
        # After N consecutive up days
        up_streak_ends = [i for i, s in streaks if s == streak_len and i + 1 < len(returns)]
        if len(up_streak_ends) >= 3:
            next_day_returns = returns.iloc[[i + 1 for i in up_streak_ends if i + 1 < len(returns)]]
            streak_patterns[f"{streak_len}일_연속_상승_후"] = {
                "reversal_rate": round(float((next_day_returns < 0).mean()) * 100, 1),
                "continuation_rate": round(float((next_day_returns > 0).mean()) * 100, 1),
                "avg_next_return": round(float(next_day_returns.mean()) * 100, 3),
                "sample_count": int(len(next_day_returns)),
            }
        # After N consecutive down days
        down_streak_ends = [i for i, s in streaks if s == -streak_len and i + 1 < len(returns)]
        if len(down_streak_ends) >= 3:
            next_day_returns = returns.iloc[[i + 1 for i in down_streak_ends if i + 1 < len(returns)]]
            streak_patterns[f"{streak_len}일_연속_하락_후"] = {
                "reversal_rate": round(float((next_day_returns > 0).mean()) * 100, 1),
                "continuation_rate": round(float((next_day_returns < 0).mean()) * 100, 1),
                "avg_next_return": round(float(next_day_returns.mean()) * 100, 3),
                "sample_count": int(len(next_day_returns)),
            }
    result["streaks"] = streak_patterns

    # ── Summary: best/worst ───────────────────────────────────
    if day_of_week:
        best_day = max(day_of_week.items(), key=lambda x: x[1]["win_rate"])
        worst_day = min(day_of_week.items(), key=lambda x: x[1]["win_rate"])
        result["summary"] = {
            "best_day": f"{best_day[0]} (승률 {best_day[1]['win_rate']}%)",
            "worst_day": f"{worst_day[0]} (승률 {worst_day[1]['win_rate']}%)",
            "total_days": int(len(returns)),
            "overall_win_rate": round(float(up.mean()) * 100, 1),
        }

    return result


def _compute_streaks(up_series: pd.Series) -> list[tuple[int, int]]:
    """Compute consecutive up/down streaks.

    Returns list of (end_index, streak_length) where positive = up streak, negative = down.
    """
    streaks = []
    if len(up_series) == 0:
        return streaks

    current_len = 1
    current_dir = 1 if up_series.iloc[0] else -1

    for i in range(1, len(up_series)):
        direction = 1 if up_series.iloc[i] else -1
        if direction == current_dir:
            current_len += 1
        else:
            streaks.append((i - 1, current_dir * current_len))
            current_len = 1
            current_dir = direction

    streaks.append((len(up_series) - 1, current_dir * current_len))
    return streaks
