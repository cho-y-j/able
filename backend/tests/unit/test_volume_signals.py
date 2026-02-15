"""Tests for the volume-based signal generators.

Covers ``volume_spike``, ``vwap_deviation``, and ``volume_breakout`` signal
generators registered in ``app.analysis.signals.volume_signals``.
"""

import numpy as np
import pandas as pd
import pytest

# Ensure all signals are registered before tests run
import app.analysis.signals  # noqa: F401
from app.analysis.signals.registry import get_signal_generator, list_signal_generators


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 100, *, seed: int = 42) -> pd.DataFrame:
    """Create a reproducible OHLCV DataFrame with *n* rows."""
    np.random.seed(seed)
    price = 50_000 + np.cumsum(np.random.randn(n) * 500)
    price = np.maximum(price, 10_000)
    return pd.DataFrame(
        {
            "open": price + np.random.randn(n) * 100,
            "high": price + np.abs(np.random.randn(n)) * 300,
            "low": price - np.abs(np.random.randn(n)) * 300,
            "close": price,
            "volume": np.random.randint(100_000, 10_000_000, n),
        }
    )


def _make_volume_spike_df() -> pd.DataFrame:
    """Create a DataFrame where a clear volume spike + bullish candle exists.

    Rows 0-59: normal volume, alternating candles.
    Row 60: volume = 10x average, bullish candle  -> should trigger entry.
    Rows 61-79: normal volume again                -> should trigger exit.
    """
    np.random.seed(99)
    n = 80
    base_volume = 1_000_000

    close = np.full(n, 50_000.0)
    open_ = np.full(n, 50_000.0)
    high = np.full(n, 50_300.0)
    low = np.full(n, 49_700.0)
    volume = np.full(n, base_volume)

    # Rows 0-59: slight random noise, roughly balanced candles
    for i in range(60):
        close[i] = 50_000 + np.random.randn() * 50
        open_[i] = 50_000 + np.random.randn() * 50
        high[i] = max(close[i], open_[i]) + abs(np.random.randn()) * 100
        low[i] = min(close[i], open_[i]) - abs(np.random.randn()) * 100
        volume[i] = base_volume + int(np.random.randn() * 100_000)

    # Row 60: big spike + bullish
    open_[60] = 50_000
    close[60] = 51_000  # bullish
    high[60] = 51_200
    low[60] = 49_800
    volume[60] = base_volume * 15  # huge spike (RVOL >> 2.0)

    # Rows 61-79: normal volume, neutral candles
    for i in range(61, n):
        close[i] = 50_500 + np.random.randn() * 30
        open_[i] = 50_500 + np.random.randn() * 30
        high[i] = max(close[i], open_[i]) + 50
        low[i] = min(close[i], open_[i]) - 50
        volume[i] = base_volume + int(np.random.randn() * 50_000)

    return pd.DataFrame(
        {"open": open_, "close": close, "high": high, "low": low, "volume": volume}
    )


def _make_bearish_spike_df() -> pd.DataFrame:
    """Volume spike + bearish candle -> should NOT trigger volume_spike entry."""
    np.random.seed(77)
    n = 80
    base_volume = 1_000_000

    close = np.full(n, 50_000.0)
    open_ = np.full(n, 50_000.0)
    high = np.full(n, 50_300.0)
    low = np.full(n, 49_700.0)
    volume = np.full(n, base_volume)

    for i in range(60):
        close[i] = 50_000 + np.random.randn() * 50
        open_[i] = 50_000 + np.random.randn() * 50
        high[i] = max(close[i], open_[i]) + abs(np.random.randn()) * 100
        low[i] = min(close[i], open_[i]) - abs(np.random.randn()) * 100
        volume[i] = base_volume + int(np.random.randn() * 100_000)

    # Row 60: volume spike but BEARISH candle (close < open)
    open_[60] = 51_000
    close[60] = 49_000  # bearish
    high[60] = 51_200
    low[60] = 48_800
    volume[60] = base_volume * 15

    for i in range(61, n):
        close[i] = 49_500 + np.random.randn() * 30
        open_[i] = 49_500 + np.random.randn() * 30
        high[i] = max(close[i], open_[i]) + 50
        low[i] = min(close[i], open_[i]) - 50
        volume[i] = base_volume + int(np.random.randn() * 50_000)

    return pd.DataFrame(
        {"open": open_, "close": close, "high": high, "low": low, "volume": volume}
    )


def _make_breakout_df() -> pd.DataFrame:
    """DataFrame where a clear price breakout + volume spike occurs.

    Rows 0-59: stable price around 50000, normal volume.
    Row 60: price breaks above the 20-day high AND volume spikes.
    Rows 61-79: price drops below the 20-day low -> triggers exit.
    """
    np.random.seed(88)
    n = 80
    base_volume = 1_000_000

    close = np.full(n, 50_000.0)
    open_ = np.full(n, 50_000.0)
    high = np.full(n, 50_200.0)
    low = np.full(n, 49_800.0)
    volume = np.full(n, base_volume)

    # Rows 0-59: stable range
    for i in range(60):
        close[i] = 50_000 + np.random.randn() * 30
        open_[i] = 50_000 + np.random.randn() * 30
        high[i] = max(close[i], open_[i]) + abs(np.random.randn()) * 50
        low[i] = min(close[i], open_[i]) - abs(np.random.randn()) * 50
        volume[i] = base_volume + int(np.random.randn() * 100_000)

    # Row 60: breakout - price jumps far above the range + volume spikes
    close[60] = 52_000
    open_[60] = 50_100
    high[60] = 52_200
    low[60] = 50_000
    volume[60] = base_volume * 15

    # Rows 61-69: stay high
    for i in range(61, 70):
        close[i] = 52_000 + np.random.randn() * 20
        open_[i] = 52_000 + np.random.randn() * 20
        high[i] = max(close[i], open_[i]) + 30
        low[i] = min(close[i], open_[i]) - 30
        volume[i] = base_volume + int(np.random.randn() * 50_000)

    # Rows 70-79: crash well below the 20-day low -> exit
    for i in range(70, n):
        close[i] = 48_000 + np.random.randn() * 20
        open_[i] = 48_000 + np.random.randn() * 20
        high[i] = max(close[i], open_[i]) + 30
        low[i] = min(close[i], open_[i]) - 30
        volume[i] = base_volume + int(np.random.randn() * 50_000)

    return pd.DataFrame(
        {"open": open_, "close": close, "high": high, "low": low, "volume": volume}
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ohlcv() -> pd.DataFrame:
    return _make_ohlcv(100)


# ---------------------------------------------------------------------------
# volume_spike tests
# ---------------------------------------------------------------------------

class TestVolumeSpike:

    def test_volume_spike_entry_on_rvol_and_bullish(self):
        """Entry fires when RVOL > threshold AND candle is bullish."""
        df = _make_volume_spike_df()
        gen = get_signal_generator("volume_spike")
        entry, exit_ = gen(df, lookback=50, rvol_threshold=2.0)

        assert entry.dtype == bool
        assert exit_.dtype == bool
        assert len(entry) == len(df)

        # Row 60 has a massive volume spike + bullish candle -> must be True
        assert entry.iloc[60], "Expected entry on row 60 (bullish volume spike)"

    def test_volume_spike_no_entry_on_bearish(self):
        """Entry must NOT fire on a volume spike if the candle is bearish."""
        df = _make_bearish_spike_df()
        gen = get_signal_generator("volume_spike")
        entry, _ = gen(df, lookback=50, rvol_threshold=2.0)

        # Row 60 has spike volume but bearish candle -> must NOT be True
        assert not entry.iloc[60], "Entry should not fire on bearish candle even with volume spike"

    def test_volume_spike_exit_on_normal_volume(self):
        """Exit fires when RVOL drops below 1.0 (normal volume)."""
        df = _make_volume_spike_df()
        gen = get_signal_generator("volume_spike")
        _, exit_ = gen(df, lookback=50, rvol_threshold=2.0)

        # After the spike, rows 61+ return to normal volume -> RVOL < 1.0
        # At least some rows in 61-79 should have exit=True
        post_spike_exits = exit_.iloc[61:].sum()
        assert post_spike_exits > 0, "Expected exit signals after volume normalises"


# ---------------------------------------------------------------------------
# vwap_deviation tests
# ---------------------------------------------------------------------------

class TestVwapDeviation:

    def test_vwap_deviation_returns_series(self, ohlcv: pd.DataFrame):
        """Generator returns two pd.Series of correct length."""
        gen = get_signal_generator("vwap_deviation")
        entry, exit_ = gen(ohlcv)

        assert isinstance(entry, pd.Series)
        assert isinstance(exit_, pd.Series)
        assert len(entry) == len(ohlcv)
        assert len(exit_) == len(ohlcv)

    def test_vwap_deviation_entry_exit_are_boolean(self, ohlcv: pd.DataFrame):
        """Both returned Series must have boolean dtype after fillna."""
        gen = get_signal_generator("vwap_deviation")
        entry, exit_ = gen(ohlcv)

        assert entry.dtype == bool, f"entry dtype is {entry.dtype}, expected bool"
        assert exit_.dtype == bool, f"exit dtype is {exit_.dtype}, expected bool"


# ---------------------------------------------------------------------------
# volume_breakout tests
# ---------------------------------------------------------------------------

class TestVolumeBreakout:

    def test_volume_breakout_entry_on_price_and_volume(self):
        """Entry fires when price breaks N-day high AND volume spikes."""
        df = _make_breakout_df()
        gen = get_signal_generator("volume_breakout")
        entry, _ = gen(df, price_lookback=20, rvol_threshold=2.0, volume_lookback=50)

        assert entry.dtype == bool
        assert len(entry) == len(df)

        # Row 60 has price breakout + volume spike -> should trigger entry
        assert entry.iloc[60], "Expected entry on row 60 (price breakout + volume spike)"

    def test_volume_breakout_exit_below_low(self):
        """Exit fires when price drops below N-day low."""
        df = _make_breakout_df()
        gen = get_signal_generator("volume_breakout")
        _, exit_ = gen(df, price_lookback=20, rvol_threshold=2.0, volume_lookback=50)

        assert exit_.dtype == bool

        # Rows 70-79 have price crashed to 48000, well below the 20-day low -> exit
        post_crash_exits = exit_.iloc[70:].sum()
        assert post_crash_exits > 0, "Expected exit signals after price crashes below N-day low"


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

class TestVolumeSignalsRegistry:

    def test_signals_registered_in_registry(self):
        """All three volume signals are discoverable in the global registry."""
        registered = list_signal_generators()

        assert "volume_spike" in registered
        assert "vwap_deviation" in registered
        assert "volume_breakout" in registered

        # Each should be callable
        for name in ("volume_spike", "vwap_deviation", "volume_breakout"):
            gen = get_signal_generator(name)
            assert callable(gen), f"{name} generator is not callable"
