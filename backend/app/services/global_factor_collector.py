"""Global/macro factor collection via Yahoo Finance.

Collects KOSPI, KOSDAQ, VIX, USD/KRW, S&P 500, NASDAQ, US 10Y, WTI, Gold, DXY.
Stores as stock_code="_GLOBAL" in factor_snapshots table.
"""

from __future__ import annotations

import logging
import math
from datetime import date

import yfinance as yf

logger = logging.getLogger(__name__)

# Yahoo Finance symbols for global/macro factors
GLOBAL_SYMBOLS = {
    "kospi_index": {"symbol": "^KS11", "description": "KOSPI Index"},
    "kosdaq_index": {"symbol": "^KQ11", "description": "KOSDAQ Index"},
    "vix_value": {"symbol": "^VIX", "description": "CBOE Volatility Index"},
    "usdkrw_rate": {"symbol": "KRW=X", "description": "USD/KRW Exchange Rate"},
    "sp500_index": {"symbol": "^GSPC", "description": "S&P 500 Index"},
    "nasdaq_index": {"symbol": "^IXIC", "description": "NASDAQ Composite"},
    "us10y_yield": {"symbol": "^TNX", "description": "US 10Y Treasury Yield"},
    "wti_price": {"symbol": "CL=F", "description": "WTI Crude Oil Futures"},
    "gold_price": {"symbol": "GC=F", "description": "Gold Futures"},
    "dxy_index": {"symbol": "DX-Y.NYB", "description": "US Dollar Index"},
}


def _safe_float(val) -> float | None:
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def fetch_global_factors() -> dict[str, float]:
    """Fetch all global/macro factor values from Yahoo Finance.

    Returns dict like {"kospi_index": 2650.5, "vix_value": 18.3, ...}
    """
    symbols = [info["symbol"] for info in GLOBAL_SYMBOLS.values()]
    results: dict[str, float] = {}

    try:
        tickers = yf.Tickers(" ".join(symbols))

        for factor_name, info in GLOBAL_SYMBOLS.items():
            sym = info["symbol"]
            try:
                ticker = tickers.tickers.get(sym)
                if ticker is None:
                    continue
                hist = ticker.history(period="5d")
                if hist.empty:
                    continue

                close = _safe_float(hist["Close"].iloc[-1])
                if close is not None:
                    results[factor_name] = close

                # Also compute change_pct if we have > 1 day
                if len(hist) >= 2:
                    prev = _safe_float(hist["Close"].iloc[-2])
                    if prev and prev != 0:
                        change_pct = (close - prev) / prev * 100
                        safe_pct = _safe_float(change_pct)
                        if safe_pct is not None:
                            results[f"{factor_name}_change_pct"] = safe_pct

            except Exception as e:
                logger.debug("Failed to fetch %s (%s): %s", factor_name, sym, e)

    except Exception as e:
        logger.error("yfinance batch fetch failed: %s", e)

    return results


def get_global_factor_catalog() -> list[dict]:
    """Return catalog of available global factors."""
    catalog = []
    for name, info in GLOBAL_SYMBOLS.items():
        catalog.append({
            "name": name,
            "category": "macro",
            "description": info["description"],
            "symbol": info["symbol"],
        })
        catalog.append({
            "name": f"{name}_change_pct",
            "category": "macro",
            "description": f"{info['description']} daily change %",
            "symbol": info["symbol"],
        })
    return catalog
