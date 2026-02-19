"""Unit tests for the Korean stock registry service."""

import pytest
from app.services.stock_registry import search_stocks, get_stock_by_code, resolve_stock_name


class TestSearchStocks:
    def test_search_by_korean_name(self):
        results = search_stocks("삼성전자")
        assert len(results) > 0
        assert results[0]["code"] == "005930"
        assert results[0]["name"] == "삼성전자"

    def test_search_by_code_prefix(self):
        results = search_stocks("0059")
        assert any(r["code"] == "005930" for r in results)

    def test_search_by_exact_code(self):
        results = search_stocks("005930")
        assert len(results) > 0
        assert results[0]["code"] == "005930"

    def test_search_snt_finds_korean_stocks(self):
        results = search_stocks("SNT")
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert any("SNT" in n for n in names)

    def test_search_case_insensitive(self):
        results_upper = search_stocks("SNT")
        results_lower = search_stocks("snt")
        assert results_upper == results_lower

    def test_search_empty_query(self):
        assert search_stocks("") == []
        assert search_stocks("   ") == []

    def test_search_limit(self):
        results = search_stocks("삼성", limit=3)
        assert len(results) <= 3

    def test_search_returns_market_info(self):
        results = search_stocks("005930")
        assert results[0]["market"] in ("KOSPI", "KOSDAQ")

    def test_search_name_contains(self):
        results = search_stocks("전자")
        assert len(results) > 0
        assert any("전자" in r["name"] for r in results)


class TestGetStockByCode:
    def test_existing_stock(self):
        stock = get_stock_by_code("005930")
        assert stock is not None
        assert stock.name == "삼성전자"
        assert stock.market == "KOSPI"

    def test_nonexistent_stock(self):
        assert get_stock_by_code("999999") is None


class TestResolveStockName:
    def test_resolve_known(self):
        assert resolve_stock_name("005930") == "삼성전자"

    def test_resolve_unknown(self):
        assert resolve_stock_name("999999") is None


class TestResolveStockCodeMarket:
    """Test that resolve_stock_code respects market parameter."""

    def test_kr_market_snt_resolves_to_korean(self):
        from app.integrations.data.yahoo_provider import resolve_stock_code
        code, name = resolve_stock_code("snt", market="kr")
        # Should find a Korean SNT stock, not US ticker
        assert code.isdigit() and len(code) == 6
        assert "SNT" in (name or "").upper() or code in ("003570", "036530", "064960", "100840")

    def test_us_market_snt_returns_ticker(self):
        from app.integrations.data.yahoo_provider import resolve_stock_code
        code, name = resolve_stock_code("snt", market="us")
        # Should return as US ticker
        assert code == "snt"

    def test_kr_market_numeric_code(self):
        from app.integrations.data.yahoo_provider import resolve_stock_code
        code, name = resolve_stock_code("005930", market="kr")
        assert code == "005930"

    def test_kr_market_korean_name(self):
        from app.integrations.data.yahoo_provider import resolve_stock_code
        code, name = resolve_stock_code("삼성전자", market="kr")
        assert code == "005930"
