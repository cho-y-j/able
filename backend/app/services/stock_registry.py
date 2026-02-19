"""Korean stock registry — in-memory database for fast stock search."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class StockInfo:
    code: str
    name: str
    market: str
    sector: str

    def to_dict(self) -> dict:
        return {"code": self.code, "name": self.name, "market": self.market, "sector": self.sector}


_stocks: list[StockInfo] = []
_code_index: dict[str, StockInfo] = {}
_loaded: bool = False

DATA_FILE = Path(__file__).parent.parent / "data" / "krx_stocks.json"


def _load():
    global _stocks, _code_index, _loaded
    if _loaded:
        return

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)

        _stocks = [StockInfo(**item) for item in raw]
        _code_index = {s.code: s for s in _stocks}
        _loaded = True
        logger.info("Loaded %d KRX stocks into registry", len(_stocks))
    except FileNotFoundError:
        logger.warning("KRX stock data file not found: %s", DATA_FILE)
        _loaded = True
    except Exception as e:
        logger.error("Failed to load KRX stock data: %s", e)
        _loaded = True


def search_stocks(query: str, limit: int = 20) -> list[dict]:
    """Search Korean stocks by code prefix, name prefix, or name substring.

    Priority: exact code > code prefix > name prefix > name contains
    """
    _load()

    if not query or not query.strip():
        return []

    q = query.strip()
    q_upper = q.upper()

    exact = []
    code_prefix = []
    name_prefix = []
    name_contains = []

    for stock in _stocks:
        if stock.code == q:
            exact.append(stock)
        elif stock.code.startswith(q):
            code_prefix.append(stock)
        elif stock.name.upper().startswith(q_upper):
            name_prefix.append(stock)
        elif q_upper in stock.name.upper():
            name_contains.append(stock)

    results = exact + code_prefix + name_prefix + name_contains
    return [s.to_dict() for s in results[:limit]]


def get_stock_by_code(code: str) -> StockInfo | None:
    _load()
    return _code_index.get(code)


def resolve_stock_name(code: str) -> str | None:
    stock = get_stock_by_code(code)
    return stock.name if stock else None
