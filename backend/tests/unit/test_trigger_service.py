"""Tests for the real-time TriggerService (tick buffering + recipe evaluation)."""

import os
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-e2e")
os.environ.setdefault("ENCRYPTION_KEY", "test" * 8 + "==")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://able:able_secret@localhost:15432/able")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://able:able_secret@localhost:15432/able")
os.environ.setdefault("REDIS_URL", "redis://localhost:16379/1")

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

from app.services.trigger_service import TriggerService


# ── Helpers ──────────────────────────────────────────────


def _make_tick(
    current_price=72000,
    open_price=71000,
    high=72500,
    low=70500,
    volume=100000,
):
    """Create a realistic tick dict."""
    return {
        "current_price": current_price,
        "open": open_price,
        "high": high,
        "low": low,
        "volume": volume,
    }


def _fill_buffer(service, stock_code="005930", n=50, base_price=72000):
    """Add n ticks with slightly varying prices."""
    for i in range(n):
        tick = _make_tick(
            current_price=base_price + i * 10,
            open_price=base_price,
            high=base_price + i * 10 + 100,
            low=base_price - 100,
            volume=100000 + i * 1000,
        )
        service.add_tick(stock_code, tick)


# ── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def svc():
    """Fresh TriggerService instance."""
    return TriggerService()


# ── Tick Buffer ──────────────────────────────────────────


class TestTickBuffer:
    def test_add_tick_and_retrieve(self, svc):
        tick = _make_tick()
        svc.add_tick("005930", tick)

        assert "005930" in svc._tick_buffer
        assert len(svc._tick_buffer["005930"]) == 1
        assert svc._tick_buffer["005930"][0]["current_price"] == 72000

    def test_buffer_max_size_cap(self, svc):
        """Buffer should be trimmed to _buffer_max_size (500)."""
        for i in range(600):
            svc.add_tick("005930", _make_tick(current_price=70000 + i))

        assert len(svc._tick_buffer["005930"]) == svc._buffer_max_size
        # Oldest tick should have been dropped; newest retained
        assert svc._tick_buffer["005930"][-1]["current_price"] == 70000 + 599
        assert svc._tick_buffer["005930"][0]["current_price"] == 70000 + 100

    def test_clear_buffer_single_stock(self, svc):
        _fill_buffer(svc, "005930")
        _fill_buffer(svc, "000660")

        svc.clear_buffer("005930")

        assert "005930" not in svc._tick_buffer
        assert len(svc._tick_buffer["000660"]) == 50

    def test_clear_buffer_all(self, svc):
        _fill_buffer(svc, "005930")
        _fill_buffer(svc, "000660")

        svc.clear_buffer()

        assert len(svc._tick_buffer) == 0


# ── get_recent_df ────────────────────────────────────────


class TestGetRecentDf:
    def test_get_recent_df_insufficient_data(self, svc):
        """Fewer than 10 ticks should return None."""
        for i in range(9):
            svc.add_tick("005930", _make_tick())

        assert svc.get_recent_df("005930") is None

    def test_get_recent_df_no_data(self, svc):
        """Non-existent stock should return None."""
        assert svc.get_recent_df("999999") is None

    def test_get_recent_df_with_current_price_mapping(self, svc):
        """Ticks using 'current_price' should be mapped to OHLCV columns."""
        _fill_buffer(svc, "005930", n=15)

        df = svc.get_recent_df("005930")
        assert df is not None
        assert isinstance(df, pd.DataFrame)
        assert "close" in df.columns
        assert "open" in df.columns
        assert "high" in df.columns
        assert "low" in df.columns
        assert "volume" in df.columns
        assert len(df) == 15

    def test_get_recent_df_with_native_ohlcv(self, svc):
        """If ticks already have OHLCV columns, no mapping is needed."""
        for i in range(12):
            svc.add_tick("005930", {
                "open": 71000,
                "high": 72500,
                "low": 70500,
                "close": 72000 + i,
                "volume": 100000,
            })

        df = svc.get_recent_df("005930")
        assert df is not None
        assert df.iloc[-1]["close"] == 72000 + 11


# ── evaluate_recipe ──────────────────────────────────────


class TestEvaluateRecipe:
    def test_evaluate_recipe_insufficient_data(self, svc):
        """With no buffered data the result should report insufficient_data."""
        result = svc.evaluate_recipe(
            "005930",
            signal_config={"combinator": "AND", "signals": []},
        )

        assert result["should_enter"] is False
        assert result["should_exit"] is False
        assert result["signal_details"]["reason"] == "insufficient_data"

    def test_evaluate_recipe_with_signals(self, svc):
        """Mock SignalComposer.compose to verify evaluate_recipe wiring."""
        _fill_buffer(svc, "005930", n=20)

        entry_series = pd.Series([False] * 19 + [True])
        exit_series = pd.Series([False] * 20)

        with patch.object(svc.composer, "compose", return_value=(entry_series, exit_series)):
            result = svc.evaluate_recipe(
                "005930",
                signal_config={"combinator": "AND", "signals": [{"type": "sma_crossover"}]},
            )

        assert result["should_enter"] is True
        assert result["should_exit"] is False
        assert "entry_signals_last_5" in result["signal_details"]

    def test_evaluate_recipe_exit_signal(self, svc):
        """Verify exit signal detection."""
        _fill_buffer(svc, "005930", n=20)

        entry_series = pd.Series([False] * 20)
        exit_series = pd.Series([False] * 19 + [True])

        with patch.object(svc.composer, "compose", return_value=(entry_series, exit_series)):
            result = svc.evaluate_recipe("005930", signal_config={"combinator": "OR", "signals": []})

        assert result["should_enter"] is False
        assert result["should_exit"] is True

    def test_evaluate_recipe_composer_exception(self, svc):
        """If SignalComposer.compose raises, result should contain the error."""
        _fill_buffer(svc, "005930", n=20)

        with patch.object(svc.composer, "compose", side_effect=ValueError("bad config")):
            result = svc.evaluate_recipe("005930", signal_config={"combinator": "AND", "signals": []})

        assert result["should_enter"] is False
        assert result["should_exit"] is False
        assert "error" in result["signal_details"]
        assert "bad config" in result["signal_details"]["error"]
