import numpy as np


# Strategy scoring weights - includes MC and OOS validation scores
SCORING_WEIGHTS = {
    "annual_return": 0.12,
    "sharpe_ratio": 0.15,
    "sortino_ratio": 0.12,
    "max_drawdown": 0.12,
    "calmar_ratio": 0.08,
    "win_rate": 0.05,
    "profit_factor": 0.08,
    "wfa_score": 0.08,
    "mc_score": 0.10,
    "oos_score": 0.10,
}

# Benchmark values for normalization (0-100 scale)
BENCHMARKS = {
    "annual_return": {"min": -20, "max": 100},    # percent
    "sharpe_ratio": {"min": -1, "max": 4},
    "sortino_ratio": {"min": -1, "max": 6},
    "max_drawdown": {"min": -50, "max": 0},        # inverted: closer to 0 is better
    "calmar_ratio": {"min": -1, "max": 5},
    "win_rate": {"min": 20, "max": 80},            # percent
    "profit_factor": {"min": 0, "max": 5},
    "wfa_score": {"min": 0, "max": 100},
    "mc_score": {"min": 0, "max": 100},
    "oos_score": {"min": 0, "max": 100},
}


def normalize_metric(value: float, metric_name: str) -> float:
    """Normalize a metric to 0-100 scale."""
    benchmark = BENCHMARKS.get(metric_name, {"min": 0, "max": 100})
    normalized = (value - benchmark["min"]) / (benchmark["max"] - benchmark["min"]) * 100
    return max(0, min(100, normalized))


def calculate_composite_score(metrics: dict, wfa_result: dict | None = None) -> dict:
    """Calculate weighted composite score from backtest metrics and validation results.

    Returns dict with composite_score (0-100), grade (A+~F), and individual scores.
    """
    scores = {}

    for metric_name, weight in SCORING_WEIGHTS.items():
        if metric_name in ("wfa_score", "stability"):
            value = wfa_result.get(metric_name, 0) if wfa_result else 0
        elif metric_name in ("mc_score", "oos_score"):
            # Can be passed directly in metrics or via wfa_result
            value = metrics.get(metric_name, 0)
            if value == 0 and wfa_result:
                value = wfa_result.get(metric_name, 0)
        elif metric_name == "max_drawdown":
            value = metrics.get(metric_name, -50)
        else:
            value = metrics.get(metric_name, 0)

        normalized = normalize_metric(value, metric_name)
        scores[metric_name] = {
            "raw": value,
            "normalized": round(normalized, 2),
            "weight": weight,
            "weighted": round(normalized * weight, 2),
        }

    composite = sum(s["weighted"] for s in scores.values())

    # Grade assignment
    if composite >= 90:
        grade = "A+"
    elif composite >= 80:
        grade = "A"
    elif composite >= 70:
        grade = "B+"
    elif composite >= 60:
        grade = "B"
    elif composite >= 50:
        grade = "C+"
    elif composite >= 40:
        grade = "C"
    elif composite >= 30:
        grade = "D"
    else:
        grade = "F"

    return {
        "composite_score": round(composite, 2),
        "grade": grade,
        "individual_scores": scores,
    }


def score_strategy(metrics: dict, wfa_result: dict | None = None) -> dict:
    """Alias for calculate_composite_score for backward compatibility."""
    result = calculate_composite_score(metrics, wfa_result)
    return {"total_score": result["composite_score"], "grade": result["grade"], **result}
