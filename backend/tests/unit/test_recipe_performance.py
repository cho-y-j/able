"""Tests for GET /recipes/{recipe_id}/performance endpoint."""

import os
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from cryptography.fernet import Fernet as _Fernet

_test_fernet_key = _Fernet.generate_key().decode()
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-e2e")
os.environ.setdefault("ENCRYPTION_KEY", _test_fernet_key)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://able:able_secret@localhost:15432/able")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://able:able_secret@localhost:15432/able")
os.environ.setdefault("REDIS_URL", "redis://localhost:16379/1")

from app.models.user import User
from app.models.trading_recipe import TradingRecipe
from app.models.trade import Trade
from app.api.v1.recipes import get_recipe_performance


# ─── Mock Helpers ──────────────────────────────────────────


class MockResult:
    def __init__(self, items=None):
        self._items = items or []

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalars(self):
        return MockScalarResult(self._items)


class MockScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


def make_mock_db(execute_side_effects):
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=execute_side_effects)
    return db


def _make_user():
    u = MagicMock(spec=User)
    u.id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    u.email = "test@example.com"
    return u


def _make_recipe(user_id, recipe_id="22222222-2222-2222-2222-222222222222"):
    r = MagicMock(spec=TradingRecipe)
    r.id = uuid.UUID(recipe_id)
    r.user_id = user_id
    r.name = "Test Recipe"
    return r


def _make_trade(
    recipe_id, stock_code="005930", side="buy",
    entry_price=70000, exit_price=None,
    pnl=None, pnl_percent=None,
    entry_at=None, exit_at=None,
    quantity=10,
):
    t = MagicMock(spec=Trade)
    t.id = uuid.uuid4()
    t.recipe_id = uuid.UUID(recipe_id)
    t.stock_code = stock_code
    t.side = side
    t.entry_price = Decimal(str(entry_price))
    t.exit_price = Decimal(str(exit_price)) if exit_price else None
    t.pnl = Decimal(str(pnl)) if pnl is not None else None
    t.pnl_percent = pnl_percent
    t.quantity = quantity
    t.entry_at = entry_at or datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)
    t.exit_at = exit_at
    return t


RECIPE_ID = "22222222-2222-2222-2222-222222222222"


class TestGetRecipePerformance:
    @pytest.mark.asyncio
    async def test_recipe_not_found(self):
        user = _make_user()
        db = make_mock_db([MockResult()])  # Empty result for recipe query
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await get_recipe_performance(RECIPE_ID, 50, 0, db, user)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_no_trades(self):
        user = _make_user()
        recipe = _make_recipe(user.id)
        db = make_mock_db([
            MockResult([recipe]),     # recipe query
            MockResult([]),           # trades query
            MockResult([None]),       # avg slippage query
        ])
        result = await get_recipe_performance(RECIPE_ID, 50, 0, db, user)
        assert result.total_trades == 0
        assert result.closed_trades == 0
        assert result.total_pnl == 0.0
        assert result.win_rate is None
        assert result.equity_curve == []
        assert result.trades == []

    @pytest.mark.asyncio
    async def test_with_closed_trades(self):
        user = _make_user()
        recipe = _make_recipe(user.id)
        trades = [
            _make_trade(RECIPE_ID, pnl=5000, pnl_percent=5.0,
                        exit_price=75000, exit_at=datetime(2026, 1, 15, tzinfo=timezone.utc)),
            _make_trade(RECIPE_ID, pnl=3000, pnl_percent=3.0,
                        exit_price=73000, exit_at=datetime(2026, 1, 20, tzinfo=timezone.utc)),
            _make_trade(RECIPE_ID, pnl=-2000, pnl_percent=-2.0,
                        exit_price=68000, exit_at=datetime(2026, 1, 25, tzinfo=timezone.utc)),
        ]
        db = make_mock_db([
            MockResult([recipe]),
            MockResult(trades),
            MockResult([3.5]),  # avg slippage
        ])
        result = await get_recipe_performance(RECIPE_ID, 50, 0, db, user)

        assert result.total_trades == 3
        assert result.closed_trades == 3
        assert result.open_trades == 0
        assert result.win_rate == 66.7  # 2/3
        assert result.total_pnl == 6000.0  # 5000 + 3000 - 2000
        assert result.avg_win == 4.0  # (5.0 + 3.0) / 2
        assert result.avg_loss == -2.0
        assert result.profit_factor == 4.0  # 8000 / 2000
        assert result.avg_slippage_bps == 3.5
        assert len(result.equity_curve) == 3
        assert len(result.trades) == 3

    @pytest.mark.asyncio
    async def test_open_trades_excluded_from_stats(self):
        user = _make_user()
        recipe = _make_recipe(user.id)
        trades = [
            _make_trade(RECIPE_ID, pnl=5000, pnl_percent=5.0,
                        exit_price=75000, exit_at=datetime(2026, 1, 15, tzinfo=timezone.utc)),
            _make_trade(RECIPE_ID),  # open trade — no exit_at, no pnl
        ]
        db = make_mock_db([
            MockResult([recipe]),
            MockResult(trades),
            MockResult([None]),
        ])
        result = await get_recipe_performance(RECIPE_ID, 50, 0, db, user)

        assert result.total_trades == 2
        assert result.closed_trades == 1
        assert result.open_trades == 1
        assert result.win_rate == 100.0
        assert result.total_pnl == 5000.0

    @pytest.mark.asyncio
    async def test_equity_curve_daily_aggregation(self):
        """Two trades closing on same day should be summed."""
        user = _make_user()
        recipe = _make_recipe(user.id)
        same_day = datetime(2026, 1, 15, tzinfo=timezone.utc)
        trades = [
            _make_trade(RECIPE_ID, pnl=3000, pnl_percent=3.0,
                        exit_price=73000, exit_at=same_day),
            _make_trade(RECIPE_ID, pnl=2000, pnl_percent=2.0,
                        exit_price=72000, exit_at=same_day),
            _make_trade(RECIPE_ID, pnl=-1000, pnl_percent=-1.0,
                        exit_price=69000, exit_at=datetime(2026, 1, 20, tzinfo=timezone.utc)),
        ]
        db = make_mock_db([
            MockResult([recipe]),
            MockResult(trades),
            MockResult([None]),
        ])
        result = await get_recipe_performance(RECIPE_ID, 50, 0, db, user)

        # Two days in equity curve (Jan 15 aggregated, Jan 20 separate)
        assert len(result.equity_curve) == 2
        assert result.equity_curve[0].date == "2026-01-15"
        assert result.equity_curve[0].value == 5000.0  # 3000 + 2000
        assert result.equity_curve[1].date == "2026-01-20"
        assert result.equity_curve[1].value == 4000.0  # 5000 - 1000 cumulative

    @pytest.mark.asyncio
    async def test_pagination(self):
        user = _make_user()
        recipe = _make_recipe(user.id)
        trades = [
            _make_trade(RECIPE_ID, pnl=1000 * i, pnl_percent=float(i),
                        exit_price=71000 + i * 100,
                        exit_at=datetime(2026, 1, 10 + i, tzinfo=timezone.utc))
            for i in range(5)
        ]
        db = make_mock_db([
            MockResult([recipe]),
            MockResult(trades),
            MockResult([None]),
        ])
        result = await get_recipe_performance(RECIPE_ID, limit=2, offset=0, db=db, user=user)

        assert result.trades_total == 5
        assert len(result.trades) == 2  # Only first 2

    @pytest.mark.asyncio
    async def test_avg_slippage(self):
        user = _make_user()
        recipe = _make_recipe(user.id)
        db = make_mock_db([
            MockResult([recipe]),
            MockResult([]),    # no trades
            MockResult([4.2]),  # avg slippage
        ])
        result = await get_recipe_performance(RECIPE_ID, 50, 0, db, user)
        assert result.avg_slippage_bps == 4.2

    @pytest.mark.asyncio
    async def test_all_losing_trades(self):
        user = _make_user()
        recipe = _make_recipe(user.id)
        trades = [
            _make_trade(RECIPE_ID, pnl=-1000, pnl_percent=-1.0,
                        exit_price=69000, exit_at=datetime(2026, 1, 15, tzinfo=timezone.utc)),
            _make_trade(RECIPE_ID, pnl=-2000, pnl_percent=-2.0,
                        exit_price=68000, exit_at=datetime(2026, 1, 20, tzinfo=timezone.utc)),
        ]
        db = make_mock_db([
            MockResult([recipe]),
            MockResult(trades),
            MockResult([None]),
        ])
        result = await get_recipe_performance(RECIPE_ID, 50, 0, db, user)

        assert result.win_rate == 0.0
        assert result.total_pnl == -3000.0
        assert result.avg_win is None
        assert result.avg_loss == -1.5
        assert result.profit_factor == 0.0  # No wins → 0 / gross_losses = 0
