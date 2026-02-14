"""Composite and pattern-based indicators.

These combine multiple indicators or derive higher-level signals
from price action patterns.
"""

import pandas as pd
import numpy as np
from app.analysis.indicators.registry import register_indicator


@register_indicator("HEIKIN_ASHI")
def heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """Heikin-Ashi candles for trend smoothing."""
    ha_close = (df["open"] + df["high"] + df["low"] + df["close"]) / 4

    ha_open = pd.Series(np.nan, index=df.index)
    ha_open.iloc[0] = (df["open"].iloc[0] + df["close"].iloc[0]) / 2
    for i in range(1, len(df)):
        ha_open.iloc[i] = (ha_open.iloc[i - 1] + ha_close.iloc[i - 1]) / 2

    ha_high = pd.concat([df["high"], ha_open, ha_close], axis=1).max(axis=1)
    ha_low = pd.concat([df["low"], ha_open, ha_close], axis=1).min(axis=1)

    df["HA_open"] = ha_open
    df["HA_high"] = ha_high
    df["HA_low"] = ha_low
    df["HA_close"] = ha_close
    return df


@register_indicator("PIVOT")
def pivot_points(df: pd.DataFrame) -> pd.DataFrame:
    """Classic pivot points (daily)."""
    pivot = (df["high"].shift(1) + df["low"].shift(1) + df["close"].shift(1)) / 3
    df["PIVOT"] = pivot
    df["PIVOT_R1"] = 2 * pivot - df["low"].shift(1)
    df["PIVOT_S1"] = 2 * pivot - df["high"].shift(1)
    df["PIVOT_R2"] = pivot + (df["high"].shift(1) - df["low"].shift(1))
    df["PIVOT_S2"] = pivot - (df["high"].shift(1) - df["low"].shift(1))
    df["PIVOT_R3"] = df["high"].shift(1) + 2 * (pivot - df["low"].shift(1))
    df["PIVOT_S3"] = df["low"].shift(1) - 2 * (df["high"].shift(1) - pivot)
    return df


@register_indicator("FIBONACCI")
def fibonacci_levels(df: pd.DataFrame, period: int = 50) -> pd.DataFrame:
    """Fibonacci retracement levels based on rolling high/low."""
    high = df["high"].rolling(period).max()
    low = df["low"].rolling(period).min()
    diff = high - low

    df[f"FIB_0"] = low
    df[f"FIB_236"] = low + 0.236 * diff
    df[f"FIB_382"] = low + 0.382 * diff
    df[f"FIB_500"] = low + 0.500 * diff
    df[f"FIB_618"] = low + 0.618 * diff
    df[f"FIB_786"] = low + 0.786 * diff
    df[f"FIB_100"] = high
    return df


@register_indicator("ZSCORE")
def zscore(df: pd.DataFrame, period: int = 20, column: str = "close") -> pd.DataFrame:
    """Z-Score: number of standard deviations from the mean."""
    mean = df[column].rolling(period).mean()
    std = df[column].rolling(period).std()
    df[f"ZSCORE_{period}"] = (df[column] - mean) / std.replace(0, np.nan)
    return df


@register_indicator("REGIME")
def regime_filter(df: pd.DataFrame, fast: int = 50, slow: int = 200) -> pd.DataFrame:
    """Market regime classification based on MA crossover and slope.

    Output:
    - REGIME: 1=bull, -1=bear, 0=sideways
    - REGIME_strength: 0-100 regime strength
    """
    sma_fast = df["close"].rolling(fast).mean()
    sma_slow = df["close"].rolling(slow).mean()

    # Slope of slow MA (annualized % change)
    slope = sma_slow.pct_change(20) * 252 * 100

    regime = pd.Series(0, index=df.index)
    regime = regime.where(~((sma_fast > sma_slow) & (slope > 5)), 1)
    regime = regime.where(~((sma_fast < sma_slow) & (slope < -5)), -1)

    # Strength: distance between MAs as % of slow MA
    strength = ((sma_fast - sma_slow) / sma_slow * 100).abs().clip(0, 100)

    df["REGIME"] = regime
    df["REGIME_strength"] = strength
    return df


@register_indicator("ELDER_IMPULSE")
def elder_impulse(df: pd.DataFrame, ema_period: int = 13) -> pd.DataFrame:
    """Elder Impulse System: combines EMA direction and MACD-H direction.

    Output: 1=green (bull), -1=red (bear), 0=blue (neutral)
    """
    ema_val = df["close"].ewm(span=ema_period, adjust=False).mean()
    ema_dir = ema_val.diff()

    # MACD histogram
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - signal_line
    macd_hist_dir = macd_hist.diff()

    impulse = pd.Series(0, index=df.index)
    impulse[(ema_dir > 0) & (macd_hist_dir > 0)] = 1
    impulse[(ema_dir < 0) & (macd_hist_dir < 0)] = -1

    df["ELDER_IMPULSE"] = impulse
    return df


@register_indicator("TREND_STRENGTH")
def trend_strength(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Trend strength: ratio of net price change to total absolute price change.

    Range: 0 (choppy) to 1 (strong trend)
    """
    abs_changes = df["close"].diff().abs().rolling(period).sum()
    net_change = df["close"].diff(period).abs()
    df[f"TREND_STR_{period}"] = (net_change / abs_changes.replace(0, np.nan)).clip(0, 1)
    return df


@register_indicator("VOL_REGIME")
def volatility_regime(df: pd.DataFrame, period: int = 20, lookback: int = 252) -> pd.DataFrame:
    """Volatility regime: percentile rank of current volatility.

    Output:
    - VOL_REGIME: 0-100 percentile
    - VOL_REGIME_class: low/normal/high/extreme
    """
    log_returns = np.log(df["close"] / df["close"].shift())
    vol = log_returns.rolling(period).std() * np.sqrt(252) * 100

    # Percentile rank
    pct_rank = vol.rolling(lookback, min_periods=50).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100, raw=False
    )

    df["VOL_REGIME"] = pct_rank

    # Classification
    vol_class = pd.Series("normal", index=df.index)
    vol_class[pct_rank < 25] = "low"
    vol_class[pct_rank > 75] = "high"
    vol_class[pct_rank > 95] = "extreme"
    df["VOL_REGIME_class"] = vol_class
    return df


@register_indicator("MACD_DIV")
def macd_divergence(df: pd.DataFrame, fast: int = 12, slow: int = 26,
                    signal: int = 9, lookback: int = 5) -> pd.DataFrame:
    """MACD histogram divergence detector.

    Detects when price makes new high/low but MACD-H doesn't confirm.
    1=bullish divergence, -1=bearish divergence, 0=none
    """
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    macd_hist = macd_line - signal_line

    price_new_low = df["close"] == df["close"].rolling(lookback * 5).min()
    macd_higher_low = macd_hist > macd_hist.rolling(lookback * 5).min()
    bullish_div = price_new_low & macd_higher_low

    price_new_high = df["close"] == df["close"].rolling(lookback * 5).max()
    macd_lower_high = macd_hist < macd_hist.rolling(lookback * 5).max()
    bearish_div = price_new_high & macd_lower_high

    divergence = pd.Series(0, index=df.index)
    divergence[bullish_div] = 1
    divergence[bearish_div] = -1

    df["MACD_DIV"] = divergence
    return df


@register_indicator("MTF_RSI")
def multitimeframe_rsi(df: pd.DataFrame, periods: tuple = (7, 14, 21)) -> pd.DataFrame:
    """Multi-timeframe RSI composite score.

    Averages RSI across multiple periods, weighted by period length.
    Output: 0-100 composite RSI score
    """
    total_weight = 0
    weighted_sum = pd.Series(0.0, index=df.index)

    for period in periods:
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1 / period, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1 / period, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi_val = 100 - (100 / (1 + rs))
        weight = period
        weighted_sum += rsi_val * weight
        total_weight += weight

    df["MTF_RSI"] = weighted_sum / total_weight
    return df


@register_indicator("TREND_QUALITY")
def trend_quality(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Trend quality index: measures smoothness and consistency of trend.

    Combines directional consistency and smoothness.
    Output: -100 (strong downtrend) to +100 (strong uptrend), 0 = no trend
    """
    changes = df["close"].diff()
    positive_count = changes.rolling(period).apply(lambda x: (x > 0).sum(), raw=True)
    direction_ratio = (positive_count / period - 0.5) * 2  # -1 to 1

    # Smoothness: R-squared of linear fit
    def r_squared(x):
        if len(x) < 3:
            return 0
        y = np.arange(len(x))
        corr = np.corrcoef(y, x)[0, 1]
        return corr ** 2 if not np.isnan(corr) else 0

    smoothness = df["close"].rolling(period).apply(r_squared, raw=True)

    df[f"TREND_QUAL_{period}"] = direction_ratio * smoothness * 100
    return df


@register_indicator("PRICE_CHANNEL")
def price_channel(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Price Channel Position: where price sits within its range.

    Output: 0 (at low) to 100 (at high)
    """
    high = df["high"].rolling(period).max()
    low = df["low"].rolling(period).min()
    df[f"PCHANNEL_{period}"] = ((df["close"] - low) / (high - low).replace(0, np.nan)) * 100
    return df
