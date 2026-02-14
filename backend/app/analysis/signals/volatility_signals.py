"""Volatility-based signal generators."""

import numpy as np
import pandas as pd

from app.analysis.signals.registry import register_signal


@register_signal(
    "keltner_breakout",
    category="volatility",
    param_space={
        "ema_period": {"type": "int", "low": 10, "high": 30},
        "atr_period": {"type": "int", "low": 7, "high": 20},
        "multiplier": {"type": "float", "low": 1.0, "high": 3.0},
    },
)
def keltner_breakout(
    df: pd.DataFrame,
    *,
    ema_period: int = 20,
    atr_period: int = 10,
    multiplier: float = 1.5,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy on close above upper Keltner, sell on close below lower."""
    close = df["close"]
    ema_val = close.ewm(span=ema_period, adjust=False).mean()

    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - close.shift()).abs(),
            (close.shift() - df["low"]).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr_val = tr.ewm(alpha=1 / atr_period, adjust=False).mean()

    upper = ema_val + multiplier * atr_val
    lower = ema_val - multiplier * atr_val

    entry = close > upper
    exit_ = close < lower
    return entry, exit_


@register_signal(
    "squeeze_momentum",
    category="volatility",
    param_space={
        "bb_period": {"type": "int", "low": 15, "high": 25},
        "bb_std": {"type": "float", "low": 1.5, "high": 2.5},
        "kc_period": {"type": "int", "low": 15, "high": 25},
        "kc_mult": {"type": "float", "low": 1.0, "high": 2.0},
    },
)
def squeeze_momentum(
    df: pd.DataFrame,
    *,
    bb_period: int = 20,
    bb_std: float = 2.0,
    kc_period: int = 20,
    kc_mult: float = 1.5,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Squeeze: BB inside KC = low vol. Buy on expansion with positive momentum."""
    close = df["close"]

    # Bollinger Bands
    bb_sma = close.rolling(bb_period).mean()
    bb_sd = close.rolling(bb_period).std()
    bb_upper = bb_sma + bb_std * bb_sd
    bb_lower = bb_sma - bb_std * bb_sd

    # Keltner Channels
    kc_ema = close.ewm(span=kc_period, adjust=False).mean()
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - close.shift()).abs(),
            (close.shift() - df["low"]).abs(),
        ],
        axis=1,
    ).max(axis=1)
    kc_atr = tr.ewm(alpha=1 / kc_period, adjust=False).mean()
    kc_upper = kc_ema + kc_mult * kc_atr
    kc_lower = kc_ema - kc_mult * kc_atr

    # Squeeze: BB inside KC
    squeeze_on = (bb_lower > kc_lower) & (bb_upper < kc_upper)
    squeeze_off = ~squeeze_on

    # Momentum: linear regression of (close - midline)
    midline = (df["high"].rolling(kc_period).max() + df["low"].rolling(kc_period).min()) / 2
    mom = close - midline

    # Buy when squeeze releases and momentum is positive
    entry = squeeze_off & squeeze_on.shift(1).fillna(False) & (mom > 0)
    exit_ = squeeze_off & squeeze_on.shift(1).fillna(False) & (mom < 0)
    # Also exit when momentum turns negative
    exit_ = exit_ | ((mom < 0) & (mom.shift(1) >= 0))
    return entry, exit_


@register_signal(
    "atr_trailing_stop",
    category="volatility",
    param_space={
        "atr_period": {"type": "int", "low": 7, "high": 21},
        "multiplier": {"type": "float", "low": 2.0, "high": 4.0},
        "entry_lookback": {"type": "int", "low": 10, "high": 30},
    },
)
def atr_trailing_stop(
    df: pd.DataFrame,
    *,
    atr_period: int = 14,
    multiplier: float = 3.0,
    entry_lookback: int = 20,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy on new high breakout, exit on ATR-based trailing stop."""
    close = df["close"]
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - close.shift()).abs(),
            (close.shift() - df["low"]).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / atr_period, adjust=False).mean()

    # Entry: close makes new high over lookback period
    highest = close.rolling(entry_lookback).max().shift(1)
    entry = close > highest

    # Exit: close drops below trailing stop (highest close - multiplier * ATR)
    running_max = close.expanding().max()
    trail_stop = running_max - multiplier * atr
    exit_ = close < trail_stop
    return entry, exit_


@register_signal(
    "bb_width_breakout",
    category="volatility",
    param_space={
        "period": {"type": "int", "low": 15, "high": 30},
        "std_dev": {"type": "float", "low": 1.5, "high": 2.5},
        "width_percentile": {"type": "int", "low": 5, "high": 20},
    },
)
def bb_width_breakout(
    df: pd.DataFrame,
    *,
    period: int = 20,
    std_dev: float = 2.0,
    width_percentile: int = 10,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy when BB width is at minimum (squeeze) and price breaks upper band."""
    close = df["close"]
    sma = close.rolling(period).mean()
    sd = close.rolling(period).std()
    upper = sma + std_dev * sd
    lower = sma - std_dev * sd
    width = (upper - lower) / sma

    # Width at percentile low = tight squeeze
    width_threshold = width.rolling(100, min_periods=50).quantile(width_percentile / 100)
    tight = width <= width_threshold

    entry = tight.shift(1).fillna(False) & (close > upper)
    exit_ = close < sma  # exit on return to mean
    return entry, exit_
