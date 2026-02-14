"""Indicator combination analysis: which indicators were most accurate on up vs down days."""

import logging
from typing import Callable

import numpy as np
import pandas as pd

from app.analysis.signals.registry import list_signal_generators, get_signal_generator

logger = logging.getLogger(__name__)


def analyze_indicator_accuracy(df: pd.DataFrame, top_n: int = 10) -> dict:
    """Analyze which indicators were most accurate on up and down days.

    For each signal generator, checks how often its buy/sell signals
    correctly predicted next-day direction.

    Returns:
        Dictionary with per-indicator accuracy stats and best combinations.
    """
    if df.empty or len(df) < 60:
        return {}

    close = df["close"]
    returns = close.pct_change().shift(-1)  # next-day return
    up_days = returns > 0
    down_days = returns < 0

    indicator_stats = {}
    sig_names = list_signal_generators()

    for sig_name in sig_names:
        try:
            sig_gen = get_signal_generator(sig_name)
            entry, exit_ = sig_gen(df)  # default params

            if entry.sum() < 5:
                continue

            # Buy signal accuracy (entry=True → next day up?)
            buy_signals = entry.reindex(returns.index, fill_value=False)
            buy_next = returns[buy_signals]
            buy_accuracy = float((buy_next > 0).mean()) * 100 if len(buy_next) > 0 else 0

            # Sell signal accuracy (exit_=True → next day down?)
            sell_signals = exit_.reindex(returns.index, fill_value=False)
            sell_next = returns[sell_signals]
            sell_accuracy = float((sell_next < 0).mean()) * 100 if len(sell_next) > 0 else 0

            # Average return when buy signal fires
            avg_return_on_buy = float(buy_next.mean()) * 100 if len(buy_next) > 0 else 0

            indicator_stats[sig_name] = {
                "buy_accuracy": round(buy_accuracy, 1),
                "sell_accuracy": round(sell_accuracy, 1),
                "combined_accuracy": round((buy_accuracy + sell_accuracy) / 2, 1),
                "avg_return_on_buy": round(avg_return_on_buy, 3),
                "buy_signal_count": int(buy_signals.sum()),
                "sell_signal_count": int(sell_signals.sum()),
            }
        except Exception as e:
            logger.debug("Indicator %s failed: %s", sig_name, e)

    if not indicator_stats:
        return {}

    # Rank indicators
    sorted_by_combined = sorted(
        indicator_stats.items(),
        key=lambda x: x[1]["combined_accuracy"],
        reverse=True,
    )

    # Best on up days (buy accuracy)
    sorted_by_buy = sorted(
        indicator_stats.items(),
        key=lambda x: x[1]["buy_accuracy"],
        reverse=True,
    )

    # Best on down days (sell accuracy)
    sorted_by_sell = sorted(
        indicator_stats.items(),
        key=lambda x: x[1]["sell_accuracy"],
        reverse=True,
    )

    return {
        "indicators": indicator_stats,
        "ranking_overall": [
            {"name": name, **stats} for name, stats in sorted_by_combined[:top_n]
        ],
        "best_for_up_days": [
            {"name": name, "buy_accuracy": stats["buy_accuracy"]}
            for name, stats in sorted_by_buy[:5]
        ],
        "best_for_down_days": [
            {"name": name, "sell_accuracy": stats["sell_accuracy"]}
            for name, stats in sorted_by_sell[:5]
        ],
    }


def find_best_combos(df: pd.DataFrame, top_n: int = 5) -> list[dict]:
    """Find the best 2-indicator combinations by consensus accuracy.

    Tests pairs of indicators: when both give buy signal simultaneously,
    measures next-day accuracy.
    """
    if df.empty or len(df) < 60:
        return []

    close = df["close"]
    returns = close.pct_change().shift(-1)

    # Generate all signals first
    signals: dict[str, pd.Series] = {}
    sig_names = list_signal_generators()

    for sig_name in sig_names:
        try:
            sig_gen = get_signal_generator(sig_name)
            entry, _ = sig_gen(df)
            if entry.sum() >= 3:
                signals[sig_name] = entry.reindex(returns.index, fill_value=False)
        except Exception:
            pass

    if len(signals) < 2:
        return []

    # Test all pairs
    combos = []
    names = list(signals.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            combined = signals[names[i]] & signals[names[j]]
            if combined.sum() < 3:
                continue

            next_returns = returns[combined]
            accuracy = float((next_returns > 0).mean()) * 100
            avg_ret = float(next_returns.mean()) * 100

            combos.append({
                "combo": [names[i], names[j]],
                "accuracy": round(accuracy, 1),
                "avg_return": round(avg_ret, 3),
                "signal_count": int(combined.sum()),
            })

    combos.sort(key=lambda x: x["accuracy"], reverse=True)
    return combos[:top_n]
