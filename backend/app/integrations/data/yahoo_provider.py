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

# Common Korean stock name → code mapping
_KR_NAME_TO_CODE: dict[str, str] = {
    "삼성전자": "005930", "삼성": "005930", "삼전": "005930",
    "SK하이닉스": "000660", "하이닉스": "000660",
    "LG에너지솔루션": "373220",
    "삼성바이오로직스": "207940", "삼바": "207940",
    "현대차": "005380", "현대자동차": "005380",
    "기아": "000270", "기아차": "000270",
    "셀트리온": "068270",
    "KB금융": "105560",
    "신한지주": "055550", "신한": "055550",
    "POSCO홀딩스": "005490", "포스코": "005490",
    "네이버": "035420", "NAVER": "035420",
    "카카오": "035720",
    "삼성SDI": "006400",
    "LG화학": "051910",
    "현대모비스": "012330",
    "삼성물산": "028260",
    "삼성생명": "032830",
    "하나금융지주": "086790", "하나금융": "086790",
    "카카오뱅크": "323410",
    "크래프톤": "259960",
    "두산에너빌리티": "034020",
    "SK이노베이션": "096770",
    "SK텔레콤": "017670",
    "LG전자": "066570",
    "한국전력": "015760", "한전": "015760",
    "카카오페이": "377300",
    "엔씨소프트": "036570", "엔씨": "036570",
    "KT": "030200",
    "SK": "034730",
}


def resolve_stock_code(raw_input: str, market: str = "kr") -> tuple[str, str | None]:
    """Resolve user input to a stock code and optional stock name.

    Args:
        raw_input: User input (code, name, or ticker)
        market: Market context — "kr" (default) or "us"
    """
    clean = raw_input.strip()

    # Check hardcoded name mapping first
    if clean in _KR_NAME_TO_CODE:
        return _KR_NAME_TO_CODE[clean], clean

    # Case-insensitive lookup in hardcoded map
    for name, code in _KR_NAME_TO_CODE.items():
        if name.lower() == clean.lower():
            return code, name

    # If it's a 6-digit number, use directly (Korean stock code) + resolve name
    if clean.isdigit() and len(clean) == 6:
        from app.services.stock_registry import resolve_stock_name
        return clean, resolve_stock_name(clean)

    # If it already has .KS/.KQ suffix, extract the code
    if clean.endswith((".KS", ".KQ")):
        code = clean.split(".")[0]
        from app.services.stock_registry import resolve_stock_name
        return code, resolve_stock_name(code)

    # For Korean market: search KRX registry for any text input
    if market == "kr":
        from app.services.stock_registry import search_stocks
        results = search_stocks(clean, limit=1)
        if results:
            return results[0]["code"], results[0]["name"]

    # US market or no KR match: treat as international ticker
    if clean.isascii() and any(c.isalpha() for c in clean):
        if market == "us":
            return clean, None
        # kr market but no match found — still return as-is for downstream error
        return clean, None

    # Unknown — return as-is
    return clean, None


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

    # Non-Korean tickers (ASCII letters only) — pass through
    if code.isascii() and any(c.isalpha() for c in code):
        return code

    # Pure numeric — determine market from code prefix
    if code.isdigit():
        if code[0] in _KOSDAQ_PREFIXES:
            return f"{code}.KQ"
        return f"{code}.KS"

    # Fallback — try to resolve as a name
    resolved, _ = resolve_stock_code(code)
    return krx_to_yahoo_ticker(resolved)


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
