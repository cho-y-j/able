"""Signal composer for combining multiple signal generators with AND/OR/MIN_AGREE/WEIGHTED logic."""

import pandas as pd
import numpy as np

from app.analysis.signals.registry import get_signal_generator


class SignalComposer:
    """Compose multiple signal generators into combined entry/exit signals."""

    VALID_COMBINATORS = {"AND", "OR", "MIN_AGREE", "WEIGHTED"}

    def compose(
        self, df: pd.DataFrame, signal_config: dict
    ) -> tuple[pd.Series, pd.Series]:
        """
        Run each signal generator and combine results.

        Args:
            df: OHLCV DataFrame
            signal_config: {
                "combinator": "AND"|"OR"|"MIN_AGREE"|"WEIGHTED",
                "min_agree": 2,
                "weight_threshold": 0.5,
                "signals": [
                    {"type": "recommended", "strategy_type": "macd_crossover", "params": {...}, "weight": 1.0},
                    {"type": "volume_spike", "params": {...}, "weight": 0.6},
                    ...
                ]
            }

        Returns:
            (combined_entry, combined_exit) boolean Series tuple
        """
        signals = signal_config.get("signals", [])
        combinator = signal_config.get("combinator", "AND")

        if combinator not in self.VALID_COMBINATORS:
            raise ValueError(
                f"Invalid combinator: {combinator}. Must be one of {self.VALID_COMBINATORS}"
            )

        if not signals:
            empty = pd.Series(False, index=df.index)
            return empty, empty

        entries: list[pd.Series] = []
        exits: list[pd.Series] = []
        weights: list[float] = []

        for sig in signals:
            sig_type = sig.get("type", "recommended")
            params = sig.get("params", {})
            weight = sig.get("weight", 1.0)

            # Resolve signal generator name
            if sig_type == "recommended":
                gen_name = sig.get("strategy_type", "")
            else:
                gen_name = sig_type

            generator = get_signal_generator(gen_name)
            entry, exit_ = generator(df, **params)

            # Ensure boolean Series
            entry = entry.fillna(False).astype(bool)
            exit_ = exit_.fillna(False).astype(bool)

            entries.append(entry)
            exits.append(exit_)
            weights.append(weight)

        if combinator == "AND":
            combined_entry = self._combine_and(entries)
            combined_exit = self._combine_or(exits)  # Exit if ANY says exit
        elif combinator == "OR":
            combined_entry = self._combine_or(entries)
            combined_exit = self._combine_and(exits)  # Exit only if ALL say exit
        elif combinator == "MIN_AGREE":
            min_agree = signal_config.get("min_agree", 2)
            combined_entry = self._combine_min_agree(entries, min_agree)
            combined_exit = self._combine_or(exits)
        elif combinator == "WEIGHTED":
            threshold = signal_config.get("weight_threshold", 0.5)
            combined_entry = self._combine_weighted(entries, weights, threshold)
            combined_exit = self._combine_or(exits)
        else:
            raise ValueError(f"Unknown combinator: {combinator}")

        return combined_entry, combined_exit

    @staticmethod
    def _combine_and(signals: list[pd.Series]) -> pd.Series:
        """All signals must be True."""
        result = signals[0].copy()
        for s in signals[1:]:
            result = result & s
        return result

    @staticmethod
    def _combine_or(signals: list[pd.Series]) -> pd.Series:
        """Any signal True is enough."""
        result = signals[0].copy()
        for s in signals[1:]:
            result = result | s
        return result

    @staticmethod
    def _combine_min_agree(signals: list[pd.Series], min_agree: int) -> pd.Series:
        """At least min_agree signals must be True."""
        stacked = pd.concat(signals, axis=1)
        agree_count = stacked.sum(axis=1)
        return agree_count >= min_agree

    @staticmethod
    def _combine_weighted(
        signals: list[pd.Series], weights: list[float], threshold: float
    ) -> pd.Series:
        """Weighted sum of signals must exceed threshold."""
        total_weight = sum(weights)
        if total_weight == 0:
            return pd.Series(False, index=signals[0].index)

        weighted_sum = pd.Series(0.0, index=signals[0].index)
        for s, w in zip(signals, weights):
            weighted_sum += s.astype(float) * w

        normalized = weighted_sum / total_weight
        return normalized >= threshold
