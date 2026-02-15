"""Tests for monitor_active_recipes and poll_condition_search periodic tasks."""

import os
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-e2e")
os.environ.setdefault("ENCRYPTION_KEY", "test" * 8 + "==")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://able:able_secret@localhost:15432/able")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://able:able_secret@localhost:15432/able")
os.environ.setdefault("REDIS_URL", "redis://localhost:16379/1")

import json
import uuid
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock


# ── Helpers ──────────────────────────────────────────────


def _make_recipe(
    recipe_id=None,
    name="Test Recipe",
    stock_codes=None,
    signal_config=None,
    custom_filters=None,
    user_id=None,
):
    """Create a mock TradingRecipe object."""
    r = MagicMock()
    r.id = recipe_id or uuid.uuid4()
    r.name = name
    r.user_id = user_id or uuid.uuid4()
    r.stock_codes = stock_codes if stock_codes is not None else ["005930"]
    r.signal_config = signal_config or {
        "combinator": "AND",
        "signals": [
            {"type": "recommended", "strategy_type": "macd_crossover", "params": {}, "weight": 1.0}
        ],
    }
    r.custom_filters = custom_filters or {}
    r.risk_config = {"stop_loss": 3, "take_profit": 5, "position_size": 10}
    r.is_active = True
    return r


def _make_condition_recipe(user_id=None, condition_id="0001"):
    """Create a recipe with a kis_condition signal."""
    uid = user_id or uuid.uuid4()
    return _make_recipe(
        name="Condition Recipe",
        user_id=uid,
        signal_config={
            "combinator": "AND",
            "signals": [
                {"type": "kis_condition", "condition_id": condition_id},
                {"type": "recommended", "strategy_type": "rsi_mean_reversion", "params": {}, "weight": 1.0},
            ],
        },
    )


def _make_ohlcv_df(n=100, last_close=72000):
    """Create a realistic OHLCV DataFrame."""
    dates = pd.date_range("2025-06-01", periods=n, freq="B")
    close = np.linspace(70000, last_close, n)
    return pd.DataFrame({
        "open": close * 0.99,
        "high": close * 1.01,
        "low": close * 0.98,
        "close": close,
        "volume": np.random.randint(100000, 500000, n),
    }, index=dates)


def _make_credential(user_id):
    """Create a mock ApiCredential."""
    cred = MagicMock()
    cred.user_id = user_id
    cred.encrypted_key = "enc_key"
    cred.encrypted_secret = "enc_secret"
    cred.account_number = "12345678-01"
    cred.is_paper_trading = True
    cred.is_active = True
    return cred


# Patch targets: lazy imports inside function bodies → patch at source
_PATCH_DB = "app.tasks.periodic_tasks._get_sync_db"
_PATCH_PROVIDER = "app.integrations.data.factory.get_data_provider"
_PATCH_COMPOSER = "app.analysis.composer.SignalComposer"
_PATCH_REDIS = "redis.from_url"
_PATCH_VAULT = "app.tasks.periodic_tasks.get_vault"
_PATCH_KIS = "app.integrations.kis.client.KISClient"
_PATCH_ASYNCIO_RUN = "asyncio.run"


# ── monitor_active_recipes ──────────────────────────────


class TestMonitorActiveRecipes:
    """Tests for the monitor_active_recipes Celery task."""

    @patch(_PATCH_DB)
    def test_no_active_recipes(self, mock_db):
        """No active recipes → early return with evaluated=0."""
        from app.tasks.periodic_tasks import monitor_active_recipes

        db = MagicMock()
        mock_db.return_value = db
        db.query.return_value.filter.return_value.all.return_value = []

        result = monitor_active_recipes()

        assert result["status"] == "ok"
        assert result["evaluated"] == 0
        assert result["signals"] == 0
        db.close.assert_called_once()

    @patch(_PATCH_REDIS)
    @patch(_PATCH_COMPOSER)
    @patch(_PATCH_PROVIDER)
    @patch(_PATCH_DB)
    def test_skips_recipe_without_stock_codes(self, mock_db, mock_prov, mock_comp, mock_redis):
        """Recipe with empty stock_codes is skipped."""
        from app.tasks.periodic_tasks import monitor_active_recipes

        recipe = _make_recipe(stock_codes=[])
        db = MagicMock()
        mock_db.return_value = db
        db.query.return_value.filter.return_value.all.return_value = [recipe]

        result = monitor_active_recipes()

        assert result["status"] == "ok"
        assert result["evaluated"] == 0
        mock_prov.return_value.get_ohlcv.assert_not_called()

    @patch(_PATCH_REDIS)
    @patch(_PATCH_COMPOSER)
    @patch(_PATCH_PROVIDER)
    @patch(_PATCH_DB)
    def test_evaluates_single_recipe(self, mock_db, mock_prov, mock_comp, mock_redis):
        """Single recipe with one stock is evaluated."""
        from app.tasks.periodic_tasks import monitor_active_recipes

        recipe = _make_recipe(stock_codes=["005930"])
        db = MagicMock()
        mock_db.return_value = db
        db.query.return_value.filter.return_value.all.return_value = [recipe]

        df = _make_ohlcv_df()
        entry = pd.Series([False] * 100)
        exit_ = pd.Series([False] * 100)

        mock_prov.return_value.get_ohlcv.return_value = df
        mock_comp.return_value.compose.return_value = (entry, exit_)

        result = monitor_active_recipes()

        assert result["status"] == "ok"
        assert result["evaluated"] == 1
        assert result["signals"] == 0

    @patch(_PATCH_REDIS)
    @patch(_PATCH_COMPOSER)
    @patch(_PATCH_PROVIDER)
    @patch(_PATCH_DB)
    def test_evaluates_multiple_recipes(self, mock_db, mock_prov, mock_comp, mock_redis):
        """Multiple recipes are all evaluated."""
        from app.tasks.periodic_tasks import monitor_active_recipes

        r1 = _make_recipe(name="R1", stock_codes=["005930"])
        r2 = _make_recipe(name="R2", stock_codes=["000660", "035720"])
        db = MagicMock()
        mock_db.return_value = db
        db.query.return_value.filter.return_value.all.return_value = [r1, r2]

        df = _make_ohlcv_df()
        entry = pd.Series([False] * 100)
        exit_ = pd.Series([False] * 100)

        mock_prov.return_value.get_ohlcv.return_value = df
        mock_comp.return_value.compose.return_value = (entry, exit_)

        result = monitor_active_recipes()

        assert result["evaluated"] == 3  # 1 + 2 stocks

    @patch(_PATCH_REDIS)
    @patch(_PATCH_COMPOSER)
    @patch(_PATCH_PROVIDER)
    @patch(_PATCH_DB)
    def test_entry_signal_cached_to_redis(self, mock_db, mock_prov, mock_comp, mock_redis):
        """Entry signal detected → data cached in Redis."""
        from app.tasks.periodic_tasks import monitor_active_recipes

        recipe = _make_recipe(stock_codes=["005930"])
        db = MagicMock()
        mock_db.return_value = db
        db.query.return_value.filter.return_value.all.return_value = [recipe]

        df = _make_ohlcv_df()
        entry = pd.Series([False] * 99 + [True])  # Last bar = entry
        exit_ = pd.Series([False] * 100)

        mock_prov.return_value.get_ohlcv.return_value = df
        mock_comp.return_value.compose.return_value = (entry, exit_)

        mock_r = MagicMock()
        mock_redis.return_value = mock_r

        result = monitor_active_recipes()

        assert result["signals"] == 1
        mock_r.set.assert_called_once()
        call_args = mock_r.set.call_args
        key = call_args[0][0]
        assert "recipe:" in key
        assert ":signal:005930" in key
        cached = json.loads(call_args[0][1])
        assert cached["should_enter"] is True
        assert cached["stock_code"] == "005930"

    @patch(_PATCH_REDIS)
    @patch(_PATCH_COMPOSER)
    @patch(_PATCH_PROVIDER)
    @patch(_PATCH_DB)
    def test_ohlcv_fetch_failure_skipped(self, mock_db, mock_prov, mock_comp, mock_redis):
        """OHLCV fetch error skips that stock, continues to next."""
        from app.tasks.periodic_tasks import monitor_active_recipes

        recipe = _make_recipe(stock_codes=["005930", "000660"])
        db = MagicMock()
        mock_db.return_value = db
        db.query.return_value.filter.return_value.all.return_value = [recipe]

        df = _make_ohlcv_df()
        entry = pd.Series([False] * 100)
        exit_ = pd.Series([False] * 100)

        # First stock raises, second succeeds
        mock_prov.return_value.get_ohlcv.side_effect = [Exception("Network error"), df]
        mock_comp.return_value.compose.return_value = (entry, exit_)

        result = monitor_active_recipes()

        assert result["status"] == "ok"
        assert result["evaluated"] == 2

    @patch(_PATCH_REDIS)
    @patch(_PATCH_COMPOSER)
    @patch(_PATCH_PROVIDER)
    @patch(_PATCH_DB)
    def test_composer_error_skipped(self, mock_db, mock_prov, mock_comp, mock_redis):
        """SignalComposer error skips that stock."""
        from app.tasks.periodic_tasks import monitor_active_recipes

        recipe = _make_recipe(stock_codes=["005930"])
        db = MagicMock()
        mock_db.return_value = db
        db.query.return_value.filter.return_value.all.return_value = [recipe]

        df = _make_ohlcv_df()
        mock_prov.return_value.get_ohlcv.return_value = df
        mock_comp.return_value.compose.side_effect = ValueError("bad config")

        result = monitor_active_recipes()

        assert result["status"] == "ok"
        assert result["signals"] == 0

    @patch(_PATCH_REDIS)
    @patch(_PATCH_COMPOSER)
    @patch(_PATCH_PROVIDER)
    @patch(_PATCH_DB)
    def test_custom_filters_block_entry(self, mock_db, mock_prov, mock_comp, mock_redis):
        """Custom filters can block an entry signal."""
        from app.tasks.periodic_tasks import monitor_active_recipes

        recipe = _make_recipe(
            stock_codes=["005930"],
            custom_filters={"volume_min": 99999999},  # Very high minimum
        )
        db = MagicMock()
        mock_db.return_value = db
        db.query.return_value.filter.return_value.all.return_value = [recipe]

        df = _make_ohlcv_df()
        entry = pd.Series([False] * 99 + [True])
        exit_ = pd.Series([False] * 100)

        mock_prov.return_value.get_ohlcv.return_value = df
        mock_comp.return_value.compose.return_value = (entry, exit_)

        result = monitor_active_recipes()

        assert result["signals"] == 0  # Blocked by volume filter


# ── poll_condition_search ────────────────────────────────


class TestPollConditionSearch:
    """Tests for the poll_condition_search Celery task."""

    @patch(_PATCH_DB)
    def test_no_condition_recipes(self, mock_db):
        """No active recipes with kis_condition → polled=0."""
        from app.tasks.periodic_tasks import poll_condition_search

        recipe = _make_recipe()  # Normal signals only
        db = MagicMock()
        mock_db.return_value = db
        db.query.return_value.filter.return_value.all.return_value = [recipe]

        result = poll_condition_search()

        assert result["status"] == "ok"
        assert result["polled"] == 0

    @patch(_PATCH_ASYNCIO_RUN)
    @patch(_PATCH_KIS)
    @patch(_PATCH_REDIS)
    @patch(_PATCH_VAULT)
    @patch(_PATCH_DB)
    def test_polls_condition_search(self, mock_db, mock_vault, mock_redis, mock_kis, mock_arun):
        """Condition search is executed and results cached in Redis."""
        from app.tasks.periodic_tasks import poll_condition_search

        uid = uuid.uuid4()
        recipe = _make_condition_recipe(user_id=uid, condition_id="0001")
        cred = _make_credential(uid)

        db = MagicMock()
        mock_db.return_value = db
        db.query.return_value.filter.return_value.all.return_value = [recipe]
        db.query.return_value.filter.return_value.first.return_value = cred

        mock_vault.return_value.decrypt.side_effect = ["app_key", "app_secret"]

        search_results = [{"stock_code": "005930", "stock_name": "삼성전자"}]
        mock_arun.return_value = search_results

        mock_r = MagicMock()
        mock_redis.return_value = mock_r

        result = poll_condition_search()

        assert result["status"] == "ok"
        assert result["polled"] == 1
        mock_r.set.assert_called_once()
        key = mock_r.set.call_args[0][0]
        assert key == "condition:0001:results"

    @patch(_PATCH_REDIS)
    @patch(_PATCH_VAULT)
    @patch(_PATCH_DB)
    def test_missing_credentials_skipped(self, mock_db, mock_vault, mock_redis):
        """User without KIS credentials is skipped."""
        from app.tasks.periodic_tasks import poll_condition_search

        uid = uuid.uuid4()
        recipe = _make_condition_recipe(user_id=uid)

        db = MagicMock()
        mock_db.return_value = db
        db.query.return_value.filter.return_value.all.return_value = [recipe]
        db.query.return_value.filter.return_value.first.return_value = None

        mock_r = MagicMock()
        mock_redis.return_value = mock_r

        result = poll_condition_search()

        assert result["status"] == "ok"
        assert result["polled"] == 0
        mock_r.set.assert_not_called()

    @patch(_PATCH_ASYNCIO_RUN)
    @patch(_PATCH_KIS)
    @patch(_PATCH_REDIS)
    @patch(_PATCH_VAULT)
    @patch(_PATCH_DB)
    def test_condition_search_api_error(self, mock_db, mock_vault, mock_redis, mock_kis, mock_arun):
        """API error on one condition doesn't stop others."""
        from app.tasks.periodic_tasks import poll_condition_search

        uid = uuid.uuid4()
        r1 = _make_condition_recipe(user_id=uid, condition_id="0001")
        r2 = _make_condition_recipe(user_id=uid, condition_id="0002")
        cred = _make_credential(uid)

        db = MagicMock()
        mock_db.return_value = db
        db.query.return_value.filter.return_value.all.return_value = [r1, r2]
        db.query.return_value.filter.return_value.first.return_value = cred

        mock_vault.return_value.decrypt.side_effect = ["app_key", "app_secret"]

        mock_r = MagicMock()
        mock_redis.return_value = mock_r

        # First condition fails, second succeeds
        mock_arun.side_effect = [Exception("KIS API error"), [{"stock_code": "000660"}]]

        result = poll_condition_search()

        assert result["polled"] == 1
        assert result["errors"] == 1

    @patch(_PATCH_ASYNCIO_RUN)
    @patch(_PATCH_KIS)
    @patch(_PATCH_REDIS)
    @patch(_PATCH_VAULT)
    @patch(_PATCH_DB)
    def test_deduplicates_condition_ids(self, mock_db, mock_vault, mock_redis, mock_kis, mock_arun):
        """Same condition_id from multiple recipes is only polled once."""
        from app.tasks.periodic_tasks import poll_condition_search

        uid = uuid.uuid4()
        r1 = _make_condition_recipe(user_id=uid, condition_id="0001")
        r2 = _make_condition_recipe(user_id=uid, condition_id="0001")
        cred = _make_credential(uid)

        db = MagicMock()
        mock_db.return_value = db
        db.query.return_value.filter.return_value.all.return_value = [r1, r2]
        db.query.return_value.filter.return_value.first.return_value = cred

        mock_vault.return_value.decrypt.side_effect = ["app_key", "app_secret"]

        mock_r = MagicMock()
        mock_redis.return_value = mock_r
        mock_arun.return_value = [{"stock_code": "005930"}]

        result = poll_condition_search()

        assert result["polled"] == 1
        assert mock_arun.call_count == 1

    @patch(_PATCH_DB)
    def test_no_active_recipes_at_all(self, mock_db):
        """No active recipes at all → polled=0."""
        from app.tasks.periodic_tasks import poll_condition_search

        db = MagicMock()
        mock_db.return_value = db
        db.query.return_value.filter.return_value.all.return_value = []

        result = poll_condition_search()

        assert result["status"] == "ok"
        assert result["polled"] == 0
