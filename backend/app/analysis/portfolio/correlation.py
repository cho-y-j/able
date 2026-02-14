"""Strategy correlation analysis: return correlation matrix and diversification ratio."""

from dataclasses import dataclass
import numpy as np


@dataclass
class CorrelationResult:
    strategy_ids: list[str]
    strategy_names: list[str]
    correlation_matrix: list[list[float]]  # NxN correlation matrix
    diversification_ratio: float  # >1 means diversification benefit
    avg_correlation: float
    max_pair: tuple[str, str, float] | None  # most correlated pair
    min_pair: tuple[str, str, float] | None  # least correlated pair


class StrategyCorrelation:
    """Computes correlation between strategy daily returns."""

    @staticmethod
    def compute(
        strategy_returns: dict[str, dict[str, list[float]]],
    ) -> CorrelationResult:
        """Calculate correlation matrix from strategy daily returns.

        Args:
            strategy_returns: {strategy_id: {"name": str, "returns": [float]}}
                Each strategy must have same-length daily return arrays.

        Returns:
            CorrelationResult with correlation matrix and diversification metrics.
        """
        ids = list(strategy_returns.keys())
        names = [strategy_returns[sid]["name"] for sid in ids]
        n = len(ids)

        if n < 2:
            return CorrelationResult(
                strategy_ids=ids,
                strategy_names=names,
                correlation_matrix=[[1.0]] if n == 1 else [],
                diversification_ratio=1.0,
                avg_correlation=0.0,
                max_pair=None,
                min_pair=None,
            )

        # Build return matrix (n_strategies x n_days)
        returns_matrix = np.array([
            strategy_returns[sid]["returns"] for sid in ids
        ], dtype=float)

        # Compute correlation matrix
        corr = np.corrcoef(returns_matrix)

        # Handle NaN (e.g., zero-variance strategy)
        corr = np.nan_to_num(corr, nan=0.0)

        # Find max/min correlation pairs (off-diagonal)
        max_corr, min_corr = -2.0, 2.0
        max_pair, min_pair = None, None

        for i in range(n):
            for j in range(i + 1, n):
                c = float(corr[i, j])
                if c > max_corr:
                    max_corr = c
                    max_pair = (ids[i], ids[j], round(c, 4))
                if c < min_corr:
                    min_corr = c
                    min_pair = (ids[i], ids[j], round(c, 4))

        # Average off-diagonal correlation
        off_diag = [float(corr[i, j]) for i in range(n) for j in range(i + 1, n)]
        avg_correlation = float(np.mean(off_diag)) if off_diag else 0.0

        # Diversification ratio = weighted_avg_vol / portfolio_vol
        # Using equal weights for simplicity
        vols = np.std(returns_matrix, axis=1)
        weights = np.ones(n) / n
        weighted_avg_vol = float(np.dot(weights, vols))
        portfolio_returns = np.dot(weights, returns_matrix)
        portfolio_vol = float(np.std(portfolio_returns))
        diversification_ratio = weighted_avg_vol / portfolio_vol if portfolio_vol > 0 else 1.0

        return CorrelationResult(
            strategy_ids=ids,
            strategy_names=names,
            correlation_matrix=[[round(float(corr[i, j]), 4) for j in range(n)] for i in range(n)],
            diversification_ratio=round(diversification_ratio, 4),
            avg_correlation=round(avg_correlation, 4),
            max_pair=max_pair,
            min_pair=min_pair,
        )
