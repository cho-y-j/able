"""Momentum-based signal generators."""

import numpy as np
import pandas as pd

from app.analysis.signals.registry import register_signal


@register_signal(
    "stochastic_crossover",
    category="momentum",
    param_space={
        "k_period": {"type": "int", "low": 5, "high": 21},
        "d_period": {"type": "int", "low": 3, "high": 7},
        "oversold": {"type": "int", "low": 15, "high": 30},
        "overbought": {"type": "int", "low": 70, "high": 85},
    },
)
def stochastic_crossover(
    df: pd.DataFrame,
    *,
    k_period: int = 14,
    d_period: int = 3,
    oversold: int = 20,
    overbought: int = 80,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy when %K crosses above %D in oversold zone, sell in overbought."""
    low_min = df["low"].rolling(k_period).min()
    high_max = df["high"].rolling(k_period).max()
    k = 100 * (df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)
    d = k.rolling(d_period).mean()
    k = k.fillna(50)
    d = d.fillna(50)

    k_above_d = k > d
    entry = (
        k_above_d
        & ~k_above_d.shift(1).fillna(False).astype(bool)
        & (k < oversold + 10)  # recently oversold zone
    )
    exit_ = (
        ~k_above_d
        & k_above_d.shift(1).fillna(True).astype(bool)
        & (k > overbought - 10)
    )
    return entry, exit_


@register_signal(
    "cci_reversal",
    category="momentum",
    param_space={
        "period": {"type": "int", "low": 10, "high": 30},
        "lower": {"type": "int", "low": -150, "high": -80},
        "upper": {"type": "int", "low": 80, "high": 150},
    },
)
def cci_reversal(
    df: pd.DataFrame,
    *,
    period: int = 20,
    lower: int = -100,
    upper: int = 100,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy when CCI crosses above lower threshold, sell above upper."""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    cci = (tp - sma) / (0.015 * mad)
    cci = cci.fillna(0)

    entry = (cci > lower) & (cci.shift(1) <= lower)
    exit_ = (cci > upper) | ((cci < lower) & (cci.shift(1) >= lower))
    return entry, exit_


@register_signal(
    "williams_r_signal",
    category="momentum",
    param_space={
        "period": {"type": "int", "low": 7, "high": 28},
        "oversold": {"type": "int", "low": -90, "high": -75},
        "overbought": {"type": "int", "low": -25, "high": -10},
    },
)
def williams_r_signal(
    df: pd.DataFrame,
    *,
    period: int = 14,
    oversold: int = -80,
    overbought: int = -20,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy when Williams %R crosses above oversold, sell above overbought."""
    high_max = df["high"].rolling(period).max()
    low_min = df["low"].rolling(period).min()
    wr = -100 * (high_max - df["close"]) / (high_max - low_min).replace(0, np.nan)
    wr = wr.fillna(-50)

    entry = (wr > oversold) & (wr.shift(1) <= oversold)
    exit_ = (wr > overbought)
    return entry, exit_


@register_signal(
    "mfi_signal",
    category="momentum",
    param_space={
        "period": {"type": "int", "low": 7, "high": 21},
        "oversold": {"type": "int", "low": 15, "high": 30},
        "overbought": {"type": "int", "low": 70, "high": 85},
    },
)
def mfi_signal(
    df: pd.DataFrame,
    *,
    period: int = 14,
    oversold: int = 20,
    overbought: int = 80,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy when MFI exits oversold zone, sell when enters overbought."""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    mf = tp * df["volume"]
    tp_diff = tp.diff()

    positive_mf = mf.where(tp_diff > 0, 0).rolling(period).sum()
    negative_mf = mf.where(tp_diff < 0, 0).rolling(period).sum()

    mfi = 100 - (100 / (1 + positive_mf / negative_mf.replace(0, np.nan)))
    mfi = mfi.fillna(50)

    entry = (mfi > oversold) & (mfi.shift(1) <= oversold)
    exit_ = (mfi > overbought)
    return entry, exit_


@register_signal(
    "roc_momentum",
    category="momentum",
    param_space={
        "period": {"type": "int", "low": 5, "high": 30},
        "threshold": {"type": "float", "low": 0.5, "high": 5.0},
    },
)
def roc_momentum(
    df: pd.DataFrame,
    *,
    period: int = 12,
    threshold: float = 2.0,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy when ROC crosses above positive threshold, sell below negative."""
    close = df["close"]
    roc = ((close - close.shift(period)) / close.shift(period)) * 100
    roc = roc.fillna(0)

    entry = (roc > threshold) & (roc.shift(1) <= threshold)
    exit_ = (roc < -threshold)
    return entry, exit_
