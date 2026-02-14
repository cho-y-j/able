"""Multi-timeframe analysis — aggregate minute data into higher timeframes
and generate cross-timeframe signals."""

from __future__ import annotations

import pandas as pd
import numpy as np
from dataclasses import dataclass


@dataclass
class TimeframeSignal:
    """Signal from a single timeframe analysis."""
    timeframe: str
    trend: str  # "bullish", "bearish", "neutral"
    strength: float  # -1.0 to 1.0
    sma_20: float | None
    sma_50: float | None
    rsi_14: float | None
    macd_signal: str  # "bullish_cross", "bearish_cross", "neutral"
    volume_trend: str  # "increasing", "decreasing", "neutral"


@dataclass
class MTFAnalysis:
    """Multi-timeframe analysis result."""
    signals: dict[str, TimeframeSignal]
    consensus: str  # "strong_bullish", "bullish", "neutral", "bearish", "strong_bearish"
    consensus_score: float  # -1.0 to 1.0
    alignment: bool  # True if all timeframes agree
    dominant_timeframe: str
    recommendation: str  # "buy", "sell", "hold"


def resample_ohlcv(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    """Resample minute OHLCV data to a higher timeframe.

    Args:
        df: DataFrame with DatetimeIndex and open/high/low/close/volume columns
        interval: Target interval ('5min', '15min', '30min', '1h', '4h', '1D')

    Returns:
        Resampled DataFrame
    """
    if df.empty:
        return df

    resampled = df.resample(interval).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna(subset=["open"])

    return resampled


def compute_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period, min_periods=period).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    # When avg_loss is 0, RSI is 100 (all gains, no losses)
    rsi = pd.Series(np.nan, index=series.index)
    mask = avg_loss.notna() & avg_gain.notna()
    zero_loss = mask & (avg_loss == 0)
    nonzero_loss = mask & (avg_loss > 0)
    rsi[zero_loss] = 100.0
    rs = avg_gain[nonzero_loss] / avg_loss[nonzero_loss]
    rsi[nonzero_loss] = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def compute_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """MACD with signal line and histogram."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def analyze_timeframe(df: pd.DataFrame, timeframe: str) -> TimeframeSignal:
    """Analyze a single timeframe and produce a signal.

    Args:
        df: OHLCV DataFrame with at least 50 rows
        timeframe: Label string (e.g. "1min", "5min", "1D")

    Returns:
        TimeframeSignal dataclass
    """
    close = df["close"]

    # SMAs
    sma_20 = compute_sma(close, 20)
    sma_50 = compute_sma(close, 50)

    last_sma20 = sma_20.iloc[-1] if len(sma_20.dropna()) > 0 else None
    last_sma50 = sma_50.iloc[-1] if len(sma_50.dropna()) > 0 else None

    # RSI
    rsi = compute_rsi(close)
    last_rsi = rsi.iloc[-1] if len(rsi.dropna()) > 0 else None

    # MACD
    macd_data = compute_macd(close)
    macd_hist = macd_data["histogram"]
    macd_signal_str = "neutral"
    if len(macd_hist.dropna()) >= 2:
        if macd_hist.iloc[-1] > 0 and macd_hist.iloc[-2] <= 0:
            macd_signal_str = "bullish_cross"
        elif macd_hist.iloc[-1] < 0 and macd_hist.iloc[-2] >= 0:
            macd_signal_str = "bearish_cross"

    # Volume trend
    vol = df["volume"]
    vol_sma = vol.rolling(window=20, min_periods=10).mean()
    vol_trend = "neutral"
    if len(vol_sma.dropna()) > 0:
        ratio = vol.iloc[-1] / vol_sma.iloc[-1] if vol_sma.iloc[-1] > 0 else 1.0
        if ratio > 1.3:
            vol_trend = "increasing"
        elif ratio < 0.7:
            vol_trend = "decreasing"

    # Trend determination
    last_close = close.iloc[-1]
    score = 0.0
    count = 0

    # SMA trend
    if last_sma20 is not None and not np.isnan(last_sma20):
        score += 1.0 if last_close > last_sma20 else -1.0
        count += 1
    if last_sma50 is not None and not np.isnan(last_sma50):
        score += 1.0 if last_close > last_sma50 else -1.0
        count += 1
    if last_sma20 is not None and last_sma50 is not None and not np.isnan(last_sma20) and not np.isnan(last_sma50):
        score += 0.5 if last_sma20 > last_sma50 else -0.5
        count += 0.5

    # RSI
    if last_rsi is not None and not np.isnan(last_rsi):
        if last_rsi > 60:
            score += 0.5
        elif last_rsi < 40:
            score -= 0.5
        count += 0.5

    # MACD
    if macd_signal_str == "bullish_cross":
        score += 1.0
    elif macd_signal_str == "bearish_cross":
        score -= 1.0
    count += 1

    strength = score / max(count, 1)
    strength = max(-1.0, min(1.0, strength))

    if strength > 0.3:
        trend = "bullish"
    elif strength < -0.3:
        trend = "bearish"
    else:
        trend = "neutral"

    return TimeframeSignal(
        timeframe=timeframe,
        trend=trend,
        strength=round(strength, 3),
        sma_20=round(last_sma20, 2) if last_sma20 is not None and not np.isnan(last_sma20) else None,
        sma_50=round(last_sma50, 2) if last_sma50 is not None and not np.isnan(last_sma50) else None,
        rsi_14=round(last_rsi, 2) if last_rsi is not None and not np.isnan(last_rsi) else None,
        macd_signal=macd_signal_str,
        volume_trend=vol_trend,
    )


def multi_timeframe_analysis(
    minute_df: pd.DataFrame,
    daily_df: pd.DataFrame | None = None,
    timeframes: list[str] | None = None,
) -> MTFAnalysis:
    """Run multi-timeframe analysis on minute + daily data.

    Args:
        minute_df: 1-minute OHLCV DataFrame with DatetimeIndex
        daily_df: Optional daily OHLCV DataFrame
        timeframes: Which timeframes to analyze (default: 5min, 15min, 1h, 1D)

    Returns:
        MTFAnalysis with consensus and per-timeframe signals
    """
    if timeframes is None:
        timeframes = ["5min", "15min", "1h"]
        if daily_df is not None and len(daily_df) >= 50:
            timeframes.append("1D")

    signals: dict[str, TimeframeSignal] = {}

    # Analyze each timeframe
    for tf in timeframes:
        if tf == "1D":
            if daily_df is not None and len(daily_df) >= 50:
                signals[tf] = analyze_timeframe(daily_df, tf)
            continue

        resampled = resample_ohlcv(minute_df, tf)
        if len(resampled) < 50:
            # Not enough data — skip
            continue

        signals[tf] = analyze_timeframe(resampled, tf)

    if not signals:
        return MTFAnalysis(
            signals={},
            consensus="neutral",
            consensus_score=0.0,
            alignment=True,
            dominant_timeframe="",
            recommendation="hold",
        )

    # Weight higher timeframes more heavily
    tf_weights = {"1min": 0.5, "5min": 1.0, "15min": 1.5, "30min": 2.0, "1h": 2.5, "4h": 3.0, "1D": 4.0}

    weighted_sum = 0.0
    total_weight = 0.0
    for tf, sig in signals.items():
        w = tf_weights.get(tf, 1.0)
        weighted_sum += sig.strength * w
        total_weight += w

    consensus_score = weighted_sum / max(total_weight, 1.0)
    consensus_score = round(max(-1.0, min(1.0, consensus_score)), 3)

    # Consensus label
    if consensus_score > 0.5:
        consensus = "strong_bullish"
    elif consensus_score > 0.2:
        consensus = "bullish"
    elif consensus_score < -0.5:
        consensus = "strong_bearish"
    elif consensus_score < -0.2:
        consensus = "bearish"
    else:
        consensus = "neutral"

    # Check alignment
    trends = [s.trend for s in signals.values()]
    non_neutral = [t for t in trends if t != "neutral"]
    alignment = len(set(non_neutral)) <= 1 if non_neutral else True

    # Dominant timeframe = highest weight timeframe with data
    dominant = max(signals.keys(), key=lambda t: tf_weights.get(t, 0))

    # Recommendation
    if consensus_score > 0.3 and alignment:
        recommendation = "buy"
    elif consensus_score < -0.3 and alignment:
        recommendation = "sell"
    else:
        recommendation = "hold"

    return MTFAnalysis(
        signals=signals,
        consensus=consensus,
        consensus_score=consensus_score,
        alignment=alignment,
        dominant_timeframe=dominant,
        recommendation=recommendation,
    )
