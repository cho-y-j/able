"""Fact Sheet generator — compress all statistical features into a concise summary for LLM."""

import logging
from datetime import datetime

import pandas as pd

from app.analysis.features.time_patterns import analyze_time_patterns
from app.analysis.features.indicator_combos import analyze_indicator_accuracy, find_best_combos

logger = logging.getLogger(__name__)


def generate_fact_sheet(
    df: pd.DataFrame,
    stock_code: str,
    stock_name: str | None = None,
    macro_data: dict | None = None,
    current_signals: dict | None = None,
) -> str:
    """Generate a compressed fact sheet string for LLM consumption.

    This is the bridge between Layer 1 (statistics) and Layer 3 (AI).
    Target: ~400-600 tokens of pure factual content.

    Args:
        df: OHLCV DataFrame for the stock.
        stock_code: Stock code (e.g., "005930").
        stock_name: Stock name (e.g., "삼성전자").
        macro_data: Pre-computed macro correlation data.
        current_signals: Currently active buy/sell signals.

    Returns:
        Formatted string ready for LLM prompt.
    """
    lines = []
    label = f"{stock_name} ({stock_code})" if stock_name else stock_code
    now = datetime.now()
    dow_kr = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"}
    today_dow = dow_kr.get(now.weekday(), "")

    lines.append(f"[{label} 매매 판단 팩트시트]")
    lines.append(f"분석일: {now.strftime('%Y-%m-%d')} ({today_dow}요일)")
    lines.append("")

    # ── Current Price Info ─────────────────────────────────────
    if not df.empty:
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        chg = ((last["close"] - prev["close"]) / prev["close"]) * 100
        lines.append("■ 현재 상태")
        lines.append(f"  종가: {last['close']:,.0f}원 (전일대비 {chg:+.2f}%)")
        lines.append(f"  거래량: {last['volume']:,.0f}")

        # Recent trend
        if len(df) >= 5:
            ret_5d = ((df["close"].iloc[-1] / df["close"].iloc[-5]) - 1) * 100
            lines.append(f"  5일 수익률: {ret_5d:+.2f}%")
        if len(df) >= 20:
            ret_20d = ((df["close"].iloc[-1] / df["close"].iloc[-20]) - 1) * 100
            lines.append(f"  20일 수익률: {ret_20d:+.2f}%")

        # Consecutive streak
        streak = _current_streak(df["close"])
        if abs(streak) >= 2:
            direction = "상승" if streak > 0 else "하락"
            lines.append(f"  연속: {abs(streak)}일 {direction} 중")
        lines.append("")

    # ── Time Patterns ─────────────────────────────────────────
    tp = analyze_time_patterns(df)
    if tp:
        lines.append("■ 시간 패턴 (통계)")
        if "day_of_week" in tp and today_dow in tp["day_of_week"]:
            d = tp["day_of_week"][today_dow]
            lines.append(f"  {today_dow}요일 승률: {d['win_rate']}% (표본 {d['sample_count']}일)")

        if "summary" in tp:
            s = tp["summary"]
            lines.append(f"  최고 요일: {s['best_day']}")
            lines.append(f"  최저 요일: {s['worst_day']}")
            lines.append(f"  전체 승률: {s['overall_win_rate']}%")

        # Streak pattern
        if "streaks" in tp:
            close = df["close"]
            streak = _current_streak(close)
            streak_key = None
            if streak >= 2:
                streak_key = f"{abs(streak)}일_연속_상승_후"
            elif streak <= -2:
                streak_key = f"{abs(streak)}일_연속_하락_후"
            if streak_key and streak_key in tp["streaks"]:
                sp = tp["streaks"][streak_key]
                lines.append(f"  {streak_key}: 반전확률 {sp.get('reversal_rate', 'N/A')}% (표본 {sp.get('sample_count', 0)})")
        lines.append("")

    # ── Indicator Signals ─────────────────────────────────────
    if current_signals:
        active_buys = [s for s, v in current_signals.items() if v.get("signal") == "buy"]
        active_sells = [s for s, v in current_signals.items() if v.get("signal") == "sell"]
        if active_buys or active_sells:
            lines.append("■ 현재 활성 시그널")
            for name in active_buys[:5]:
                acc = current_signals[name].get("accuracy", "?")
                lines.append(f"  매수: {name} (적중률 {acc}%)")
            for name in active_sells[:5]:
                acc = current_signals[name].get("accuracy", "?")
                lines.append(f"  매도: {name} (적중률 {acc}%)")
            lines.append("")

    # ── Indicator Accuracy Summary ────────────────────────────
    ia = analyze_indicator_accuracy(df, top_n=5)
    if ia and "ranking_overall" in ia:
        lines.append("■ 지표 적중률 TOP 5")
        for ind in ia["ranking_overall"][:5]:
            lines.append(
                f"  {ind['name']}: 매수 {ind['buy_accuracy']}% / 매도 {ind['sell_accuracy']}% "
                f"(종합 {ind['combined_accuracy']}%)"
            )
        lines.append("")

    # ── Best Combos ───────────────────────────────────────────
    combos = find_best_combos(df, top_n=3)
    if combos:
        lines.append("■ 최고 지표 조합")
        for c in combos[:3]:
            lines.append(
                f"  {c['combo'][0]} + {c['combo'][1]}: "
                f"적중률 {c['accuracy']}%, 평균수익 {c['avg_return']:+.3f}% "
                f"(시그널 {c['signal_count']}회)"
            )
        lines.append("")

    # ── Macro Correlations ────────────────────────────────────
    if macro_data and "correlations" in macro_data:
        lines.append("■ 매크로 상관관계")
        for item in macro_data.get("strongest", [])[:5]:
            corr_str = f"상관 {item['correlation']:+.2f}"
            lead = item.get("lead_correlation", 0)
            lead_str = f", 선행 {lead:+.2f}" if abs(lead) > 0.1 else ""
            wr = item.get("win_rate_on_macro_up")
            wr_str = f", 매크로↑시 승률 {wr}%" if wr else ""
            lines.append(f"  {item['name']}: {corr_str}{lead_str}{wr_str}")

        if macro_data.get("lead_lag_signals"):
            lines.append("  ⚡ 선행 지표:")
            for name, info in list(macro_data["lead_lag_signals"].items())[:3]:
                lines.append(f"    {info['interpretation']}")
        lines.append("")

    return "\n".join(lines)


def get_current_signals(df: pd.DataFrame) -> dict:
    """Check which indicators are currently signaling buy/sell.

    Returns dict of {signal_name: {"signal": "buy"|"sell"|"none", "accuracy": float}}.
    """
    from app.analysis.signals.registry import list_signal_generators, get_signal_generator

    results = {}
    returns = df["close"].pct_change().shift(-1)

    for sig_name in list_signal_generators():
        try:
            sig_gen = get_signal_generator(sig_name)
            entry, exit_ = sig_gen(df)

            # Check last row for active signal
            signal = "none"
            if len(entry) > 0 and entry.iloc[-1]:
                signal = "buy"
            elif len(exit_) > 0 and exit_.iloc[-1]:
                signal = "sell"

            # Calculate historical accuracy
            buy_signals = entry.reindex(returns.index, fill_value=False)
            buy_next = returns[buy_signals]
            accuracy = round(float((buy_next > 0).mean()) * 100, 1) if len(buy_next) >= 3 else 0

            results[sig_name] = {"signal": signal, "accuracy": accuracy}
        except Exception:
            pass

    return results


def _current_streak(close: pd.Series) -> int:
    """Calculate current consecutive up/down streak. Positive = up, negative = down."""
    if len(close) < 2:
        return 0
    returns = close.pct_change().dropna()
    if len(returns) == 0:
        return 0

    streak = 0
    direction = 1 if returns.iloc[-1] > 0 else -1

    for i in range(len(returns) - 1, -1, -1):
        if (returns.iloc[i] > 0 and direction > 0) or (returns.iloc[i] < 0 and direction < 0):
            streak += 1
        else:
            break

    return streak * direction
