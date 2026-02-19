"""Tests for Pattern API endpoints."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest


class MockResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


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
def mock_pattern():
    p = MagicMock()
    p.id = uuid.uuid4()
    p.name = "RSI Reversal Pattern"
    p.description = "Rising from RSI oversold"
    p.pattern_type = "rise_5pct_5day"
    p.feature_importance = {"rsi_14": 0.35, "macd_histogram": 0.2}
    p.model_metrics = {"accuracy": 0.72, "f1": 0.65}
    p.rule_description = "RSI가 40 이하에서 반등 후 MACD 골든크로스"
    p.rule_config = {"rules": [{"factor": "rsi_14", "operator": "<=", "threshold": 40}]}
    p.validation_results = {"walk_forward_sharpe": 1.2}
    p.status = "validated"
    p.sample_count = 500
    p.event_count = 45
    return p


class TestListPatterns:
    @pytest.mark.asyncio
    async def test_returns_list(self, test_user, mock_db, mock_pattern):
        from app.api.v1.patterns import list_patterns

        mock_db.execute = AsyncMock(return_value=MockResult([mock_pattern]))

        result = await list_patterns(status=None, limit=20, db=mock_db, user=test_user)
        assert len(result) == 1
        assert result[0].name == "RSI Reversal Pattern"
        assert result[0].status == "validated"

    @pytest.mark.asyncio
    async def test_empty_list(self, test_user, mock_db):
        from app.api.v1.patterns import list_patterns

        mock_db.execute = AsyncMock(return_value=MockResult([]))
        result = await list_patterns(status=None, limit=20, db=mock_db, user=test_user)
        assert result == []


class TestGetPattern:
    @pytest.mark.asyncio
    async def test_found(self, test_user, mock_db, mock_pattern):
        from app.api.v1.patterns import get_pattern

        mock_db.execute = AsyncMock(return_value=MockResult([mock_pattern]))

        result = await get_pattern(
            pattern_id=str(mock_pattern.id), db=mock_db, user=test_user
        )
        assert result.pattern_type == "rise_5pct_5day"
        assert result.feature_importance["rsi_14"] == 0.35

    @pytest.mark.asyncio
    async def test_not_found(self, test_user, mock_db):
        from app.api.v1.patterns import get_pattern
        from fastapi import HTTPException

        mock_db.execute = AsyncMock(return_value=MockResult([]))

        with pytest.raises(HTTPException) as exc_info:
            await get_pattern(
                pattern_id=str(uuid.uuid4()), db=mock_db, user=test_user
            )
        assert exc_info.value.status_code == 404


class TestDiscoverPattern:
    @pytest.mark.asyncio
    async def test_queues_discovery(self, test_user):
        from app.api.v1.patterns import discover_pattern, PatternDiscoverRequest

        request = PatternDiscoverRequest(
            pattern_type="rise_5pct_5day",
            threshold_pct=5.0,
            window_days=5,
        )
        result = await discover_pattern(request=request, user=test_user)
        assert result["status"] == "queued"


class TestActivatePattern:
    @pytest.mark.asyncio
    async def test_activate_validated(self, test_user, mock_db, mock_pattern):
        from app.api.v1.patterns import activate_pattern

        mock_pattern.status = "validated"
        mock_db.execute = AsyncMock(return_value=MockResult([mock_pattern]))

        result = await activate_pattern(
            pattern_id=str(mock_pattern.id), db=mock_db, user=test_user
        )
        assert result["status"] == "active"
        assert mock_pattern.status == "active"

    @pytest.mark.asyncio
    async def test_activate_not_found(self, test_user, mock_db):
        from app.api.v1.patterns import activate_pattern
        from fastapi import HTTPException

        mock_db.execute = AsyncMock(return_value=MockResult([]))

        with pytest.raises(HTTPException) as exc_info:
            await activate_pattern(
                pattern_id=str(uuid.uuid4()), db=mock_db, user=test_user
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_activate_invalid_status(self, test_user, mock_db, mock_pattern):
        from app.api.v1.patterns import activate_pattern
        from fastapi import HTTPException

        mock_pattern.status = "deprecated"
        mock_db.execute = AsyncMock(return_value=MockResult([mock_pattern]))

        with pytest.raises(HTTPException) as exc_info:
            await activate_pattern(
                pattern_id=str(mock_pattern.id), db=mock_db, user=test_user
            )
        assert exc_info.value.status_code == 400
