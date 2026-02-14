"""Macro correlation analysis: stock vs indices, FX, futures, economic events."""

import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Macro tickers to correlate with
_MACRO_TICKERS = {
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
    "S&P500": "^GSPC",
    "나스닥": "^IXIC",
    "USD/KRW": "KRW=X",
    "미국10Y금리": "^TNX",
    "VIX": "^VIX",
    "WTI유가": "CL=F",
    "금": "GC=F",
}


def analyze_macro_correlation(
    df: pd.DataFrame,
    stock_code: str,
    lookback_days: int = 252,
) -> dict:
    """Analyze correlation between a stock and macro indicators.

    Args:
        df: Stock OHLCV DataFrame with DatetimeIndex.
        stock_code: Stock code for reference.
        lookback_days: Number of trading days to analyze.

    Returns:
        Dictionary with correlation data and actionable insights.
    """
    if df.empty or len(df) < 30:
        return {}

    try:
        import yfinance as yf
    except ImportError:
        return {"error": "yfinance not installed"}

    stock_returns = df["close"].pct_change().dropna()
    if len(stock_returns) == 0:
        return {}

    start_date = stock_returns.index[0].strftime("%Y-%m-%d")
    end_date = stock_returns.index[-1].strftime("%Y-%m-%d")

    correlations = {}
    lead_lag = {}  # Does the macro indicator lead the stock?

    for name, ticker in _MACRO_TICKERS.items():
        try:
            macro_df = yf.download(
                ticker, start=start_date, end=end_date,
                progress=False, auto_adjust=True,
            )
            if macro_df.empty or len(macro_df) < 20:
                continue

            # Normalize columns
            macro_df.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in macro_df.columns]
            macro_returns = macro_df["close"].pct_change().dropna()

            # Align dates
            common = stock_returns.index.intersection(macro_returns.index)
            if len(common) < 20:
                continue

            sr = stock_returns.loc[common]
            mr = macro_returns.loc[common]

            # Same-day correlation
            corr = float(sr.corr(mr))

            # Lead: macro yesterday → stock today
            mr_shifted = mr.shift(1).loc[common].dropna()
            common2 = sr.index.intersection(mr_shifted.index)
            lead_corr = float(sr.loc[common2].corr(mr_shifted.loc[common2])) if len(common2) > 20 else 0

            # When macro is strongly positive (>1%), stock win rate
            macro_up_strong = mr > 0.01
            if macro_up_strong.sum() >= 5:
                stock_on_macro_up = sr[macro_up_strong]
                win_rate_on_macro_up = float((stock_on_macro_up > 0).mean()) * 100
            else:
                win_rate_on_macro_up = None

            correlations[name] = {
                "correlation": round(corr, 3),
                "lead_correlation": round(lead_corr, 3),
                "win_rate_on_macro_up": round(win_rate_on_macro_up, 1) if win_rate_on_macro_up else None,
                "data_points": int(len(common)),
            }

            # Flag significant lead relationships
            if abs(lead_corr) > 0.15:
                direction = "동행" if lead_corr > 0 else "역행"
                lead_lag[name] = {
                    "lead_correlation": round(lead_corr, 3),
                    "direction": direction,
                    "interpretation": f"{name} 전일 상승 시 → 종목 {'상승' if lead_corr > 0 else '하락'} 경향",
                }

        except Exception as e:
            logger.debug("Macro %s (%s) failed: %s", name, ticker, e)

    if not correlations:
        return {}

    # Sort by absolute correlation
    sorted_corr = sorted(
        correlations.items(),
        key=lambda x: abs(x[1]["correlation"]),
        reverse=True,
    )

    return {
        "correlations": correlations,
        "strongest": [
            {"name": n, **c} for n, c in sorted_corr[:5]
        ],
        "lead_lag_signals": lead_lag,
        "stock_code": stock_code,
        "analysis_period": f"{start_date} ~ {end_date}",
        "data_points": int(len(stock_returns)),
    }
