"""Tests for RecipeExecutor service.

Tests cover:
- KIS credentials retrieval and error handling
- Signal evaluation and execution flow
- Position size calculation from risk_config
- Custom filter application
- Order persistence to DB
- Execution failure handling
"""

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch, AsyncMock, MagicMock, PropertyMock

import pytest
import pandas as pd
from cryptography.fernet import Fernet as _Fernet

# Set test environment before importing app
_test_fernet_key = _Fernet.generate_key().decode()
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-e2e")
os.environ.setdefault("ENCRYPTION_KEY", _test_fernet_key)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://able:able_secret@localhost:15432/able")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://able:able_secret@localhost:15432/able")
os.environ.setdefault("REDIS_URL", "redis://localhost:16379/1")


# ─── Helpers ──────────────────────────────────────────────────


def _make_recipe(user_id=None, stock_codes=None, risk_config=None, signal_config=None, custom_filters=None):
    """Create a mock TradingRecipe."""
    r = MagicMock()
    r.id = uuid.uuid4()
    r.user_id = user_id or uuid.uuid4()
    r.name = "Test Recipe"
    r.signal_config = signal_config or {
        "combinator": "AND",
        "signals": [
            {"type": "recommended", "strategy_type": "sma_crossover", "weight": 1.0}
        ],
    }
    r.custom_filters = custom_filters or {}
    r.stock_codes = stock_codes if stock_codes is not None else ["005930"]
    r.risk_config = risk_config or {"stop_loss": 3, "take_profit": 5, "position_size": 10}
    r.is_active = True
    return r


def _make_ohlcv_df(n=100, close_val=50000, volume_val=5_000_000):
    """Create a mock OHLCV DataFrame."""
    return pd.DataFrame({
        "open": [close_val] * n,
        "high": [close_val + 1000] * n,
        "low": [close_val - 1000] * n,
        "close": [close_val] * n,
        "volume": [volume_val] * n,
    }, index=pd.date_range("2025-01-01", periods=n))


def _make_exec_result(success=True, kis_order_id="KIS123", fill_price=50000,
                      execution_strategy="direct", error_message=None):
    """Create a mock ExecutionResult."""
    r = MagicMock()
    r.success = success
    r.kis_order_id = kis_order_id
    r.fill_price = fill_price
    r.execution_strategy = execution_strategy
    r.error_message = error_message
    r.slippage = None
    return r


# ─── Patches ──────────────────────────────────────────────────

_PATCH_VAULT = "app.services.recipe_executor.get_vault"
_PATCH_KIS = "app.services.recipe_executor.KISClient"
_PATCH_ENGINE = "app.services.recipe_executor.ExecutionEngine"
_PATCH_COMPOSER = "app.services.recipe_executor.SignalComposer"
_PATCH_FETCH = "app.services.recipe_executor.fetch_ohlcv_data"


# ─── Tests ────────────────────────────────────────────────────


class TestRecipeExecutorCredentials:
    """Test KIS credential retrieval."""

    @pytest.mark.asyncio
    async def test_no_credentials_raises_error(self):
        """Execute raises ValueError when no KIS credentials found."""
        from app.services.recipe_executor import RecipeExecutor

        db = AsyncMock()
        # No credential found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        executor = RecipeExecutor()
        recipe = _make_recipe()

        with pytest.raises(ValueError, match="KIS credentials not found"):
            await executor.execute(
                user_id=str(recipe.user_id),
                recipe=recipe,
                db=db,
            )

    @pytest.mark.asyncio
    @patch(_PATCH_VAULT)
    async def test_decrypt_failure_raises_error(self, mock_vault_fn):
        """Execute raises ValueError when credential decryption fails."""
        from app.services.recipe_executor import RecipeExecutor

        db = AsyncMock()
        cred = MagicMock()
        cred.encrypted_key = b"enc"
        cred.encrypted_secret = b"enc"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = cred
        db.execute = AsyncMock(return_value=mock_result)

        vault = MagicMock()
        vault.decrypt.side_effect = Exception("Decryption failed")
        mock_vault_fn.return_value = vault

        executor = RecipeExecutor()
        recipe = _make_recipe()

        with pytest.raises(ValueError, match="KIS credentials not found"):
            await executor.execute(
                user_id=str(recipe.user_id),
                recipe=recipe,
                db=db,
            )


class TestRecipeExecutorSignals:
    """Test signal evaluation and execution flow."""

    @pytest.mark.asyncio
    @patch(_PATCH_FETCH)
    @patch(_PATCH_COMPOSER)
    @patch(_PATCH_ENGINE)
    @patch(_PATCH_KIS)
    @patch(_PATCH_VAULT)
    async def test_no_entry_signal_returns_no_signal(
        self, mock_vault_fn, mock_kis_cls, mock_engine_cls, mock_composer_cls, mock_fetch
    ):
        """When signals indicate no entry, returns no_signal status."""
        from app.services.recipe_executor import RecipeExecutor

        # Setup mocks
        vault = MagicMock()
        vault.decrypt.return_value = "key"
        mock_vault_fn.return_value = vault

        kis = AsyncMock()
        kis.get_balance = AsyncMock(return_value={"total_balance": 10_000_000})
        mock_kis_cls.return_value = kis

        df = _make_ohlcv_df()
        mock_fetch.return_value = df

        # No entry, no exit
        entry = pd.Series([False] * 100)
        exit_ = pd.Series([False] * 100)
        mock_composer_cls.return_value.compose.return_value = (entry, exit_)

        db = AsyncMock()
        cred = MagicMock()
        cred.encrypted_key = b"enc"
        cred.encrypted_secret = b"enc"
        cred.account_number = "12345"
        cred.is_paper_trading = True
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = cred
        db.execute = AsyncMock(return_value=mock_result)

        executor = RecipeExecutor()
        recipe = _make_recipe(stock_codes=["005930"])

        results = await executor.execute(
            user_id=str(recipe.user_id),
            recipe=recipe,
            db=db,
        )

        assert len(results) == 1
        assert results[0]["status"] == "no_signal"
        mock_engine_cls.return_value.execute.assert_not_called()

    @pytest.mark.asyncio
    @patch(_PATCH_FETCH)
    @patch(_PATCH_COMPOSER)
    @patch(_PATCH_ENGINE)
    @patch(_PATCH_KIS)
    @patch(_PATCH_VAULT)
    async def test_entry_signal_places_buy_order(
        self, mock_vault_fn, mock_kis_cls, mock_engine_cls, mock_composer_cls, mock_fetch
    ):
        """When entry signal fires, a buy order is placed and persisted."""
        from app.services.recipe_executor import RecipeExecutor

        vault = MagicMock()
        vault.decrypt.return_value = "key"
        mock_vault_fn.return_value = vault

        kis = AsyncMock()
        kis.get_balance = AsyncMock(return_value={"total_balance": 10_000_000})
        mock_kis_cls.return_value = kis

        df = _make_ohlcv_df(close_val=50000)
        mock_fetch.return_value = df

        # Entry signal on last bar
        entry = pd.Series([False] * 99 + [True])
        exit_ = pd.Series([False] * 100)
        mock_composer_cls.return_value.compose.return_value = (entry, exit_)

        exec_result = _make_exec_result(success=True, kis_order_id="KIS001")
        mock_engine_cls.return_value.execute = AsyncMock(return_value=exec_result)

        db = AsyncMock()
        cred = MagicMock()
        cred.encrypted_key = b"enc"
        cred.encrypted_secret = b"enc"
        cred.account_number = "12345"
        cred.is_paper_trading = True
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = cred
        db.execute = AsyncMock(return_value=mock_result)
        db.add = MagicMock()
        db.flush = AsyncMock()

        executor = RecipeExecutor()
        recipe = _make_recipe(
            stock_codes=["005930"],
            risk_config={"stop_loss": 3, "take_profit": 5, "position_size": 10},
        )

        results = await executor.execute(
            user_id=str(recipe.user_id),
            recipe=recipe,
            db=db,
        )

        assert len(results) == 1
        assert results[0]["status"] == "submitted"
        assert results[0]["side"] == "buy"
        assert results[0]["kis_order_id"] == "KIS001"
        # Position size: 10% of 10M = 1M; 1M / 50000 = 20 shares
        assert results[0]["quantity"] == 20
        # Order persisted to DB
        db.add.assert_called_once()
        db.flush.assert_awaited()


class TestRecipeExecutorPositionSizing:
    """Test position size calculation."""

    @pytest.mark.asyncio
    @patch(_PATCH_FETCH)
    @patch(_PATCH_COMPOSER)
    @patch(_PATCH_ENGINE)
    @patch(_PATCH_KIS)
    @patch(_PATCH_VAULT)
    async def test_position_size_calculation(
        self, mock_vault_fn, mock_kis_cls, mock_engine_cls, mock_composer_cls, mock_fetch
    ):
        """Position size is calculated as (balance * position_pct) / price."""
        from app.services.recipe_executor import RecipeExecutor

        vault = MagicMock()
        vault.decrypt.return_value = "key"
        mock_vault_fn.return_value = vault

        kis = AsyncMock()
        kis.get_balance = AsyncMock(return_value={"total_balance": 50_000_000})
        mock_kis_cls.return_value = kis

        # Price 100,000 won
        df = _make_ohlcv_df(close_val=100_000)
        mock_fetch.return_value = df

        entry = pd.Series([False] * 99 + [True])
        exit_ = pd.Series([False] * 100)
        mock_composer_cls.return_value.compose.return_value = (entry, exit_)

        exec_result = _make_exec_result()
        mock_engine_cls.return_value.execute = AsyncMock(return_value=exec_result)

        db = AsyncMock()
        cred = MagicMock()
        cred.encrypted_key = b"enc"
        cred.encrypted_secret = b"enc"
        cred.account_number = "12345"
        cred.is_paper_trading = True
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = cred
        db.execute = AsyncMock(return_value=mock_result)
        db.add = MagicMock()
        db.flush = AsyncMock()

        executor = RecipeExecutor()
        # 5% of 50M = 2.5M; 2.5M / 100,000 = 25 shares
        recipe = _make_recipe(
            stock_codes=["035720"],
            risk_config={"stop_loss": 2, "take_profit": 4, "position_size": 5},
        )

        results = await executor.execute(
            user_id=str(recipe.user_id),
            recipe=recipe,
            db=db,
        )

        assert results[0]["quantity"] == 25


class TestRecipeExecutorCustomFilters:
    """Test custom filter application."""

    @pytest.mark.asyncio
    @patch(_PATCH_FETCH)
    @patch(_PATCH_COMPOSER)
    @patch(_PATCH_ENGINE)
    @patch(_PATCH_KIS)
    @patch(_PATCH_VAULT)
    async def test_volume_filter_blocks_entry(
        self, mock_vault_fn, mock_kis_cls, mock_engine_cls, mock_composer_cls, mock_fetch
    ):
        """Entry signal is blocked when volume is below volume_min filter."""
        from app.services.recipe_executor import RecipeExecutor

        vault = MagicMock()
        vault.decrypt.return_value = "key"
        mock_vault_fn.return_value = vault

        kis = AsyncMock()
        kis.get_balance = AsyncMock(return_value={"total_balance": 10_000_000})
        mock_kis_cls.return_value = kis

        # Low volume
        df = _make_ohlcv_df(volume_val=500)
        mock_fetch.return_value = df

        entry = pd.Series([False] * 99 + [True])
        exit_ = pd.Series([False] * 100)
        mock_composer_cls.return_value.compose.return_value = (entry, exit_)

        db = AsyncMock()
        cred = MagicMock()
        cred.encrypted_key = b"enc"
        cred.encrypted_secret = b"enc"
        cred.account_number = "12345"
        cred.is_paper_trading = True
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = cred
        db.execute = AsyncMock(return_value=mock_result)

        executor = RecipeExecutor()
        recipe = _make_recipe(
            stock_codes=["005930"],
            custom_filters={"volume_min": 1_000_000},
        )

        results = await executor.execute(
            user_id=str(recipe.user_id),
            recipe=recipe,
            db=db,
        )

        assert len(results) == 1
        assert results[0]["status"] == "no_signal"
        mock_engine_cls.return_value.execute.assert_not_called()

    @pytest.mark.asyncio
    @patch(_PATCH_FETCH)
    @patch(_PATCH_COMPOSER)
    @patch(_PATCH_ENGINE)
    @patch(_PATCH_KIS)
    @patch(_PATCH_VAULT)
    async def test_price_range_filter_blocks_entry(
        self, mock_vault_fn, mock_kis_cls, mock_engine_cls, mock_composer_cls, mock_fetch
    ):
        """Entry signal is blocked when price is outside price_range filter."""
        from app.services.recipe_executor import RecipeExecutor

        vault = MagicMock()
        vault.decrypt.return_value = "key"
        mock_vault_fn.return_value = vault

        kis = AsyncMock()
        kis.get_balance = AsyncMock(return_value={"total_balance": 10_000_000})
        mock_kis_cls.return_value = kis

        # Price 50000 is outside range [60000, 100000]
        df = _make_ohlcv_df(close_val=50000)
        mock_fetch.return_value = df

        entry = pd.Series([False] * 99 + [True])
        exit_ = pd.Series([False] * 100)
        mock_composer_cls.return_value.compose.return_value = (entry, exit_)

        db = AsyncMock()
        cred = MagicMock()
        cred.encrypted_key = b"enc"
        cred.encrypted_secret = b"enc"
        cred.account_number = "12345"
        cred.is_paper_trading = True
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = cred
        db.execute = AsyncMock(return_value=mock_result)

        executor = RecipeExecutor()
        recipe = _make_recipe(
            stock_codes=["005930"],
            custom_filters={"price_range": [60000, 100000]},
        )

        results = await executor.execute(
            user_id=str(recipe.user_id),
            recipe=recipe,
            db=db,
        )

        assert results[0]["status"] == "no_signal"


class TestRecipeExecutorFailures:
    """Test execution failure handling."""

    @pytest.mark.asyncio
    @patch(_PATCH_FETCH)
    @patch(_PATCH_COMPOSER)
    @patch(_PATCH_ENGINE)
    @patch(_PATCH_KIS)
    @patch(_PATCH_VAULT)
    async def test_ohlcv_fetch_failure_returns_error(
        self, mock_vault_fn, mock_kis_cls, mock_engine_cls, mock_composer_cls, mock_fetch
    ):
        """When OHLCV data fetch fails, returns error status."""
        from app.services.recipe_executor import RecipeExecutor

        vault = MagicMock()
        vault.decrypt.return_value = "key"
        mock_vault_fn.return_value = vault

        kis = AsyncMock()
        kis.get_balance = AsyncMock(return_value={"total_balance": 10_000_000})
        mock_kis_cls.return_value = kis

        mock_fetch.side_effect = Exception("Network error")

        db = AsyncMock()
        cred = MagicMock()
        cred.encrypted_key = b"enc"
        cred.encrypted_secret = b"enc"
        cred.account_number = "12345"
        cred.is_paper_trading = True
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = cred
        db.execute = AsyncMock(return_value=mock_result)

        executor = RecipeExecutor()
        recipe = _make_recipe(stock_codes=["005930"])

        results = await executor.execute(
            user_id=str(recipe.user_id),
            recipe=recipe,
            db=db,
        )

        assert len(results) == 1
        assert results[0]["status"] == "error"
        assert "Data fetch failed" in results[0]["error"]

    @pytest.mark.asyncio
    @patch(_PATCH_FETCH)
    @patch(_PATCH_COMPOSER)
    @patch(_PATCH_ENGINE)
    @patch(_PATCH_KIS)
    @patch(_PATCH_VAULT)
    async def test_insufficient_data_returns_skipped(
        self, mock_vault_fn, mock_kis_cls, mock_engine_cls, mock_composer_cls, mock_fetch
    ):
        """When OHLCV has < 60 rows, returns skipped status."""
        from app.services.recipe_executor import RecipeExecutor

        vault = MagicMock()
        vault.decrypt.return_value = "key"
        mock_vault_fn.return_value = vault

        kis = AsyncMock()
        kis.get_balance = AsyncMock(return_value={"total_balance": 10_000_000})
        mock_kis_cls.return_value = kis

        # Only 30 rows < 60 minimum
        mock_fetch.return_value = _make_ohlcv_df(n=30)

        db = AsyncMock()
        cred = MagicMock()
        cred.encrypted_key = b"enc"
        cred.encrypted_secret = b"enc"
        cred.account_number = "12345"
        cred.is_paper_trading = True
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = cred
        db.execute = AsyncMock(return_value=mock_result)

        executor = RecipeExecutor()
        recipe = _make_recipe(stock_codes=["005930"])

        results = await executor.execute(
            user_id=str(recipe.user_id),
            recipe=recipe,
            db=db,
        )

        assert results[0]["status"] == "skipped"
        assert "Insufficient data" in results[0]["error"]

    @pytest.mark.asyncio
    @patch(_PATCH_FETCH)
    @patch(_PATCH_COMPOSER)
    @patch(_PATCH_ENGINE)
    @patch(_PATCH_KIS)
    @patch(_PATCH_VAULT)
    async def test_execution_engine_failure_returns_failed(
        self, mock_vault_fn, mock_kis_cls, mock_engine_cls, mock_composer_cls, mock_fetch
    ):
        """When ExecutionEngine fails, order is saved as failed."""
        from app.services.recipe_executor import RecipeExecutor

        vault = MagicMock()
        vault.decrypt.return_value = "key"
        mock_vault_fn.return_value = vault

        kis = AsyncMock()
        kis.get_balance = AsyncMock(return_value={"total_balance": 10_000_000})
        mock_kis_cls.return_value = kis

        df = _make_ohlcv_df()
        mock_fetch.return_value = df

        entry = pd.Series([False] * 99 + [True])
        exit_ = pd.Series([False] * 100)
        mock_composer_cls.return_value.compose.return_value = (entry, exit_)

        exec_result = _make_exec_result(success=False, kis_order_id=None, error_message="API timeout")
        mock_engine_cls.return_value.execute = AsyncMock(return_value=exec_result)

        db = AsyncMock()
        cred = MagicMock()
        cred.encrypted_key = b"enc"
        cred.encrypted_secret = b"enc"
        cred.account_number = "12345"
        cred.is_paper_trading = True
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = cred
        db.execute = AsyncMock(return_value=mock_result)
        db.add = MagicMock()
        db.flush = AsyncMock()

        executor = RecipeExecutor()
        recipe = _make_recipe(stock_codes=["005930"])

        results = await executor.execute(
            user_id=str(recipe.user_id),
            recipe=recipe,
            db=db,
        )

        assert results[0]["status"] == "failed"
        # Order is still persisted to DB even on failure
        db.add.assert_called_once()

    @pytest.mark.asyncio
    @patch(_PATCH_FETCH)
    @patch(_PATCH_COMPOSER)
    @patch(_PATCH_ENGINE)
    @patch(_PATCH_KIS)
    @patch(_PATCH_VAULT)
    async def test_empty_stock_codes_returns_empty(
        self, mock_vault_fn, mock_kis_cls, mock_engine_cls, mock_composer_cls, mock_fetch
    ):
        """When recipe has no stock codes, returns empty list."""
        from app.services.recipe_executor import RecipeExecutor

        vault = MagicMock()
        vault.decrypt.return_value = "key"
        mock_vault_fn.return_value = vault

        kis = AsyncMock()
        kis.get_balance = AsyncMock(return_value={"total_balance": 10_000_000})
        mock_kis_cls.return_value = kis

        db = AsyncMock()
        cred = MagicMock()
        cred.encrypted_key = b"enc"
        cred.encrypted_secret = b"enc"
        cred.account_number = "12345"
        cred.is_paper_trading = True
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = cred
        db.execute = AsyncMock(return_value=mock_result)

        executor = RecipeExecutor()
        recipe = _make_recipe(stock_codes=[])

        results = await executor.execute(
            user_id=str(recipe.user_id),
            recipe=recipe,
            db=db,
        )

        assert results == []
