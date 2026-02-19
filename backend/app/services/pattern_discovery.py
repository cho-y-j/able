"""Pattern Discovery Engine.

Discovers multi-factor patterns that predict stock price movements
by analyzing historical factor snapshots and price data.

Pipeline:
1. Extract rise events (stocks that rose N% in M days)
2. Build feature matrix from factor snapshots before each event
3. Train classifier (RandomForest) to distinguish events from non-events
4. Extract feature importance as the discovered pattern
5. Generate screening rules for live trading
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def extract_rise_events(
    price_data: pd.DataFrame,
    threshold_pct: float = 5.0,
    window_days: int = 5,
) -> list[dict[str, Any]]:
    """Find dates where a stock rose by threshold% within window days.

    Args:
        price_data: DataFrame with 'date' and 'close' columns
        threshold_pct: Minimum rise percentage
        window_days: Look-ahead window for measuring rise

    Returns:
        List of {date, close, future_close, return_pct}
    """
    if len(price_data) < window_days + 1:
        return []

    events = []
    closes = price_data["close"].values
    dates = price_data["date"].values if "date" in price_data.columns else list(range(len(closes)))

    for i in range(len(closes) - window_days):
        future_max = max(closes[i + 1: i + window_days + 1])
        return_pct = (future_max - closes[i]) / closes[i] * 100

        if return_pct >= threshold_pct:
            events.append({
                "index": i,
                "date": dates[i],
                "close": float(closes[i]),
                "future_close": float(future_max),
                "return_pct": float(return_pct),
            })

    return events


def build_feature_matrix(
    factor_snapshots: dict[str, dict[str, float]],
    event_indices: list[int],
    non_event_indices: list[int],
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Build X, y matrices from factor snapshots.

    Args:
        factor_snapshots: {index_or_date: {factor_name: value}}
        event_indices: Indices/dates of rise events (label=1)
        non_event_indices: Indices/dates of non-events (label=0)

    Returns:
        (X, y, feature_names) where X is (n_samples, n_features), y is (n_samples,)
    """
    all_indices = event_indices + non_event_indices
    labels = [1] * len(event_indices) + [0] * len(non_event_indices)

    # Determine feature names from first available snapshot
    feature_names = []
    for idx in all_indices:
        key = str(idx)
        if key in factor_snapshots and factor_snapshots[key]:
            feature_names = sorted(factor_snapshots[key].keys())
            break

    if not feature_names:
        return np.array([]), np.array([]), []

    rows = []
    valid_labels = []
    for idx, label in zip(all_indices, labels):
        key = str(idx)
        if key not in factor_snapshots:
            continue
        snapshot = factor_snapshots[key]
        row = [snapshot.get(f, 0.0) for f in feature_names]
        rows.append(row)
        valid_labels.append(label)

    if not rows:
        return np.array([]), np.array([]), feature_names

    X = np.array(rows, dtype=np.float64)
    y = np.array(valid_labels, dtype=np.int32)

    # Replace NaN/Inf
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    return X, y, feature_names


def train_classifier(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    n_splits: int = 5,
) -> dict[str, Any]:
    """Train RandomForest classifier with time-series cross-validation.

    Returns:
        {
            feature_importance: {name: importance},
            metrics: {accuracy, precision, recall, f1},
            model: trained model object
        }
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

    if len(X) < 20 or len(feature_names) == 0:
        return {
            "feature_importance": {},
            "metrics": {"accuracy": 0, "precision": 0, "recall": 0, "f1": 0},
            "model": None,
        }

    tscv = TimeSeriesSplit(n_splits=min(n_splits, len(X) // 4))

    all_y_true = []
    all_y_pred = []

    # Final model trained on all data
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=5,
        min_samples_leaf=5,
        random_state=42,
        class_weight="balanced",
    )

    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        fold_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=5,
            min_samples_leaf=5,
            random_state=42,
            class_weight="balanced",
        )
        fold_model.fit(X_train, y_train)
        y_pred = fold_model.predict(X_test)

        all_y_true.extend(y_test)
        all_y_pred.extend(y_pred)

    # Train final model on all data
    model.fit(X, y)

    # Metrics from cross-validation
    y_true = np.array(all_y_true)
    y_pred = np.array(all_y_pred)

    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }

    # Feature importance
    importance = dict(zip(feature_names, model.feature_importances_.tolist()))
    importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

    return {
        "feature_importance": importance,
        "metrics": metrics,
        "model": model,
    }


def generate_screening_rule(
    feature_importance: dict[str, float],
    X: np.ndarray,
    feature_names: list[str],
    top_n: int = 5,
) -> dict[str, Any]:
    """Generate screening rules from top important features.

    Uses median values of event samples as thresholds.

    Returns:
        {
            "rules": [{"factor": name, "operator": ">=", "threshold": value}],
            "min_match": 3
        }
    """
    if len(feature_importance) == 0 or len(X) == 0:
        return {"rules": [], "min_match": 0}

    # Get top N factors
    top_factors = list(feature_importance.keys())[:top_n]
    factor_indices = {name: i for i, name in enumerate(feature_names)}

    rules = []
    for factor in top_factors:
        if factor not in factor_indices:
            continue
        idx = factor_indices[factor]
        col_values = X[:, idx]
        median = float(np.median(col_values))

        # Determine direction based on feature behavior
        # If higher value correlates with events, use >=; otherwise <=
        rules.append({
            "factor": factor,
            "operator": ">=",
            "threshold": round(median, 4),
            "importance": round(feature_importance[factor], 4),
        })

    return {
        "rules": rules,
        "min_match": max(1, len(rules) // 2),
    }


def grade_pattern(metrics: dict[str, float]) -> str:
    """Assign a letter grade based on model metrics."""
    f1 = metrics.get("f1", 0)
    if f1 >= 0.7:
        return "A"
    elif f1 >= 0.5:
        return "B"
    elif f1 >= 0.3:
        return "C"
    else:
        return "D"
