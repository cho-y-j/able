"""Intraday analysis service for minute-level factor extraction and signals.

Provides real-time technical analysis on minute OHLCV data from KIS API.
Used for short-term trading decisions and intraday strategy monitoring.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _safe_float(val) -> float | None:
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def minute_data_to_df(minute_data: list[dict]) -> pd.DataFrame:
    """Convert KIS minute OHLCV list to pandas DataFrame.

    Input format: [{"time": "153000", "open": 78000, "high": 78100, ...}]
    Returns DataFrame sorted by time ascending with proper columns.
    """
    if not minute_data:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

    df = pd.DataFrame(minute_data)
    # Ensure numeric columns
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    # Sort by time ascending (KIS returns descending)
    df = df.sort_values("time").reset_index(drop=True)
    return df


def extract_minute_factors(df: pd.DataFrame) -> dict[str, float]:
    """Extract technical factors from minute OHLCV DataFrame.

    Uses shorter lookback windows appropriate for minute-level data.
    Returns dict of {factor_name: value}.
    """
    if df.empty or len(df) < 5:
        return {}

    results: dict[str, float] = {}

    # RSI (9-period for minute data)
    try:
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0).rolling(9).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(9).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        val = _safe_float(rsi.iloc[-1])
        if val is not None:
            results["rsi_9m"] = val
    except Exception:
        pass

    # MACD (5, 13, 4 for minute data — faster settings)
    try:
        ema5 = df["close"].ewm(span=5, adjust=False).mean()
        ema13 = df["close"].ewm(span=13, adjust=False).mean()
        macd = ema5 - ema13
        signal = macd.ewm(span=4, adjust=False).mean()
        hist = macd - signal
        val = _safe_float(hist.iloc[-1])
        if val is not None:
            results["macd_hist_m"] = val

        # Cross detection
        if len(macd) >= 2:
            prev = macd.iloc[-2] - signal.iloc[-2]
            curr = macd.iloc[-1] - signal.iloc[-1]
            if prev <= 0 and curr > 0:
                results["macd_cross_m"] = 1.0
            elif prev >= 0 and curr < 0:
                results["macd_cross_m"] = -1.0
            else:
                results["macd_cross_m"] = 0.0
    except Exception:
        pass

    # Bollinger Band position (10-period for minute)
    try:
        sma = df["close"].rolling(10).mean()
        std = df["close"].rolling(10).std()
        upper = sma + 2 * std
        lower = sma - 2 * std
        bw = upper.iloc[-1] - lower.iloc[-1]
        if bw > 0:
            val = _safe_float((df["close"].iloc[-1] - lower.iloc[-1]) / bw)
            if val is not None:
                results["bb_position_m"] = val
    except Exception:
        pass

    # Stochastic %K (9-period)
    try:
        low9 = df["low"].rolling(9).min()
        high9 = df["high"].rolling(9).max()
        denom = high9 - low9
        k = 100 * (df["close"] - low9) / denom.replace(0, np.nan)
        val = _safe_float(k.iloc[-1])
        if val is not None:
            results["stoch_k_m"] = val
    except Exception:
        pass

    # Relative volume (vs session average)
    try:
        avg_vol = df["volume"].mean()
        if avg_vol > 0:
            val = _safe_float(df["volume"].iloc[-1] / avg_vol)
            if val is not None:
                results["rvol_m"] = val
    except Exception:
        pass

    # Volume spike (current vs 5-bar avg)
    try:
        avg5 = df["volume"].rolling(5).mean()
        if avg5.iloc[-1] > 0:
            val = _safe_float(df["volume"].iloc[-1] / avg5.iloc[-1])
            if val is not None:
                results["vol_spike_m"] = val
    except Exception:
        pass

    # Price momentum (5-bar rate of change)
    try:
        if len(df) >= 6:
            prev = df["close"].iloc[-6]
            if prev > 0:
                val = _safe_float((df["close"].iloc[-1] - prev) / prev * 100)
                if val is not None:
                    results["roc_5m"] = val
    except Exception:
        pass

    # VWAP (Volume Weighted Average Price)
    try:
        tp = (df["high"] + df["low"] + df["close"]) / 3
        cum_tp_vol = (tp * df["volume"]).cumsum()
        cum_vol = df["volume"].cumsum()
        vwap = cum_tp_vol / cum_vol.replace(0, np.nan)
        vwap_val = _safe_float(vwap.iloc[-1])
        close_val = df["close"].iloc[-1]
        if vwap_val and close_val > 0:
            results["vwap"] = vwap_val
            results["vwap_spread_m"] = round((close_val - vwap_val) / vwap_val * 100, 4)
    except Exception:
        pass

    # ATR percent (9-period for minute)
    try:
        high, low, close = df["high"], df["low"], df["close"]
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(9).mean()
        c = close.iloc[-1]
        if c > 0:
            val = _safe_float(atr.iloc[-1] / c * 100)
            if val is not None:
                results["atr_pct_m"] = val
    except Exception:
        pass

    # Session high/low proximity
    try:
        session_high = df["high"].max()
        session_low = df["low"].min()
        current = df["close"].iloc[-1]
        rng = session_high - session_low
        if rng > 0:
            results["session_position"] = round((current - session_low) / rng, 4)
    except Exception:
        pass

    return results


def generate_minute_signals(factors: dict[str, float]) -> list[dict[str, Any]]:
    """Generate trading signals from minute-level factors.

    Returns list of signals with name, direction (bullish/bearish/neutral), strength (0-1).
    """
    signals: list[dict[str, Any]] = []

    # RSI signal
    rsi = factors.get("rsi_9m")
    if rsi is not None:
        if rsi < 25:
            signals.append({"name": "RSI 과매도", "direction": "bullish", "strength": 0.8, "detail": f"RSI {rsi:.1f}"})
        elif rsi < 35:
            signals.append({"name": "RSI 저점 접근", "direction": "bullish", "strength": 0.5, "detail": f"RSI {rsi:.1f}"})
        elif rsi > 75:
            signals.append({"name": "RSI 과매수", "direction": "bearish", "strength": 0.8, "detail": f"RSI {rsi:.1f}"})
        elif rsi > 65:
            signals.append({"name": "RSI 고점 접근", "direction": "bearish", "strength": 0.5, "detail": f"RSI {rsi:.1f}"})

    # MACD cross signal
    macd_cross = factors.get("macd_cross_m")
    if macd_cross == 1.0:
        signals.append({"name": "MACD 골든크로스", "direction": "bullish", "strength": 0.7, "detail": "단기 상승 전환"})
    elif macd_cross == -1.0:
        signals.append({"name": "MACD 데드크로스", "direction": "bearish", "strength": 0.7, "detail": "단기 하락 전환"})

    # Bollinger Band signal
    bb = factors.get("bb_position_m")
    if bb is not None:
        if bb < 0.1:
            signals.append({"name": "BB 하단 이탈", "direction": "bullish", "strength": 0.6, "detail": f"BB 위치: {bb:.2f}"})
        elif bb > 0.9:
            signals.append({"name": "BB 상단 이탈", "direction": "bearish", "strength": 0.6, "detail": f"BB 위치: {bb:.2f}"})

    # Volume spike signal
    vol_spike = factors.get("vol_spike_m")
    if vol_spike is not None and vol_spike > 3.0:
        roc = factors.get("roc_5m", 0)
        direction = "bullish" if roc > 0 else "bearish"
        signals.append({
            "name": "거래량 급증",
            "direction": direction,
            "strength": min(vol_spike / 5, 1.0),
            "detail": f"평균 대비 {vol_spike:.1f}배",
        })

    # VWAP spread signal
    vwap_spread = factors.get("vwap_spread_m")
    if vwap_spread is not None:
        if vwap_spread > 1.0:
            signals.append({"name": "VWAP 상회", "direction": "bullish", "strength": 0.5, "detail": f"VWAP 대비 +{vwap_spread:.2f}%"})
        elif vwap_spread < -1.0:
            signals.append({"name": "VWAP 하회", "direction": "bearish", "strength": 0.5, "detail": f"VWAP 대비 {vwap_spread:.2f}%"})

    # Stochastic signal
    stoch = factors.get("stoch_k_m")
    if stoch is not None:
        if stoch < 20:
            signals.append({"name": "스토캐스틱 과매도", "direction": "bullish", "strength": 0.6, "detail": f"%K: {stoch:.1f}"})
        elif stoch > 80:
            signals.append({"name": "스토캐스틱 과매수", "direction": "bearish", "strength": 0.6, "detail": f"%K: {stoch:.1f}"})

    return signals


def compute_minute_summary(
    factors: dict[str, float],
    signals: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute overall intraday analysis summary.

    Returns sentiment score (-1 to +1), signal summary, and recommendation.
    """
    if not signals:
        return {
            "sentiment": 0.0,
            "sentiment_label": "중립",
            "bullish_count": 0,
            "bearish_count": 0,
            "recommendation": "관망",
        }

    bullish = [s for s in signals if s["direction"] == "bullish"]
    bearish = [s for s in signals if s["direction"] == "bearish"]

    bull_score = sum(s["strength"] for s in bullish)
    bear_score = sum(s["strength"] for s in bearish)
    total = bull_score + bear_score

    sentiment = (bull_score - bear_score) / total if total > 0 else 0.0

    if sentiment > 0.3:
        label = "매수 우위"
        rec = "매수 검토"
    elif sentiment < -0.3:
        label = "매도 우위"
        rec = "매도/관망 검토"
    else:
        label = "중립"
        rec = "관망"

    return {
        "sentiment": round(sentiment, 3),
        "sentiment_label": label,
        "bullish_count": len(bullish),
        "bearish_count": len(bearish),
        "recommendation": rec,
    }
