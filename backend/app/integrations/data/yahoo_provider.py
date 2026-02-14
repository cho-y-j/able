"""Yahoo Finance data provider using yfinance."""

import logging
from datetime import datetime

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None  # type: ignore

from app.integrations.data.base import DataProvider

logger = logging.getLogger(__name__)

# KRX stock code to Yahoo ticker mapping
# Korean stocks on Yahoo Finance use .KS (KOSPI) or .KQ (KOSDAQ) suffix
_KOSDAQ_PREFIXES = {"2", "3", "4"}  # KOSDAQ codes typically start with these


def krx_to_yahoo_ticker(stock_code: str) -> str:
    """Convert KRX stock code to Yahoo Finance ticker.

    Examples:
        005930 → 005930.KS (Samsung - KOSPI)
        247540 → 247540.KQ (Kakao Games - KOSDAQ)
    """
    code = stock_code.strip()

    # Already has Yahoo suffix
    if code.endswith((".KS", ".KQ")):
        return code

    # Non-Korean tickers (contains letters) — pass through
    if any(c.isalpha() for c in code):
        return code

    # Determine market from code prefix
    if code[0] in _KOSDAQ_PREFIXES:
        return f"{code}.KQ"
    return f"{code}.KS"


class YahooDataProvider(DataProvider):
    """Yahoo Finance data provider (no credentials required)."""

    def get_ohlcv(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        interval: str = "1d",
    ) -> pd.DataFrame:
        ticker = krx_to_yahoo_ticker(stock_code)

        # Normalize date format (YYYYMMDD → YYYY-MM-DD)
        start = _normalize_date(start_date)
        end = _normalize_date(end_date)

        logger.info(f"Fetching {ticker} from Yahoo Finance: {start} to {end} ({interval})")

        df = yf.download(
            ticker,
            start=start,
            end=end,
            interval=interval,
            auto_adjust=True,
            progress=False,
        )

        if df.empty:
            logger.warning(f"No data returned for {ticker}")
            return pd.DataFrame()

        # Standardize column names to lowercase
        df.columns = [c.lower() if isinstance(c, str) else c[0].lower() for c in df.columns]

        # Ensure we have the expected columns
        expected = ["open", "high", "low", "close", "volume"]
        for col in expected:
            if col not in df.columns:
                logger.warning(f"Missing column {col} in Yahoo data for {ticker}")
                return pd.DataFrame()

        df = df[expected]
        df.index.name = "date"

        # Drop any NaN rows
        df = df.dropna()

        return df

    def get_price(self, stock_code: str) -> dict:
        ticker = krx_to_yahoo_ticker(stock_code)
        info = yf.Ticker(ticker)

        try:
            fast_info = info.fast_info
            return {
                "stock_code": stock_code,
                "current_price": float(getattr(fast_info, "last_price", 0) or 0),
                "change": 0,
                "change_percent": 0,
                "volume": int(getattr(fast_info, "last_volume", 0) or 0),
                "high": float(getattr(fast_info, "day_high", 0) or 0),
                "low": float(getattr(fast_info, "day_low", 0) or 0),
                "open": float(getattr(fast_info, "open", 0) or 0),
            }
        except Exception as e:
            logger.warning(f"Failed to get price for {ticker}: {e}")
            return {
                "stock_code": stock_code,
                "current_price": 0,
                "change": 0,
                "change_percent": 0,
                "volume": 0,
                "high": 0,
                "low": 0,
                "open": 0,
            }

    @property
    def name(self) -> str:
        return "yahoo"

    @property
    def requires_credentials(self) -> bool:
        return False


def _normalize_date(d: str) -> str:
    """Convert YYYYMMDD to YYYY-MM-DD if needed."""
    d = d.strip()
    if len(d) == 8 and d.isdigit():
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return d
