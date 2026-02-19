"""Tests for Factor API endpoints."""

import uuid
from datetime import datetime, timezone, date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class MockResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None


@pytest.fixture
def test_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@test.com"
    return user


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db


class TestFactorCatalog:
    @pytest.mark.asyncio
    async def test_catalog_returns_list(self, test_user):
        from app.api.v1.factors import get_factor_catalog

        result = await get_factor_catalog(user=test_user)
        assert isinstance(result, list)
        assert len(result) >= 20
        for entry in result:
            assert hasattr(entry, "name")
            assert hasattr(entry, "category")
            assert hasattr(entry, "description")

    @pytest.mark.asyncio
    async def test_catalog_includes_momentum(self, test_user):
        from app.api.v1.factors import get_factor_catalog

        result = await get_factor_catalog(user=test_user)
        categories = {e.category for e in result}
        assert "momentum" in categories
        assert "trend" in categories
        assert "volatility" in categories
        assert "volume" in categories


class TestLatestFactors:
    @pytest.mark.asyncio
    async def test_returns_latest_factors(self, test_user, mock_db):
        from app.api.v1.factors import get_latest_stock_factors

        mock_snap = MagicMock()
        mock_snap.factor_name = "rsi_14"
        mock_snap.value = 55.3
        mock_snap.metadata_ = {"category": "momentum"}
        mock_snap.snapshot_date = date(2026, 2, 19)
        mock_snap.stock_code = "005930"
        mock_snap.timeframe = "daily"

        mock_db.execute = AsyncMock(return_value=MockResult([mock_snap]))

        result = await get_latest_stock_factors(
            stock_code="005930",
            db=mock_db,
            user=test_user,
        )
        assert len(result) == 1
        assert result[0].factor_name == "rsi_14"
        assert result[0].value == 55.3

    @pytest.mark.asyncio
    async def test_empty_returns_empty_list(self, test_user, mock_db):
        from app.api.v1.factors import get_latest_stock_factors

        mock_db.execute = AsyncMock(return_value=MockResult([]))

        result = await get_latest_stock_factors(
            stock_code="999999",
            db=mock_db,
            user=test_user,
        )
        assert result == []


class TestQuerySnapshots:
    @pytest.mark.asyncio
    async def test_returns_filtered_snapshots(self, test_user, mock_db):
        from app.api.v1.factors import query_factor_snapshots

        mock_snap = MagicMock()
        mock_snap.factor_name = "macd_histogram"
        mock_snap.value = 120.5
        mock_snap.metadata_ = {"category": "trend"}
        mock_snap.snapshot_date = date(2026, 2, 19)
        mock_snap.stock_code = "005930"
        mock_snap.timeframe = "daily"

        mock_db.execute = AsyncMock(return_value=MockResult([mock_snap]))

        result = await query_factor_snapshots(
            stock_code="005930",
            factor_name="macd_histogram",
            date_from=None,
            date_to=None,
            limit=100,
            offset=0,
            db=mock_db,
            user=test_user,
        )
        assert len(result) == 1
        assert result[0].factor_name == "macd_histogram"

    @pytest.mark.asyncio
    async def test_pagination(self, test_user, mock_db):
        from app.api.v1.factors import query_factor_snapshots

        mock_db.execute = AsyncMock(return_value=MockResult([]))

        result = await query_factor_snapshots(
            stock_code=None,
            factor_name=None,
            date_from=None,
            date_to=None,
            limit=10,
            offset=50,
            db=mock_db,
            user=test_user,
        )
        assert result == []
