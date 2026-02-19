"""Tests for Rankings API endpoints."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def test_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    return user


class TestRankingsCatalog:
    @pytest.mark.asyncio
    async def test_returns_catalog(self, test_user):
        from app.api.v1.rankings import get_rankings_catalog

        result = await get_rankings_catalog(user=test_user)
        assert "rankings" in result
        assert len(result["rankings"]) == 4
        types = {r["type"] for r in result["rankings"]}
        assert "price" in types
        assert "volume" in types
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
    async def test_returns_list(self, test_user):
        from app.api.v1.rankings import get_price_rankings

        result = await get_price_rankings(direction="up", limit=30, user=test_user)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_direction_down(self, test_user):
        from app.api.v1.rankings import get_price_rankings

        result = await get_price_rankings(direction="down", limit=10, user=test_user)
        assert isinstance(result, list)


class TestVolumeRankings:
    @pytest.mark.asyncio
    async def test_returns_list(self, test_user):
        from app.api.v1.rankings import get_volume_rankings

        result = await get_volume_rankings(limit=30, user=test_user)
        assert isinstance(result, list)


class TestInterestStocks:
    @pytest.mark.asyncio
    async def test_returns_list(self, test_user):
        from app.api.v1.rankings import get_interest_stocks

        result = await get_interest_stocks(limit=20, user=test_user)
        assert isinstance(result, list)
