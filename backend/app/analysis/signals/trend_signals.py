"""Trend-following signal generators."""

import numpy as np
import pandas as pd

from app.analysis.signals.registry import register_signal


@register_signal(
    "rsi_mean_reversion",
    category="momentum",
    param_space={
        "period": {"type": "int", "low": 5, "high": 30},
        "oversold": {"type": "int", "low": 15, "high": 40},
        "overbought": {"type": "int", "low": 60, "high": 85},
    },
)
def rsi_mean_reversion(
    df: pd.DataFrame,
    *,
    period: int = 14,
    oversold: int = 30,
    overbought: int = 70,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy when RSI dips below oversold, sell when RSI rises above overbought."""
    close = df["close"]
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(50)
    return (rsi < oversold), (rsi > overbought)


@register_signal(
    "sma_crossover",
    category="trend",
    param_space={
        "fast_period": {"type": "int", "low": 5, "high": 30},
        "slow_period": {"type": "int", "low": 30, "high": 200},
    },
)
def sma_crossover(
    df: pd.DataFrame,
    *,
    fast_period: int = 10,
    slow_period: int = 50,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy when fast SMA crosses above slow SMA, sell on cross below."""
    close = df["close"]
    fast = close.rolling(window=fast_period, min_periods=fast_period).mean()
    slow = close.rolling(window=slow_period, min_periods=slow_period).mean()
    above = fast > slow
    entry = above & ~above.shift(1).fillna(False).astype(bool)
    exit_ = ~above & above.shift(1).fillna(True).astype(bool)
    return entry, exit_


@register_signal(
    "ema_crossover",
    category="trend",
    param_space={
        "fast_period": {"type": "int", "low": 5, "high": 25},
        "slow_period": {"type": "int", "low": 25, "high": 100},
    },
)
def ema_crossover(
    df: pd.DataFrame,
    *,
    fast_period: int = 9,
    slow_period: int = 21,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy when fast EMA crosses above slow EMA, sell on cross below."""
    close = df["close"]
    fast = close.ewm(span=fast_period, adjust=False).mean()
    slow = close.ewm(span=slow_period, adjust=False).mean()
    above = fast > slow
    entry = above & ~above.shift(1).fillna(False).astype(bool)
    exit_ = ~above & above.shift(1).fillna(True).astype(bool)
    return entry, exit_


@register_signal(
    "bb_bounce",
    category="volatility",
    param_space={
        "period": {"type": "int", "low": 10, "high": 30},
        "std_dev": {"type": "float", "low": 1.5, "high": 3.0},
    },
)
def bb_bounce(
    df: pd.DataFrame,
    *,
    period: int = 20,
    std_dev: float = 2.0,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy on touch of lower Bollinger Band, sell on touch of upper."""
    close = df["close"]
    sma = close.rolling(window=period, min_periods=period).mean()
    std = close.rolling(window=period, min_periods=period).std()
    lower = sma - std_dev * std
    upper = sma + std_dev * std
    return (close <= lower), (close >= upper)


@register_signal(
    "macd_crossover",
    category="trend",
    param_space={
        "fast": {"type": "int", "low": 8, "high": 16},
        "slow": {"type": "int", "low": 20, "high": 35},
        "signal": {"type": "int", "low": 5, "high": 12},
    },
)
def macd_crossover(
    df: pd.DataFrame,
    *,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy when MACD crosses above signal line, sell on cross below."""
    close = df["close"]
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()

    above = macd_line > signal_line
    entry = above & ~above.shift(1).fillna(False).astype(bool)
    exit_ = ~above & above.shift(1).fillna(True).astype(bool)
    return entry, exit_


@register_signal(
    "supertrend",
    category="trend",
    param_space={
        "period": {"type": "int", "low": 7, "high": 21},
        "multiplier": {"type": "float", "low": 1.5, "high": 4.0},
    },
)
def supertrend_signal(
    df: pd.DataFrame,
    *,
    period: int = 10,
    multiplier: float = 3.0,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy when Supertrend flips up, sell when it flips down."""
    hl2 = (df["high"] + df["low"]) / 2
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(window=period).mean()

    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr

    direction = pd.Series(0, index=df.index, dtype=int)
    if len(df) > period:
        # Initialize: start as downtrend so a real uptrend must prove itself
        mid = (upper.iloc[period] + lower.iloc[period]) / 2
        direction.iloc[period] = 1 if df["close"].iloc[period] > mid else -1
        for i in range(period + 1, len(df)):
            if df["close"].iloc[i] > upper.iloc[i - 1]:
                direction.iloc[i] = 1
            elif df["close"].iloc[i] < lower.iloc[i - 1]:
                direction.iloc[i] = -1
            else:
                direction.iloc[i] = direction.iloc[i - 1]

    # Entry: direction flips from -1 to 1, Exit: flips from 1 to -1
    entry = (direction == 1) & (direction.shift(1) == -1)
    exit_ = (direction == -1) & (direction.shift(1) == 1)
    # Also exit if we've been long and direction is still 0 at start
    entry = entry.fillna(False).astype(bool)
    exit_ = exit_.fillna(False).astype(bool)
    return entry, exit_


@register_signal(
    "ichimoku_cloud",
    category="trend",
    param_space={
        "tenkan": {"type": "int", "low": 7, "high": 12},
        "kijun": {"type": "int", "low": 20, "high": 35},
    },
)
def ichimoku_cloud_signal(
    df: pd.DataFrame,
    *,
    tenkan: int = 9,
    kijun: int = 26,
    senkou_b: int = 52,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy on Tenkan-Kijun cross above cloud, sell on cross below."""
    high, low, close = df["high"], df["low"], df["close"]

    tenkan_sen = (high.rolling(tenkan).max() + low.rolling(tenkan).min()) / 2
    kijun_sen = (high.rolling(kijun).max() + low.rolling(kijun).min()) / 2
    senkou_a = ((tenkan_sen + kijun_sen) / 2).shift(kijun)
    senkou_b_line = (
        (high.rolling(senkou_b).max() + low.rolling(senkou_b).min()) / 2
    ).shift(kijun)

    cloud_top = pd.concat([senkou_a, senkou_b_line], axis=1).max(axis=1)

    # Tenkan crosses above Kijun while price is above cloud
    tk_above = tenkan_sen > kijun_sen
    above_cloud = close > cloud_top

    entry = tk_above & ~tk_above.shift(1).fillna(False).astype(bool) & above_cloud
    exit_ = ~tk_above & tk_above.shift(1).fillna(True).astype(bool)
    return entry, exit_


@register_signal(
    "adx_trend",
    category="trend",
    param_space={
        "period": {"type": "int", "low": 10, "high": 25},
        "adx_threshold": {"type": "int", "low": 20, "high": 35},
    },
)
def adx_trend_signal(
    df: pd.DataFrame,
    *,
    period: int = 14,
    adx_threshold: int = 25,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy when +DI > -DI and ADX above threshold (strong trend), sell on reversal."""
    high, low, close = df["high"], df["low"], df["close"]

    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

    tr = pd.concat(
        [
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()

    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()

    strong_up = (plus_di > minus_di) & (adx > adx_threshold)
    entry = strong_up & ~strong_up.shift(1).fillna(False).astype(bool)
    exit_ = (minus_di > plus_di) | (adx < adx_threshold)
    return entry, exit_


@register_signal(
    "psar_reversal",
    category="trend",
    param_space={
        "af_start": {"type": "float", "low": 0.01, "high": 0.04},
        "af_max": {"type": "float", "low": 0.15, "high": 0.30},
    },
)
def psar_reversal_signal(
    df: pd.DataFrame,
    *,
    af_start: float = 0.02,
    af_max: float = 0.2,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Buy when PSAR flips below price (uptrend), sell when above."""
    high_arr, low_arr = df["high"].values, df["low"].values
    close_arr = df["close"].values
    n = len(df)
    sar = np.zeros(n)
    trend = np.ones(n)
    af = af_start
    ep = low_arr[0]
    sar[0] = high_arr[0]

    for i in range(1, n):
        if trend[i - 1] == 1:
            sar[i] = sar[i - 1] + af * (ep - sar[i - 1])
            sar[i] = min(sar[i], low_arr[i - 1], low_arr[max(0, i - 2)])
            if low_arr[i] < sar[i]:
                trend[i] = -1
                sar[i] = ep
                ep = low_arr[i]
                af = af_start
            else:
                trend[i] = 1
                if high_arr[i] > ep:
                    ep = high_arr[i]
                    af = min(af + af_start, af_max)
        else:
            sar[i] = sar[i - 1] + af * (ep - sar[i - 1])
            sar[i] = max(sar[i], high_arr[i - 1], high_arr[max(0, i - 2)])
            if high_arr[i] > sar[i]:
                trend[i] = 1
                sar[i] = ep
                ep = high_arr[i]
                af = af_start
            else:
                trend[i] = -1
                if low_arr[i] < ep:
                    ep = low_arr[i]
                    af = min(af + af_start, af_max)

    trend_series = pd.Series(trend, index=df.index)
    entry = (trend_series == 1) & (trend_series.shift(1) == -1)
    exit_ = (trend_series == -1) & (trend_series.shift(1) == 1)
    return entry, exit_


@register_signal(
    "donchian_breakout",
    category="trend",
    param_space={
        "entry_period": {"type": "int", "low": 10, "high": 55},
        "exit_period": {"type": "int", "low": 5, "high": 20},
    },
)
def donchian_breakout_signal(
    df: pd.DataFrame,
    *,
    entry_period: int = 20,
    exit_period: int = 10,
    **_kw,
) -> tuple[pd.Series, pd.Series]:
    """Turtle Trading: buy on highest-high breakout, sell on lowest-low break."""
    close = df["close"]
    entry_high = df["high"].rolling(window=entry_period).max().shift(1)
    exit_low = df["low"].rolling(window=exit_period).min().shift(1)

    entry = close > entry_high
    exit_ = close < exit_low
    return entry, exit_
