"""Volume-based signal generators."""

import numpy as np
import pandas as pd

from app.analysis.signals.registry import register_signal


@register_signal(
    "volume_spike",
    category="volume",
    param_space={
        "lookback": {"type": "int", "low": 10, "high": 100},
        "rvol_threshold": {"type": "float", "low": 1.5, "high": 5.0},
    },
)
def volume_spike_signal(
    df: pd.DataFrame,
    *,
    lookback: int = 50,
    rvol_threshold: float = 2.0,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """RVOL (Relative Volume) spike detection.

    Entry: Volume exceeds rvol_threshold * average AND candle is bullish (close > open).
    Exit: Volume returns to normal (RVOL < 1.0).
    """
    volume = df["volume"]
    avg_volume = volume.rolling(window=lookback, min_periods=lookback).mean()
    rvol = volume / avg_volume.replace(0, np.nan)
    rvol = rvol.fillna(0)

    bullish = df["close"] > df["open"]
    entry = (rvol > rvol_threshold) & bullish
    exit_ = rvol < 1.0

    return entry.fillna(False), exit_.fillna(False)


@register_signal(
    "vwap_deviation",
    category="volume",
    param_space={
        "band_mult": {"type": "float", "low": 1.0, "high": 3.0},
    },
)
def vwap_deviation_signal(
    df: pd.DataFrame,
    *,
    band_mult: float = 2.0,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """VWAP deviation band signal.

    Entry: Price touches lower VWAP band then bounces back above.
    Exit: Price touches upper VWAP band.
    """
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    volume = df["volume"]

    cum_vol = volume.cumsum()
    cum_tp_vol = (typical_price * volume).cumsum()
    vwap = cum_tp_vol / cum_vol.replace(0, np.nan)

    # Standard deviation band
    squared_diff = (typical_price - vwap) ** 2
    cum_sq_diff_vol = (squared_diff * volume).cumsum()
    vwap_std = np.sqrt(cum_sq_diff_vol / cum_vol.replace(0, np.nan))

    lower_band = vwap - band_mult * vwap_std
    upper_band = vwap + band_mult * vwap_std

    close = df["close"]
    prev_close = close.shift(1)

    # Entry: was below lower band, now above it (bounce)
    entry = (prev_close < lower_band.shift(1)) & (close >= lower_band)
    # Exit: touches upper band
    exit_ = close >= upper_band

    return entry.fillna(False), exit_.fillna(False)


@register_signal(
    "volume_breakout",
    category="volume",
    param_space={
        "price_lookback": {"type": "int", "low": 10, "high": 60},
        "rvol_threshold": {"type": "float", "low": 1.5, "high": 5.0},
    },
)
def volume_breakout_signal(
    df: pd.DataFrame,
    *,
    price_lookback: int = 20,
    rvol_threshold: float = 2.0,
    volume_lookback: int = 50,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Volume + price breakout signal.

    Entry: Price breaks above N-day high AND volume spikes.
    Exit: Price drops below N-day low.
    """
    close = df["close"]
    volume = df["volume"]

    high_n = close.rolling(window=price_lookback, min_periods=price_lookback).max()
    low_n = close.rolling(window=price_lookback, min_periods=price_lookback).min()

    avg_volume = volume.rolling(window=volume_lookback, min_periods=volume_lookback).mean()
    rvol = volume / avg_volume.replace(0, np.nan)
    rvol = rvol.fillna(0)

    # Entry: price breaks above previous high + volume spike
    entry = (close > high_n.shift(1)) & (rvol > rvol_threshold)
    # Exit: price drops below previous low
    exit_ = close < low_n.shift(1)

    return entry.fillna(False), exit_.fillna(False)
