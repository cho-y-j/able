"""Tests for global/macro factor collection via Yahoo Finance."""

from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

from app.services.global_factor_collector import (
    fetch_global_factors,
    get_global_factor_catalog,
    GLOBAL_SYMBOLS,
)


class TestGlobalSymbols:
    def test_has_required_symbols(self):
        assert "kospi_index" in GLOBAL_SYMBOLS
        assert "vix_value" in GLOBAL_SYMBOLS
        assert "usdkrw_rate" in GLOBAL_SYMBOLS
        assert "sp500_index" in GLOBAL_SYMBOLS
        assert "nasdaq_index" in GLOBAL_SYMBOLS

    def test_all_have_symbol_and_description(self):
        for name, info in GLOBAL_SYMBOLS.items():
            assert "symbol" in info, f"{name} missing symbol"
            assert "description" in info, f"{name} missing description"

    def test_has_10_symbols(self):
        assert len(GLOBAL_SYMBOLS) == 10


class TestFetchGlobalFactors:
    def test_fetches_with_mock(self):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame({
            "Close": [2600.0, 2650.0],
            "Open": [2580.0, 2610.0],
            "High": [2620.0, 2660.0],
            "Low": [2570.0, 2600.0],
            "Volume": [1000000, 1100000],
        })

        mock_tickers = MagicMock()
        mock_tickers.tickers = {sym: mock_ticker for sym in
                                 [info["symbol"] for info in GLOBAL_SYMBOLS.values()]}

        with patch("app.services.global_factor_collector.yf") as mock_yf:
            mock_yf.Tickers.return_value = mock_tickers
            result = fetch_global_factors()

        assert isinstance(result, dict)
        assert len(result) > 0
        # Should have both value and change_pct
        assert "kospi_index" in result
        assert "kospi_index_change_pct" in result

    def test_handles_empty_history(self):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()

        mock_tickers = MagicMock()
        mock_tickers.tickers = {"^KS11": mock_ticker}

        with patch("app.services.global_factor_collector.yf") as mock_yf:
            mock_yf.Tickers.return_value = mock_tickers
            result = fetch_global_factors()
        assert isinstance(result, dict)

    def test_handles_yfinance_error(self):
        with patch("app.services.global_factor_collector.yf") as mock_yf:
            mock_yf.Tickers.side_effect = Exception("network error")
            result = fetch_global_factors()
        assert result == {}

    def test_change_pct_calculation(self):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame({
            "Close": [100.0, 105.0],
            "Open": [100.0, 101.0],
            "High": [102.0, 106.0],
            "Low": [99.0, 100.0],
            "Volume": [1000, 1200],
        })

        mock_tickers = MagicMock()
        # Only provide one symbol for simplicity
        all_syms = {info["symbol"]: mock_ticker for info in GLOBAL_SYMBOLS.values()}
        mock_tickers.tickers = all_syms

        with patch("app.services.global_factor_collector.yf") as mock_yf:
            mock_yf.Tickers.return_value = mock_tickers
            result = fetch_global_factors()

        # change_pct should be (105 - 100) / 100 * 100 = 5.0
        for key in result:
            if key.endswith("_change_pct"):
                assert abs(result[key] - 5.0) < 0.01
                break

    def test_no_nan_or_inf_values(self):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame({
            "Close": [100.0, 105.0],
            "Open": [100.0, 101.0],
            "High": [102.0, 106.0],
            "Low": [99.0, 100.0],
            "Volume": [1000, 1200],
        })

        mock_tickers = MagicMock()
        mock_tickers.tickers = {info["symbol"]: mock_ticker for info in GLOBAL_SYMBOLS.values()}

        with patch("app.services.global_factor_collector.yf") as mock_yf:
            mock_yf.Tickers.return_value = mock_tickers
            result = fetch_global_factors()

        for name, val in result.items():
            assert not np.isnan(val), f"{name} is NaN"
            assert not np.isinf(val), f"{name} is Inf"


class TestGetGlobalFactorCatalog:
    def test_returns_catalog(self):
        catalog = get_global_factor_catalog()
        assert len(catalog) == len(GLOBAL_SYMBOLS) * 2  # value + change_pct each

    def test_has_required_fields(self):
        catalog = get_global_factor_catalog()
        for item in catalog:
            assert "name" in item
            assert "category" in item
            assert item["category"] == "macro"
            assert "description" in item

    def test_includes_change_pct_entries(self):
        catalog = get_global_factor_catalog()
        names = [c["name"] for c in catalog]
        assert "kospi_index" in names
        assert "kospi_index_change_pct" in names
