"""Factor collection service for storing point-in-time factor snapshots.

Collects technical factors from OHLCV data and global/macro factors
from external sources. Used for multi-factor analysis and pattern discovery.
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime
from typing import Callable

import numpy as np
import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.factor_snapshot import FactorSnapshot

logger = logging.getLogger(__name__)

# ── Factor Registry ──────────────────────────────────────────

FactorExtractor = Callable[[pd.DataFrame], float]

_FACTOR_REGISTRY: dict[str, dict] = {}

GLOBAL_STOCK_CODE = "_GLOBAL"


def register_factor(
    name: str,
    *,
    category: str = "general",
    description: str = "",
):
    """Decorator to register a factor extractor."""

    def decorator(func: FactorExtractor):
        _FACTOR_REGISTRY[name] = {
            "extractor": func,
            "category": category,
            "description": description,
        }
        return func

    return decorator


def get_factor_extractor(name: str) -> FactorExtractor:
    if name not in _FACTOR_REGISTRY:
        raise ValueError(f"Unknown factor: {name}")
    return _FACTOR_REGISTRY[name]["extractor"]


def list_factors() -> list[dict]:
    """Return catalog of all registered factors."""
    return [
        {
            "name": name,
            "category": entry["category"],
            "description": entry["description"],
        }
        for name, entry in sorted(_FACTOR_REGISTRY.items())
    ]


def list_factors_by_category() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for name, entry in _FACTOR_REGISTRY.items():
        result.setdefault(entry["category"], []).append(name)
    for v in result.values():
        v.sort()
    return result


def _safe_float(val) -> float | None:
    """Convert to float, return None for NaN/Inf."""
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


# ── Technical Factor Extractors ──────────────────────────────
# Each takes a DataFrame with columns: open, high, low, close, volume
# and returns a single float value for the most recent row.


@register_factor("rsi_14", category="momentum", description="RSI(14) current value")
def rsi_14(df: pd.DataFrame) -> float:
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])


@register_factor("macd_histogram", category="trend", description="MACD - Signal line")
def macd_histogram(df: pd.DataFrame) -> float:
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return float(hist.iloc[-1])


@register_factor("macd_signal_cross", category="trend", description="MACD/Signal cross direction (+1/-1/0)")
def macd_signal_cross(df: pd.DataFrame) -> float:
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    if len(macd) < 2:
        return 0.0
    prev_diff = macd.iloc[-2] - signal.iloc[-2]
    curr_diff = macd.iloc[-1] - signal.iloc[-1]
    if prev_diff <= 0 and curr_diff > 0:
        return 1.0  # golden cross
    elif prev_diff >= 0 and curr_diff < 0:
        return -1.0  # dead cross
    return 0.0


@register_factor("bb_position", category="volatility", description="Bollinger Band position (0=lower, 1=upper)")
def bb_position(df: pd.DataFrame) -> float:
    sma = df["close"].rolling(20).mean()
    std = df["close"].rolling(20).std()
    upper = sma + 2 * std
    lower = sma - 2 * std
    band_width = upper.iloc[-1] - lower.iloc[-1]
    if band_width == 0:
        return 0.5
    return float((df["close"].iloc[-1] - lower.iloc[-1]) / band_width)


@register_factor("sma_20_slope", category="trend", description="SMA20 5-day slope")
def sma_20_slope(df: pd.DataFrame) -> float:
    sma = df["close"].rolling(20).mean()
    if len(sma.dropna()) < 5:
        return 0.0
    slope = (sma.iloc[-1] - sma.iloc[-5]) / sma.iloc[-5] * 100
    return float(slope)


@register_factor("sma_50_spread", category="trend", description="(close - SMA50) / SMA50 * 100")
def sma_50_spread(df: pd.DataFrame) -> float:
    sma50 = df["close"].rolling(50).mean()
    val = sma50.iloc[-1]
    if val == 0 or pd.isna(val):
        return 0.0
    return float((df["close"].iloc[-1] - val) / val * 100)


@register_factor("ema_12_26_spread", category="trend", description="(EMA12 - EMA26) / EMA26 * 100")
def ema_12_26_spread(df: pd.DataFrame) -> float:
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    val = ema26.iloc[-1]
    if val == 0 or pd.isna(val):
        return 0.0
    return float((ema12.iloc[-1] - val) / val * 100)


@register_factor("adx_value", category="trend", description="ADX(14) current value")
def adx_value(df: pd.DataFrame) -> float:
    high, low, close = df["high"], df["low"], df["close"]
    plus_dm = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    # Zero out when opposing DM is larger
    plus_dm = plus_dm.where(plus_dm > minus_dm, 0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0)

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)

    atr14 = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr14.replace(0, np.nan))
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr14.replace(0, np.nan))

    di_sum = plus_di + minus_di
    dx = (100 * (plus_di - minus_di).abs() / di_sum.replace(0, np.nan))
    adx = dx.rolling(14).mean()
    return float(adx.iloc[-1])


@register_factor("stochastic_k", category="momentum", description="Stochastic %K(14) current value")
def stochastic_k(df: pd.DataFrame) -> float:
    low14 = df["low"].rolling(14).min()
    high14 = df["high"].rolling(14).max()
    denom = high14 - low14
    k = 100 * (df["close"] - low14) / denom.replace(0, np.nan)
    return float(k.iloc[-1])


@register_factor("cci_value", category="momentum", description="CCI(20) current value")
def cci_value(df: pd.DataFrame) -> float:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma = tp.rolling(20).mean()
    mad = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    cci = (tp - sma) / (0.015 * mad.replace(0, np.nan))
    return float(cci.iloc[-1])


@register_factor("williams_r", category="momentum", description="Williams %R(14) current value")
def williams_r(df: pd.DataFrame) -> float:
    high14 = df["high"].rolling(14).max()
    low14 = df["low"].rolling(14).min()
    denom = high14 - low14
    wr = -100 * (high14 - df["close"]) / denom.replace(0, np.nan)
    return float(wr.iloc[-1])


@register_factor("mfi_value", category="momentum", description="MFI(14) current value")
def mfi_value(df: pd.DataFrame) -> float:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    raw_mf = tp * df["volume"]
    delta = tp.diff()
    pos_mf = raw_mf.where(delta > 0, 0).rolling(14).sum()
    neg_mf = raw_mf.where(delta <= 0, 0).rolling(14).sum()
    mfr = pos_mf / neg_mf.replace(0, np.nan)
    mfi = 100 - (100 / (1 + mfr))
    return float(mfi.iloc[-1])


@register_factor("atr_pct", category="volatility", description="ATR(14) / close * 100")
def atr_pct(df: pd.DataFrame) -> float:
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    c = close.iloc[-1]
    if c == 0:
        return 0.0
    return float(atr.iloc[-1] / c * 100)


@register_factor("bb_width", category="volatility", description="Bollinger Band width / middle * 100")
def bb_width(df: pd.DataFrame) -> float:
    sma = df["close"].rolling(20).mean()
    std = df["close"].rolling(20).std()
    mid = sma.iloc[-1]
    if mid == 0 or pd.isna(mid):
        return 0.0
    width = 4 * std.iloc[-1]  # upper - lower = 4 * std
    return float(width / mid * 100)


@register_factor("obv_slope", category="volume", description="OBV 5-day slope (normalized)")
def obv_slope(df: pd.DataFrame) -> float:
    sign = np.sign(df["close"].diff())
    obv = (sign * df["volume"]).cumsum()
    if len(obv.dropna()) < 5:
        return 0.0
    # Normalize by average volume to get comparable units
    avg_vol = df["volume"].rolling(20).mean().iloc[-1]
    if avg_vol == 0 or pd.isna(avg_vol):
        return 0.0
    return float((obv.iloc[-1] - obv.iloc[-5]) / avg_vol)


@register_factor("rvol_20", category="volume", description="Today volume / 20-day average volume")
def rvol_20(df: pd.DataFrame) -> float:
    avg = df["volume"].rolling(20).mean()
    val = avg.iloc[-1]
    if val == 0 or pd.isna(val):
        return 1.0
    return float(df["volume"].iloc[-1] / val)


@register_factor("volume_ma_ratio", category="volume", description="Volume / 20-day MA volume")
def volume_ma_ratio(df: pd.DataFrame) -> float:
    avg = df["volume"].rolling(20).mean()
    val = avg.iloc[-1]
    if val == 0 or pd.isna(val):
        return 1.0
    return float(df["volume"].iloc[-1] / val)


@register_factor("roc_10", category="momentum", description="10-day rate of change (%)")
def roc_10(df: pd.DataFrame) -> float:
    if len(df) < 11:
        return 0.0
    prev = df["close"].iloc[-11]
    if prev == 0:
        return 0.0
    return float((df["close"].iloc[-1] - prev) / prev * 100)


@register_factor("close_vs_high_20", category="trend", description="close / 20-day high")
def close_vs_high_20(df: pd.DataFrame) -> float:
    high20 = df["high"].rolling(20).max()
    val = high20.iloc[-1]
    if val == 0 or pd.isna(val):
        return 1.0
    return float(df["close"].iloc[-1] / val)


@register_factor("close_vs_low_20", category="trend", description="close / 20-day low")
def close_vs_low_20(df: pd.DataFrame) -> float:
    low20 = df["low"].rolling(20).min()
    val = low20.iloc[-1]
    if val == 0 or pd.isna(val):
        return 1.0
    return float(df["close"].iloc[-1] / val)


# ── Extraction Helpers ───────────────────────────────────────


def extract_technical_factors(df: pd.DataFrame) -> dict[str, float]:
    """Extract all registered technical factors from OHLCV DataFrame.

    Returns dict of {factor_name: value}. Skips factors that fail or produce NaN.
    """
    results = {}
    for name, entry in _FACTOR_REGISTRY.items():
        try:
            val = entry["extractor"](df)
            safe = _safe_float(val)
            if safe is not None:
                results[name] = safe
        except Exception:
            logger.debug("Factor %s extraction failed", name, exc_info=True)
    return results


async def save_factor_snapshots(
    db: AsyncSession,
    stock_code: str,
    snapshot_dt: date,
    factors: dict[str, float],
    timeframe: str = "daily",
) -> int:
    """Upsert factor snapshots into DB. Returns count of saved factors."""
    if not factors:
        return 0

    values = []
    for name, value in factors.items():
        entry = _FACTOR_REGISTRY.get(name, {})
        values.append({
            "snapshot_date": snapshot_dt,
            "stock_code": stock_code,
            "timeframe": timeframe,
            "factor_name": name,
            "value": value,
            "metadata": {"category": entry.get("category", ""), "source": "collector"},
        })

    # Upsert using ON CONFLICT
    stmt = text("""
        INSERT INTO factor_snapshots (id, snapshot_date, stock_code, timeframe, factor_name, value, metadata, created_at, updated_at)
        VALUES (gen_random_uuid(), :snapshot_date, :stock_code, :timeframe, :factor_name, :value, :metadata::jsonb, now(), now())
        ON CONFLICT ON CONSTRAINT uq_factor_snapshot
        DO UPDATE SET value = EXCLUDED.value, metadata = EXCLUDED.metadata, updated_at = now()
    """)

    count = 0
    for v in values:
        try:
            await db.execute(stmt, v)
            count += 1
        except Exception:
            logger.warning("Failed to save factor %s for %s", v["factor_name"], stock_code)

    await db.commit()
    return count


async def get_latest_factors(
    db: AsyncSession,
    stock_code: str,
    timeframe: str = "daily",
) -> list[FactorSnapshot]:
    """Get latest factor values for a stock."""
    # Subquery for max date per factor
    subq = (
        select(
            FactorSnapshot.factor_name,
            FactorSnapshot.snapshot_date,
        )
        .where(
            FactorSnapshot.stock_code == stock_code,
            FactorSnapshot.timeframe == timeframe,
        )
        .distinct(FactorSnapshot.factor_name)
        .order_by(FactorSnapshot.factor_name, FactorSnapshot.snapshot_date.desc())
        .subquery()
    )

    stmt = (
        select(FactorSnapshot)
        .join(
            subq,
            (FactorSnapshot.factor_name == subq.c.factor_name)
            & (FactorSnapshot.snapshot_date == subq.c.snapshot_date),
        )
        .where(
            FactorSnapshot.stock_code == stock_code,
            FactorSnapshot.timeframe == timeframe,
        )
        .order_by(FactorSnapshot.factor_name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_factor_snapshots(
    db: AsyncSession,
    stock_code: str | None = None,
    factor_name: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[FactorSnapshot]:
    """Query factor snapshots with filters."""
    stmt = select(FactorSnapshot).order_by(FactorSnapshot.snapshot_date.desc())

    if stock_code:
        stmt = stmt.where(FactorSnapshot.stock_code == stock_code)
    if factor_name:
        stmt = stmt.where(FactorSnapshot.factor_name == factor_name)
    if date_from:
        stmt = stmt.where(FactorSnapshot.snapshot_date >= date_from)
    if date_to:
        stmt = stmt.where(FactorSnapshot.snapshot_date <= date_to)

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())
