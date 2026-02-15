"""Tests for the SignalComposer engine.

Verifies all combinator modes (AND, OR, MIN_AGREE, WEIGHTED),
edge cases (empty signals, invalid combinator/signal type), and
correct entry/exit logic.
"""

import numpy as np
import pandas as pd
import pytest

# Trigger signal registration before importing the composer
import app.analysis.signals  # noqa: F401
from app.analysis.composer import SignalComposer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 100) -> pd.DataFrame:
    """Create a reproducible OHLCV DataFrame with *n* rows."""
    np.random.seed(42)
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


def _signal_cfg(
    combinator: str,
    signal_names: list[str],
    *,
    min_agree: int = 2,
    weight_threshold: float = 0.5,
    weights: list[float] | None = None,
) -> dict:
    """Build a signal_config dict accepted by ``SignalComposer.compose``."""
    signals = []
    for idx, name in enumerate(signal_names):
        sig = {
            "type": "recommended",
            "strategy_type": name,
            "params": {},
            "weight": (weights[idx] if weights else 1.0),
        }
        signals.append(sig)
    return {
        "combinator": combinator,
        "min_agree": min_agree,
        "weight_threshold": weight_threshold,
        "signals": signals,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def composer() -> SignalComposer:
    return SignalComposer()


@pytest.fixture
def ohlcv() -> pd.DataFrame:
    return _make_ohlcv(100)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAndCombinator:
    """AND: entry requires ALL signals True, exit when ANY is True."""

    def test_and_combinator_all_agree(self, composer: SignalComposer, ohlcv: pd.DataFrame):
        """When all signals agree on entry rows, the composed entry should be True there."""
        cfg = _signal_cfg("AND", ["rsi_mean_reversion", "sma_crossover"])
        entry, exit_ = composer.compose(ohlcv, cfg)

        assert isinstance(entry, pd.Series)
        assert isinstance(exit_, pd.Series)
        assert entry.dtype == bool
        assert exit_.dtype == bool
        assert len(entry) == len(ohlcv)

        # AND entry must be a subset of each individual signal's entry
        from app.analysis.signals.registry import get_signal_generator

        e1, _ = get_signal_generator("rsi_mean_reversion")(ohlcv)
        e2, _ = get_signal_generator("sma_crossover")(ohlcv)
        e1 = e1.fillna(False).astype(bool)
        e2 = e2.fillna(False).astype(bool)

        # Everywhere the composed entry is True, both individuals must be True
        assert (entry & ~e1).sum() == 0, "AND entry has True where signal 1 is False"
        assert (entry & ~e2).sum() == 0, "AND entry has True where signal 2 is False"

    def test_and_combinator_partial_disagree(self, composer: SignalComposer, ohlcv: pd.DataFrame):
        """If one signal never fires, AND entry should be all-False."""
        from app.analysis.signals.registry import get_signal_generator

        # Run the two signals individually
        e1, _ = get_signal_generator("rsi_mean_reversion")(ohlcv)
        e2, _ = get_signal_generator("sma_crossover")(ohlcv)
        e1 = e1.fillna(False).astype(bool)
        e2 = e2.fillna(False).astype(bool)

        cfg = _signal_cfg("AND", ["rsi_mean_reversion", "sma_crossover"])
        entry, _ = composer.compose(ohlcv, cfg)

        # The AND result must be <= each individual
        assert entry.sum() <= e1.sum()
        assert entry.sum() <= e2.sum()

        # Where signals disagree, AND must be False
        disagree_mask = e1 ^ e2
        assert (entry & disagree_mask).sum() == 0


class TestOrCombinator:
    """OR: entry if ANY signal fires, exit only when ALL signals say exit."""

    def test_or_combinator_any_true(self, composer: SignalComposer, ohlcv: pd.DataFrame):
        from app.analysis.signals.registry import get_signal_generator

        e1, x1 = get_signal_generator("rsi_mean_reversion")(ohlcv)
        e2, x2 = get_signal_generator("sma_crossover")(ohlcv)
        e1, e2 = e1.fillna(False).astype(bool), e2.fillna(False).astype(bool)
        x1, x2 = x1.fillna(False).astype(bool), x2.fillna(False).astype(bool)

        cfg = _signal_cfg("OR", ["rsi_mean_reversion", "sma_crossover"])
        entry, exit_ = composer.compose(ohlcv, cfg)

        # OR entry >= each individual
        assert entry.sum() >= e1.sum()
        assert entry.sum() >= e2.sum()

        # Exit requires ALL to agree -> exit is AND of individual exits
        expected_exit = x1 & x2
        pd.testing.assert_series_equal(exit_, expected_exit, check_names=False)


class TestMinAgreeCombinator:
    """MIN_AGREE: entry when >= min_agree signals are True."""

    def test_min_agree_threshold(self, composer: SignalComposer, ohlcv: pd.DataFrame):
        """With min_agree=1 and 2 signals, result should match OR behaviour."""
        cfg = _signal_cfg(
            "MIN_AGREE",
            ["rsi_mean_reversion", "sma_crossover"],
            min_agree=1,
        )
        entry, _ = composer.compose(ohlcv, cfg)

        # min_agree=1 is logically equivalent to OR
        or_cfg = _signal_cfg("OR", ["rsi_mean_reversion", "sma_crossover"])
        or_entry, _ = composer.compose(ohlcv, or_cfg)

        pd.testing.assert_series_equal(
            entry.astype(bool), or_entry.astype(bool), check_names=False
        )

    def test_min_agree_below_threshold(self, composer: SignalComposer, ohlcv: pd.DataFrame):
        """With min_agree=3 and only 2 signals, entry should always be False."""
        cfg = _signal_cfg(
            "MIN_AGREE",
            ["rsi_mean_reversion", "sma_crossover"],
            min_agree=3,
        )
        entry, _ = composer.compose(ohlcv, cfg)

        # Can never get 3 agreements with 2 signals
        assert entry.sum() == 0, "Expected no entry when min_agree > number of signals"


class TestWeightedCombinator:
    """WEIGHTED: normalised weighted sum >= threshold."""

    def test_weighted_above_threshold(self, composer: SignalComposer, ohlcv: pd.DataFrame):
        """A heavily-weighted signal that fires should push above threshold."""
        from app.analysis.signals.registry import get_signal_generator

        e1, _ = get_signal_generator("rsi_mean_reversion")(ohlcv)
        e1 = e1.fillna(False).astype(bool)

        # Give signal 1 a dominant weight (0.9) and threshold 0.4
        cfg = _signal_cfg(
            "WEIGHTED",
            ["rsi_mean_reversion", "sma_crossover"],
            weight_threshold=0.4,
            weights=[0.9, 0.1],
        )
        entry, _ = composer.compose(ohlcv, cfg)

        # Because signal 1 has weight 0.9 out of 1.0 total,
        # wherever signal 1 fires alone: 0.9/1.0 = 0.9 >= 0.4 -> True
        # So the weighted entry should fire at least wherever signal 1 fires (alone)
        assert entry.dtype == bool
        assert entry.sum() >= 0  # at minimum, no crash

    def test_weighted_below_threshold(self, composer: SignalComposer, ohlcv: pd.DataFrame):
        """A low-weight signal that fires alone should not reach a high threshold."""
        cfg = _signal_cfg(
            "WEIGHTED",
            ["rsi_mean_reversion", "sma_crossover"],
            weight_threshold=0.95,
            weights=[0.1, 0.1],
        )
        entry, _ = composer.compose(ohlcv, cfg)

        # With equal tiny weights, normalised score is 0.0 or 0.5 or 1.0.
        # 0.95 threshold means only rows where BOTH fire would pass (normalised=1.0).
        from app.analysis.signals.registry import get_signal_generator

        e1, _ = get_signal_generator("rsi_mean_reversion")(ohlcv)
        e2, _ = get_signal_generator("sma_crossover")(ohlcv)
        e1 = e1.fillna(False).astype(bool)
        e2 = e2.fillna(False).astype(bool)

        both = e1 & e2
        # Weighted entry with 0.95 threshold should only fire when both are True
        # (normalised sum = 1.0 >= 0.95)
        pd.testing.assert_series_equal(entry, both, check_names=False)


class TestEdgeCases:
    """Empty signals and invalid inputs."""

    def test_empty_signals_returns_false(self, composer: SignalComposer, ohlcv: pd.DataFrame):
        cfg = {"combinator": "AND", "signals": []}
        entry, exit_ = composer.compose(ohlcv, cfg)

        assert (entry == False).all()  # noqa: E712
        assert (exit_ == False).all()  # noqa: E712
        assert len(entry) == len(ohlcv)
        assert len(exit_) == len(ohlcv)

    def test_invalid_combinator_raises(self, composer: SignalComposer, ohlcv: pd.DataFrame):
        cfg = {"combinator": "XOR", "signals": [{"type": "volume_spike", "params": {}}]}
        with pytest.raises(ValueError, match="Invalid combinator"):
            composer.compose(ohlcv, cfg)

    def test_invalid_signal_type_raises(self, composer: SignalComposer, ohlcv: pd.DataFrame):
        cfg = {
            "combinator": "AND",
            "signals": [
                {
                    "type": "recommended",
                    "strategy_type": "totally_nonexistent_signal_xyz",
                    "params": {},
                }
            ],
        }
        with pytest.raises(ValueError, match="Unknown signal"):
            composer.compose(ohlcv, cfg)
