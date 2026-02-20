"""Trending stocks service — scrapes Naver Finance popular search keywords.

Provides real-time trending stock data from Naver Finance,
which reflects what Korean retail investors are actively searching.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Naver Finance popular search (인기검색)
NAVER_POPULAR_URL = "https://finance.naver.com/sise/lastsearch2.naver"
# Naver Finance real-time search ranking
NAVER_REALTIME_URL = "https://finance.naver.com/sise/field_submit.naver"


async def fetch_naver_trending(limit: int = 30) -> list[dict[str, Any]]:
    """Fetch trending (popular search) stocks from Naver Finance.

    Returns list of:
        {"rank": 1, "stock_name": "삼성전자", "stock_code": "005930",
         "search_count": 12345, "change_pct": 2.5, "price": 78000}
    """
    results: list[dict[str, Any]] = []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                NAVER_POPULAR_URL,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.select_one("table.type_5")
        if not table:
            logger.warning("Naver trending: table.type_5 not found")
            return []

        rows = table.select("tr")
        rank = 0
        for row in rows:
            cells = row.select("td")
            if len(cells) < 6:
                continue

            rank += 1
            if rank > limit:
                break

            try:
                # Column layout: 순위, 검색종목, 검색비율, 현재가, 전일비, 등락률
                name_link = cells[1].select_one("a")
                if not name_link:
                    continue

                stock_name = name_link.get_text(strip=True)
                href = name_link.get("href", "")
                # Extract stock code from href like /item/main.naver?code=005930
                stock_code = ""
                if "code=" in href:
                    stock_code = href.split("code=")[-1].split("&")[0]

                search_ratio_text = cells[2].get_text(strip=True).replace("%", "").replace(",", "")
                price_text = cells[3].get_text(strip=True).replace(",", "")
                change_pct_text = cells[5].get_text(strip=True).replace("%", "").replace("+", "")

                search_ratio = _safe_parse_float(search_ratio_text)
                price = _safe_parse_int(price_text)
                change_pct = _safe_parse_float(change_pct_text)

                results.append({
                    "rank": rank,
                    "stock_name": stock_name,
                    "stock_code": stock_code,
                    "search_ratio": search_ratio,
                    "price": price,
                    "change_pct": change_pct,
                })

            except Exception as e:
                logger.debug("Failed to parse trending row: %s", e)
                continue

    except httpx.HTTPError as e:
        logger.warning("Naver trending fetch failed: %s", e)
    except Exception as e:
        logger.error("Naver trending unexpected error: %s", e)

    return results


def parse_trending_html(html: str, limit: int = 30) -> list[dict[str, Any]]:
    """Parse Naver Finance trending HTML (for testing without network).

    Same logic as fetch_naver_trending but takes raw HTML.
    """
    results: list[dict[str, Any]] = []
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.type_5")
    if not table:
        return []

    rows = table.select("tr")
    rank = 0
    for row in rows:
        cells = row.select("td")
        if len(cells) < 6:
            continue

        rank += 1
        if rank > limit:
            break

        try:
            name_link = cells[1].select_one("a")
            if not name_link:
                continue

            stock_name = name_link.get_text(strip=True)
            href = name_link.get("href", "")
            stock_code = ""
            if "code=" in href:
                stock_code = href.split("code=")[-1].split("&")[0]

            search_ratio_text = cells[2].get_text(strip=True).replace("%", "").replace(",", "")
            price_text = cells[3].get_text(strip=True).replace(",", "")
            change_pct_text = cells[5].get_text(strip=True).replace("%", "").replace("+", "")

            results.append({
                "rank": rank,
                "stock_name": stock_name,
                "stock_code": stock_code,
                "search_ratio": _safe_parse_float(search_ratio_text),
                "price": _safe_parse_int(price_text),
                "change_pct": _safe_parse_float(change_pct_text),
            })
        except Exception:
            continue

    return results


def _safe_parse_float(s: str) -> float:
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _safe_parse_int(s: str) -> int:
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0
