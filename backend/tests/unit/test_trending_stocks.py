"""Tests for trending stocks service (Naver Finance scraping)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.trending_stocks import (
    parse_trending_html,
    fetch_naver_trending,
    _safe_parse_float,
    _safe_parse_int,
)


# Minimal HTML that mimics Naver Finance 인기검색 table structure
SAMPLE_HTML = """
<table class="type_5">
<tr>
<td>1</td>
<td><a href="/item/main.naver?code=005930">삼성전자</a></td>
<td>12.50%</td>
<td>78,000</td>
<td>+2,000</td>
<td>+2.63%</td>
</tr>
<tr>
<td>2</td>
<td><a href="/item/main.naver?code=000660">SK하이닉스</a></td>
<td>8.30%</td>
<td>195,000</td>
<td>+5,000</td>
<td>+2.63%</td>
</tr>
<tr>
<td>3</td>
<td><a href="/item/main.naver?code=035420">NAVER</a></td>
<td>5.20%</td>
<td>215,000</td>
<td>-3,000</td>
<td>-1.38%</td>
</tr>
</table>
"""


class TestParseTrendingHtml:
    def test_parses_sample_html(self):
        result = parse_trending_html(SAMPLE_HTML)
        assert len(result) == 3

    def test_first_entry_fields(self):
        result = parse_trending_html(SAMPLE_HTML)
        first = result[0]
        assert first["rank"] == 1
        assert first["stock_name"] == "삼성전자"
        assert first["stock_code"] == "005930"
        assert first["search_ratio"] == 12.50
        assert first["price"] == 78000

    def test_negative_change(self):
        result = parse_trending_html(SAMPLE_HTML)
        naver = result[2]
        assert naver["stock_name"] == "NAVER"
        assert naver["change_pct"] == -1.38

    def test_limit_parameter(self):
        result = parse_trending_html(SAMPLE_HTML, limit=2)
        assert len(result) == 2

    def test_empty_html(self):
        result = parse_trending_html("")
        assert result == []

    def test_no_table(self):
        result = parse_trending_html("<div>No table here</div>")
        assert result == []

    def test_extracts_stock_code_from_href(self):
        result = parse_trending_html(SAMPLE_HTML)
        assert result[0]["stock_code"] == "005930"
        assert result[1]["stock_code"] == "000660"
        assert result[2]["stock_code"] == "035420"

    def test_all_entries_have_required_fields(self):
        result = parse_trending_html(SAMPLE_HTML)
        for item in result:
            assert "rank" in item
            assert "stock_name" in item
            assert "stock_code" in item
            assert "search_ratio" in item
            assert "price" in item
            assert "change_pct" in item


class TestFetchNaverTrending:
    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_HTML
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.trending_stocks.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await fetch_naver_trending(limit=10)

        assert len(result) == 3
        assert result[0]["stock_name"] == "삼성전자"

    @pytest.mark.asyncio
    async def test_handles_network_error(self):
        import httpx

        with patch("app.services.trending_stocks.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.HTTPError("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await fetch_naver_trending()

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_empty_response(self):
        mock_resp = MagicMock()
        mock_resp.text = "<html></html>"
        mock_resp.raise_for_status = MagicMock()

        with patch("app.services.trending_stocks.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await fetch_naver_trending()

        assert result == []


class TestSafeParseHelpers:
    def test_safe_parse_float(self):
        assert _safe_parse_float("12.5") == 12.5
        assert _safe_parse_float("-3.2") == -3.2
        assert _safe_parse_float("invalid") == 0.0
        assert _safe_parse_float("") == 0.0

    def test_safe_parse_int(self):
        assert _safe_parse_int("78000") == 78000
        assert _safe_parse_int("78000.5") == 78000
        assert _safe_parse_int("invalid") == 0
        assert _safe_parse_int("") == 0
