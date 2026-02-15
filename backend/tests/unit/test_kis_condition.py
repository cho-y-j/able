"""Tests for KIS condition search (조건검색) client methods and signal generator.

Tests cover:
- KISClient.get_condition_list() - list saved condition searches
- KISClient.run_condition_search() - execute a condition search
- kis_condition_signal() - convert condition search results to entry/exit signals
"""

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet as _Fernet

# Set test environment before importing app
_test_fernet_key = _Fernet.generate_key().decode()
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-e2e")
os.environ.setdefault("ENCRYPTION_KEY", _test_fernet_key)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://able:able_secret@localhost:15432/able")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://able:able_secret@localhost:15432/able")
os.environ.setdefault("REDIS_URL", "redis://localhost:16379/1")

from app.integrations.kis.client import KISClient
from app.analysis.signals.condition_search import kis_condition_signal


# ─── Helpers ──────────────────────────────────────────────────


def _make_kis_client():
    """Create a KISClient with dummy credentials for testing."""
    client = KISClient(
        app_key="test-app-key",
        app_secret="test-app-secret",
        account_number="50162896-01",
        is_paper=True,
    )
    return client


def _make_ohlcv_df(n_bars=50):
    """Create a sample OHLCV DataFrame for signal testing."""
    dates = pd.date_range("2024-01-01", periods=n_bars, freq="B")
    np.random.seed(42)
    close = 70000 + np.cumsum(np.random.randn(n_bars) * 500)
    return pd.DataFrame(
        {
            "open": close - np.random.rand(n_bars) * 200,
            "high": close + np.random.rand(n_bars) * 300,
            "low": close - np.random.rand(n_bars) * 300,
            "close": close,
            "volume": np.random.randint(100000, 5000000, n_bars),
        },
        index=dates,
    )


# ─── KISClient.get_condition_list Tests ──────────────────────


class TestGetConditionList:
    """Test KISClient.get_condition_list() method."""

    @pytest.mark.asyncio
    async def test_get_condition_list(self):
        """get_condition_list returns parsed list of conditions from KIS API."""
        client = _make_kis_client()

        mock_response = {
            "output2": [
                {"condition_seq": "0001", "condition_nm": "골든크로스"},
                {"condition_seq": "0002", "condition_nm": "거래량 급증"},
                {"condition_seq": "0003", "condition_nm": "MACD 상향돌파"},
            ]
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            result = await client.get_condition_list()

        assert len(result) == 3
        assert result[0] == {"condition_id": "0001", "condition_name": "골든크로스"}
        assert result[1] == {"condition_id": "0002", "condition_name": "거래량 급증"}
        assert result[2] == {"condition_id": "0003", "condition_name": "MACD 상향돌파"}

        mock_req.assert_awaited_once_with(
            "GET",
            "/uapi/domestic-stock/v1/quotations/psearch-title",
            "HHKST03900300",
            params={"user_id": ""},
        )

    @pytest.mark.asyncio
    async def test_get_condition_list_empty(self):
        """get_condition_list returns empty list when no conditions saved."""
        client = _make_kis_client()

        mock_response = {"output2": []}

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            result = await client.get_condition_list()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_condition_list_filters_empty_seq(self):
        """get_condition_list skips items with empty condition_seq."""
        client = _make_kis_client()

        mock_response = {
            "output2": [
                {"condition_seq": "0001", "condition_nm": "골든크로스"},
                {"condition_seq": "", "condition_nm": "빈 조건"},  # should be filtered
                {"condition_nm": "시퀀스 없음"},  # no condition_seq at all
            ]
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            result = await client.get_condition_list()

        assert len(result) == 1
        assert result[0]["condition_id"] == "0001"


# ─── KISClient.run_condition_search Tests ────────────────────


class TestRunConditionSearch:
    """Test KISClient.run_condition_search() method."""

    @pytest.mark.asyncio
    async def test_run_condition_search(self):
        """run_condition_search returns parsed list of matching stocks."""
        client = _make_kis_client()

        mock_response = {
            "output2": [
                {
                    "stck_shrn_iscd": "005930",
                    "hts_kor_isnm": "삼성전자",
                    "stck_prpr": "72000",
                    "prdy_ctrt": "1.50",
                    "acml_vol": "15000000",
                },
                {
                    "stck_shrn_iscd": "000660",
                    "hts_kor_isnm": "SK하이닉스",
                    "stck_prpr": "185000",
                    "prdy_ctrt": "2.30",
                    "acml_vol": "8000000",
                },
            ]
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            result = await client.run_condition_search("0001")

        assert len(result) == 2

        assert result[0] == {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "current_price": 72000.0,
            "change_percent": 1.50,
            "volume": 15000000,
        }
        assert result[1] == {
            "stock_code": "000660",
            "stock_name": "SK하이닉스",
            "current_price": 185000.0,
            "change_percent": 2.30,
            "volume": 8000000,
        }

        mock_req.assert_awaited_once_with(
            "GET",
            "/uapi/domestic-stock/v1/quotations/psearch-result",
            "HHKST03900400",
            params={"user_id": "", "seq": "0001"},
        )

    @pytest.mark.asyncio
    async def test_run_condition_search_empty(self):
        """run_condition_search returns empty list when no stocks match."""
        client = _make_kis_client()

        mock_response = {"output2": []}

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            result = await client.run_condition_search("0099")

        assert result == []

    @pytest.mark.asyncio
    async def test_run_condition_search_filters_empty_code(self):
        """run_condition_search skips items with empty stock code."""
        client = _make_kis_client()

        mock_response = {
            "output2": [
                {
                    "stck_shrn_iscd": "005930",
                    "hts_kor_isnm": "삼성전자",
                    "stck_prpr": "72000",
                    "prdy_ctrt": "1.50",
                    "acml_vol": "15000000",
                },
                {
                    "stck_shrn_iscd": "",
                    "hts_kor_isnm": "빈 종목",
                    "stck_prpr": "0",
                    "prdy_ctrt": "0",
                    "acml_vol": "0",
                },
            ]
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response

            result = await client.run_condition_search("0001")

        assert len(result) == 1
        assert result[0]["stock_code"] == "005930"


# ─── kis_condition_signal Tests ──────────────────────────────


class TestKisConditionSignal:
    """Test kis_condition_signal() signal generator."""

    def test_kis_condition_signal_matching(self):
        """Signal generates entry on last bar when stock_code is in matching_stocks."""
        df = _make_ohlcv_df(30)

        entry, exit_ = kis_condition_signal(
            df,
            matching_stocks=["005930", "000660", "035720"],
            stock_code="005930",
        )

        assert isinstance(entry, pd.Series)
        assert isinstance(exit_, pd.Series)
        assert len(entry) == 30
        assert len(exit_) == 30

        # Only the last bar should have entry=True
        assert entry.iloc[-1] is True or entry.iloc[-1] == True  # noqa: E712
        assert entry.iloc[:-1].sum() == 0  # All other bars are False

        # No exit signals
        assert exit_.sum() == 0

    def test_kis_condition_signal_not_matching(self):
        """Signal generates no entry when stock_code is NOT in matching_stocks."""
        df = _make_ohlcv_df(30)

        entry, exit_ = kis_condition_signal(
            df,
            matching_stocks=["000660", "035720"],
            stock_code="005930",
        )

        assert entry.sum() == 0
        assert exit_.sum() == 0

    def test_kis_condition_signal_empty_matching(self):
        """Signal generates no entry when matching_stocks is None or empty."""
        df = _make_ohlcv_df(20)

        # None matching_stocks
        entry, exit_ = kis_condition_signal(
            df,
            matching_stocks=None,
            stock_code="005930",
        )
        assert entry.sum() == 0
        assert exit_.sum() == 0

        # Empty matching_stocks
        entry2, exit_2 = kis_condition_signal(
            df,
            matching_stocks=[],
            stock_code="005930",
        )
        assert entry2.sum() == 0
        assert exit_2.sum() == 0

    def test_kis_condition_signal_no_stock_code(self):
        """Signal generates no entry when stock_code is None."""
        df = _make_ohlcv_df(20)

        entry, exit_ = kis_condition_signal(
            df,
            matching_stocks=["005930"],
            stock_code=None,
        )
        assert entry.sum() == 0
        assert exit_.sum() == 0

    def test_kis_condition_signal_single_bar(self):
        """Signal works correctly with a single-bar DataFrame."""
        df = _make_ohlcv_df(1)

        entry, exit_ = kis_condition_signal(
            df,
            matching_stocks=["005930"],
            stock_code="005930",
        )

        assert len(entry) == 1
        assert entry.iloc[0] is True or entry.iloc[0] == True  # noqa: E712
        assert exit_.sum() == 0

    def test_kis_condition_signal_empty_df(self):
        """Signal returns empty series for an empty DataFrame."""
        df = pd.DataFrame(
            {"open": [], "high": [], "low": [], "close": [], "volume": []},
            index=pd.DatetimeIndex([]),
        )

        entry, exit_ = kis_condition_signal(
            df,
            matching_stocks=["005930"],
            stock_code="005930",
        )

        assert len(entry) == 0
        assert len(exit_) == 0

    def test_kis_condition_signal_returns_correct_index(self):
        """Signal series index matches the input DataFrame index."""
        df = _make_ohlcv_df(10)

        entry, exit_ = kis_condition_signal(
            df,
            matching_stocks=["005930"],
            stock_code="005930",
        )

        assert entry.index.equals(df.index)
        assert exit_.index.equals(df.index)
