import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


@pytest.fixture(autouse=True)
def _reset_security_state():
    """Reset rate limiter and account lockout between tests."""
    from app.core.rate_limit import get_rate_limiter
    from app.core.account_lockout import get_account_lockout
    get_rate_limiter().reset()
    get_account_lockout().reset()
    yield
    get_rate_limiter().reset()
    get_account_lockout().reset()


@pytest.fixture
def sample_ohlcv():
    """Generate sample OHLCV data for testing."""
    np.random.seed(42)
    dates = pd.date_range(start="2023-01-01", periods=500, freq="B")
    price = 50000 + np.cumsum(np.random.randn(500) * 500)
    price = np.maximum(price, 10000)

    df = pd.DataFrame({
        "open": price + np.random.randn(500) * 100,
        "high": price + abs(np.random.randn(500)) * 300,
        "low": price - abs(np.random.randn(500)) * 300,
        "close": price,
        "volume": np.random.randint(100000, 10000000, 500),
    }, index=dates)
    return df
