"""Tests for data provider abstraction and factory."""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from app.integrations.data.base import DataProvider
from app.integrations.data.factory import get_data_provider
from app.integrations.data.yahoo_provider import YahooDataProvider, krx_to_yahoo_ticker
from app.integrations.data.kis_provider import KISDataProvider


class TestKrxToYahooTicker:
    def test_kospi_stock(self):
        assert krx_to_yahoo_ticker("005930") == "005930.KS"

    def test_kosdaq_stock_prefix_2(self):
        assert krx_to_yahoo_ticker("247540") == "247540.KQ"

    def test_kosdaq_stock_prefix_3(self):
        assert krx_to_yahoo_ticker("373220") == "373220.KQ"

    def test_already_has_suffix(self):
        assert krx_to_yahoo_ticker("005930.KS") == "005930.KS"
        assert krx_to_yahoo_ticker("247540.KQ") == "247540.KQ"

    def test_us_ticker_passthrough(self):
        assert krx_to_yahoo_ticker("AAPL") == "AAPL"
        assert krx_to_yahoo_ticker("TSLA") == "TSLA"

    def test_kospi_prefix_0(self):
        assert krx_to_yahoo_ticker("000660") == "000660.KS"  # SK Hynix

    def test_kospi_prefix_1(self):
        assert krx_to_yahoo_ticker("105560") == "105560.KS"  # KB Financial


class TestFactory:
    def test_yahoo_provider(self):
        provider = get_data_provider("yahoo")
        assert isinstance(provider, YahooDataProvider)
        assert provider.name == "yahoo"
        assert not provider.requires_credentials

    def test_kis_provider(self):
        provider = get_data_provider(
            "kis",
            app_key="test_key",
            app_secret="test_secret",
            account_number="12345678",
        )
        assert isinstance(provider, KISDataProvider)
        assert provider.name == "kis"
        assert provider.requires_credentials

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown data source"):
            get_data_provider("bloomberg")


class TestYahooDataProvider:
    def test_is_data_provider(self):
        provider = YahooDataProvider()
        assert isinstance(provider, DataProvider)

    def test_name(self):
        assert YahooDataProvider().name == "yahoo"

    def test_no_credentials_required(self):
        assert not YahooDataProvider().requires_credentials

    def test_get_ohlcv_returns_dataframe(self):
        import numpy as np
        import app.integrations.data.yahoo_provider as yp

        mock_yf = MagicMock()
        dates = pd.date_range("2024-01-01", periods=10, freq="B")
        mock_df = pd.DataFrame({
            "Open": np.random.rand(10) * 100 + 50000,
            "High": np.random.rand(10) * 100 + 50500,
            "Low": np.random.rand(10) * 100 + 49500,
            "Close": np.random.rand(10) * 100 + 50000,
            "Volume": np.random.randint(100000, 1000000, 10),
        }, index=dates)
        mock_yf.download.return_value = mock_df

        original_yf = yp.yf
        yp.yf = mock_yf
        try:
            provider = YahooDataProvider()
            df = provider.get_ohlcv("005930", "20240101", "20240115")

            assert isinstance(df, pd.DataFrame)
            assert len(df) == 10
            for col in ["open", "high", "low", "close", "volume"]:
                assert col in df.columns
        finally:
            yp.yf = original_yf

    def test_get_ohlcv_empty_data(self):
        import app.integrations.data.yahoo_provider as yp

        mock_yf = MagicMock()
        mock_yf.download.return_value = pd.DataFrame()

        original_yf = yp.yf
        yp.yf = mock_yf
        try:
            provider = YahooDataProvider()
            df = provider.get_ohlcv("INVALID", "20240101", "20240115")
            assert df.empty
        finally:
            yp.yf = original_yf

    def test_date_normalization(self):
        import app.integrations.data.yahoo_provider as yp

        mock_yf = MagicMock()
        mock_yf.download.return_value = pd.DataFrame()

        original_yf = yp.yf
        yp.yf = mock_yf
        try:
            provider = YahooDataProvider()
            provider.get_ohlcv("005930", "20240101", "20240115")
            call_args = mock_yf.download.call_args
            assert call_args.kwargs["start"] == "2024-01-01"
            assert call_args.kwargs["end"] == "2024-01-15"
        finally:
            yp.yf = original_yf

    def test_get_price(self):
        import app.integrations.data.yahoo_provider as yp

        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_fast_info = MagicMock()
        mock_fast_info.last_price = 72500.0
        mock_fast_info.last_volume = 5000000
        mock_fast_info.day_high = 73000.0
        mock_fast_info.day_low = 72000.0
        mock_fast_info.open = 72200.0
        mock_ticker.fast_info = mock_fast_info
        mock_yf.Ticker.return_value = mock_ticker

        original_yf = yp.yf
        yp.yf = mock_yf
        try:
            provider = YahooDataProvider()
            price = provider.get_price("005930")

            assert price["stock_code"] == "005930"
            assert price["current_price"] == 72500.0
            assert price["volume"] == 5000000
        finally:
            yp.yf = original_yf


class TestKISDataProvider:
    def test_is_data_provider(self):
        provider = KISDataProvider("key", "secret")
        assert isinstance(provider, DataProvider)

    def test_name(self):
        assert KISDataProvider("key", "secret").name == "kis"

    def test_credentials_required(self):
        assert KISDataProvider("key", "secret").requires_credentials

    def test_paper_vs_real_url(self):
        from app.integrations.kis.constants import PAPER_BASE_URL, REAL_BASE_URL
        paper = KISDataProvider("key", "secret", is_paper=True)
        real = KISDataProvider("key", "secret", is_paper=False)
        assert paper.base_url == PAPER_BASE_URL
        assert real.base_url == REAL_BASE_URL


class TestDataProviderABC:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            DataProvider()

    def test_concrete_must_implement_methods(self):
        class IncompleteProvider(DataProvider):
            pass
        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_complete_provider_works(self):
        class TestProvider(DataProvider):
            def get_ohlcv(self, stock_code, start_date, end_date, interval="1d"):
                return pd.DataFrame()
            def get_price(self, stock_code):
                return {}
            @property
            def name(self):
                return "test"
        p = TestProvider()
        assert p.name == "test"
        assert p.requires_credentials is True  # default
