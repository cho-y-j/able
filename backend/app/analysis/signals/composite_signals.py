"""Composite and multi-indicator signal generators."""

import numpy as np
import pandas as pd

from app.analysis.signals.registry import register_signal


@register_signal(
    "elder_impulse",
    category="composite",
    param_space={
        "ema_period": {"type": "int", "low": 10, "high": 20},
        "macd_fast": {"type": "int", "low": 10, "high": 14},
        "macd_slow": {"type": "int", "low": 24, "high": 30},
        "macd_signal": {"type": "int", "low": 7, "high": 11},
    },
)
def elder_impulse_signal(
    df: pd.DataFrame,
    *,
    ema_period: int = 13,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Elder Impulse: buy when both EMA and MACD histogram rise (green bar)."""
    close = df["close"]
    ema_val = close.ewm(span=ema_period, adjust=False).mean()
    ema_rising = ema_val > ema_val.shift(1)

    macd_line = close.ewm(span=macd_fast, adjust=False).mean() - close.ewm(
        span=macd_slow, adjust=False
    ).mean()
    signal_line = macd_line.ewm(span=macd_signal, adjust=False).mean()
    hist = macd_line - signal_line
    hist_rising = hist > hist.shift(1)

    # Green: both rising -> buy signal
    # Red: both falling -> sell signal
    green = ema_rising & hist_rising
    red = ~ema_rising & ~hist_rising

    entry = green & ~green.shift(1).fillna(False).astype(bool)
    exit_ = red
    return entry, exit_


@register_signal(
    "multi_ma_vote",
    category="composite",
    param_space={
        "fast": {"type": "int", "low": 5, "high": 15},
        "medium": {"type": "int", "low": 20, "high": 50},
        "slow": {"type": "int", "low": 50, "high": 200},
    },
)
def multi_ma_vote(
    df: pd.DataFrame,
    *,
    fast: int = 10,
    medium: int = 30,
    slow: int = 100,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy when price is above all 3 MAs (aligned uptrend), sell below 2+."""
    close = df["close"]
    ma_fast = close.ewm(span=fast, adjust=False).mean()
    ma_med = close.ewm(span=medium, adjust=False).mean()
    ma_slow = close.ewm(span=slow, adjust=False).mean()

    above_fast = close > ma_fast
    above_med = close > ma_med
    above_slow = close > ma_slow
    votes = above_fast.astype(int) + above_med.astype(int) + above_slow.astype(int)

    all_above = votes == 3
    entry = all_above & ~all_above.shift(1).fillna(False).astype(bool)
    exit_ = votes <= 1  # below 2 or more MAs
    return entry, exit_


@register_signal(
    "rsi_macd_combo",
    category="composite",
    param_space={
        "rsi_period": {"type": "int", "low": 7, "high": 21},
        "rsi_threshold": {"type": "int", "low": 30, "high": 50},
        "macd_fast": {"type": "int", "low": 8, "high": 14},
        "macd_slow": {"type": "int", "low": 20, "high": 30},
    },
)
def rsi_macd_combo(
    df: pd.DataFrame,
    *,
    rsi_period: int = 14,
    rsi_threshold: int = 40,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy when RSI rising from below threshold AND MACD crossing up."""
    close = df["close"]

    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / rsi_period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / rsi_period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = (100 - (100 / (1 + rs))).fillna(50)

    # MACD
    macd_line = close.ewm(span=macd_fast, adjust=False).mean() - close.ewm(
        span=macd_slow, adjust=False
    ).mean()
    signal_line = macd_line.ewm(span=macd_signal, adjust=False).mean()
    macd_above = macd_line > signal_line

    # Entry: RSI recovering from low + MACD bullish
    rsi_recovering = (rsi > rsi_threshold) & (rsi.shift(1) <= rsi_threshold)
    entry = rsi_recovering & macd_above
    exit_ = (rsi > 70) | (~macd_above & macd_above.shift(1).fillna(True).astype(bool))
    return entry, exit_


@register_signal(
    "obv_trend",
    category="composite",
    param_space={
        "obv_period": {"type": "int", "low": 10, "high": 30},
        "price_period": {"type": "int", "low": 10, "high": 30},
    },
)
def obv_trend_signal(
    df: pd.DataFrame,
    *,
    obv_period: int = 20,
    price_period: int = 20,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy when OBV trend and price trend are both up (volume confirms price)."""
    close = df["close"]
    volume = df["volume"]

    # OBV
    direction = np.sign(close.diff())
    obv = (volume * direction).cumsum()

    # OBV and price SMAs
    obv_sma = obv.rolling(obv_period).mean()
    price_sma = close.rolling(price_period).mean()

    obv_up = obv > obv_sma
    price_up = close > price_sma
    confirmed = obv_up & price_up

    entry = confirmed & ~confirmed.shift(1).fillna(False).astype(bool)
    exit_ = ~obv_up & ~price_up  # both trending down
    return entry, exit_
