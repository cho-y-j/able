"""Tests for Rankings API endpoints."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def test_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    return user


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db


@pytest.fixture
def mock_kis():
    kis = MagicMock()
    kis.get_price_ranking = AsyncMock(return_value=[
        {"rank": 1, "stock_code": "005930", "stock_name": "삼성전자",
         "price": 78000, "change_pct": 5.2, "volume": 12300000},
        {"rank": 2, "stock_code": "000660", "stock_name": "SK하이닉스",
         "price": 195000, "change_pct": 4.8, "volume": 8100000},
    ])
    kis.get_volume_ranking = AsyncMock(return_value=[
        {"rank": 1, "stock_code": "005930", "stock_name": "삼성전자",
         "price": 78000, "change_pct": 5.2, "volume": 15000000},
    ])
    return kis


class TestRankingsCatalog:
    @pytest.mark.asyncio
    async def test_returns_catalog(self, test_user):
        from app.api.v1.rankings import get_rankings_catalog

        result = await get_rankings_catalog(user=test_user)
        assert "rankings" in result
        assert len(result["rankings"]) == 5
        types = {r["type"] for r in result["rankings"]}
        assert "price" in types
        assert "volume" in types
        assert "trending" in types
        assert "themes" in types
        assert "interest" in types

    @pytest.mark.asyncio
    async def test_includes_theme_count(self, test_user):
        from app.api.v1.rankings import get_rankings_catalog

        result = await get_rankings_catalog(user=test_user)
        assert "theme_count" in result
        assert result["theme_count"] >= 10


class TestPriceRankings:
    @pytest.mark.asyncio
    async def test_returns_data_from_kis(self, test_user, mock_db, mock_kis):
        from app.api.v1.rankings import get_price_rankings

        with patch("app.api.v1.rankings.get_kis_client", AsyncMock(return_value=mock_kis)):
            result = await get_price_rankings(direction="up", limit=30, user=test_user, db=mock_db)
        assert len(result) == 2
        assert result[0].stock_code == "005930"
        assert result[0].change_pct == 5.2

    @pytest.mark.asyncio
    async def test_direction_down(self, test_user, mock_db, mock_kis):
        from app.api.v1.rankings import get_price_rankings

        with patch("app.api.v1.rankings.get_kis_client", AsyncMock(return_value=mock_kis)):
            result = await get_price_rankings(direction="down", limit=10, user=test_user, db=mock_db)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self, test_user, mock_db):
        from app.api.v1.rankings import get_price_rankings

        with patch("app.api.v1.rankings.get_kis_client", AsyncMock(side_effect=Exception("no creds"))):
            result = await get_price_rankings(direction="up", limit=30, user=test_user, db=mock_db)
        assert result == []


class TestVolumeRankings:
    @pytest.mark.asyncio
    async def test_returns_data_from_kis(self, test_user, mock_db, mock_kis):
        from app.api.v1.rankings import get_volume_rankings

        with patch("app.api.v1.rankings.get_kis_client", AsyncMock(return_value=mock_kis)):
            result = await get_volume_rankings(limit=30, user=test_user, db=mock_db)
        assert len(result) == 1
        assert result[0].stock_code == "005930"

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self, test_user, mock_db):
        from app.api.v1.rankings import get_volume_rankings

        with patch("app.api.v1.rankings.get_kis_client", AsyncMock(side_effect=Exception("fail"))):
            result = await get_volume_rankings(limit=30, user=test_user, db=mock_db)
        assert result == []


class TestInterestStocks:
    @pytest.mark.asyncio
    async def test_returns_scored_list(self, test_user, mock_db, mock_kis):
        from app.api.v1.rankings import get_interest_stocks

        with patch("app.api.v1.rankings.get_kis_client", AsyncMock(return_value=mock_kis)):
            result = await get_interest_stocks(limit=20, user=test_user, db=mock_db)
        assert isinstance(result, list)
        assert len(result) >= 1
        # Check first result has required fields
        first = result[0]
        assert first.stock_code == "005930"
        assert first.score >= 0

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self, test_user, mock_db):
        from app.api.v1.rankings import get_interest_stocks

        with patch("app.api.v1.rankings.get_kis_client", AsyncMock(side_effect=Exception("fail"))):
            result = await get_interest_stocks(limit=20, user=test_user, db=mock_db)
        assert result == []


class TestTrendingStocks:
    @pytest.mark.asyncio
    async def test_returns_trending_data(self, test_user):
        from app.api.v1.rankings import get_trending_stocks

        mock_data = [
            {"rank": 1, "stock_name": "삼성전자", "stock_code": "005930",
             "search_ratio": 12.5, "price": 78000, "change_pct": 2.63},
        ]
        with patch("app.services.trending_stocks.fetch_naver_trending", AsyncMock(return_value=mock_data)):
            result = await get_trending_stocks(limit=20, user=test_user)
        assert len(result) == 1
        assert result[0].stock_name == "삼성전자"
        assert result[0].search_ratio == 12.5

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self, test_user):
        from app.api.v1.rankings import get_trending_stocks

        with patch("app.services.trending_stocks.fetch_naver_trending", AsyncMock(side_effect=Exception("fail"))):
            result = await get_trending_stocks(limit=20, user=test_user)
        assert result == []


class TestRankingsCatalogIncludesTrending:
    @pytest.mark.asyncio
    async def test_catalog_has_trending(self, test_user):
        from app.api.v1.rankings import get_rankings_catalog

        result = await get_rankings_catalog(user=test_user)
        types = {r["type"] for r in result["rankings"]}
        assert "trending" in types
