"""Tests for pattern discovery engine."""

import math
import numpy as np
import pandas as pd
import pytest

from app.services.pattern_discovery import (
    extract_rise_events,
    build_feature_matrix,
    train_classifier,
    generate_screening_rule,
    grade_pattern,
)


def _make_price_data(n=100, with_events=True):
    """Create synthetic price data with optional rise events."""
    np.random.seed(42)
    base = 50000
    closes = [base]
    for i in range(1, n):
        # Normal random walk
        change = np.random.randn() * 200
        if with_events and i in [30, 60, 80]:
            # Insert rise events: +6% over 3 days
            change = closes[-1] * 0.025
        closes.append(closes[-1] + change)

    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "date": dates,
        "close": closes,
    })


class TestExtractRiseEvents:
    def test_finds_events(self):
        df = _make_price_data(100, with_events=True)
        events = extract_rise_events(df, threshold_pct=3.0, window_days=5)
        assert len(events) > 0

    def test_no_events_in_flat_data(self):
        # Flat prices — no significant rises
        df = pd.DataFrame({
            "date": pd.date_range("2025-01-01", periods=50, freq="B"),
            "close": [50000] * 50,
        })
        events = extract_rise_events(df, threshold_pct=5.0, window_days=5)
        assert len(events) == 0

    def test_event_has_required_fields(self):
        df = _make_price_data(100, with_events=True)
        events = extract_rise_events(df, threshold_pct=3.0, window_days=5)
        if events:
            e = events[0]
            assert "index" in e
            assert "date" in e
            assert "close" in e
            assert "return_pct" in e
            assert e["return_pct"] >= 3.0

    def test_short_data_returns_empty(self):
        df = pd.DataFrame({"date": ["2025-01-01"], "close": [50000]})
        assert extract_rise_events(df) == []

    def test_threshold_filtering(self):
        df = _make_price_data(100, with_events=True)
        events_3 = extract_rise_events(df, threshold_pct=3.0)
        events_10 = extract_rise_events(df, threshold_pct=10.0)
        assert len(events_3) >= len(events_10)


class TestBuildFeatureMatrix:
    def test_builds_matrix(self):
        snapshots = {
            "0": {"rsi_14": 45.0, "macd_histogram": 100.0},
            "1": {"rsi_14": 55.0, "macd_histogram": -50.0},
            "2": {"rsi_14": 30.0, "macd_histogram": 200.0},
            "3": {"rsi_14": 70.0, "macd_histogram": -100.0},
        }
        X, y, features = build_feature_matrix(
            snapshots,
            event_indices=[0, 2],
            non_event_indices=[1, 3],
        )
        assert X.shape == (4, 2)
        assert y.shape == (4,)
        assert len(features) == 2
        assert sum(y == 1) == 2
        assert sum(y == 0) == 2

    def test_missing_snapshots_skipped(self):
        snapshots = {
            "0": {"rsi_14": 45.0},
            # "1" missing
        }
        X, y, features = build_feature_matrix(
            snapshots,
            event_indices=[0],
            non_event_indices=[1],
        )
        assert X.shape[0] == 1  # Only one valid sample

    def test_empty_input(self):
        X, y, features = build_feature_matrix({}, [], [])
        assert len(X) == 0
        assert len(y) == 0

    def test_nan_handled(self):
        snapshots = {
            "0": {"rsi_14": float("nan"), "macd": 100.0},
            "1": {"rsi_14": 50.0, "macd": float("inf")},
        }
        X, y, features = build_feature_matrix(
            snapshots,
            event_indices=[0],
            non_event_indices=[1],
        )
        assert not np.any(np.isnan(X))
        assert not np.any(np.isinf(X))


class TestTrainClassifier:
    def test_trains_model(self):
        np.random.seed(42)
        n = 100
        X = np.random.randn(n, 5)
        # Make pattern: events have higher feature 0
        y = (X[:, 0] > 0.5).astype(int)
        features = ["f1", "f2", "f3", "f4", "f5"]

        result = train_classifier(X, y, features)
        assert "feature_importance" in result
        assert "metrics" in result
        assert "model" in result
        assert len(result["feature_importance"]) == 5
        assert 0 <= result["metrics"]["accuracy"] <= 1
        assert 0 <= result["metrics"]["f1"] <= 1

    def test_insufficient_data(self):
        X = np.array([[1, 2], [3, 4]])
        y = np.array([0, 1])
        result = train_classifier(X, y, ["a", "b"])
        assert result["model"] is None
        assert result["metrics"]["accuracy"] == 0

    def test_feature_importance_sorted(self):
        np.random.seed(42)
        X = np.random.randn(200, 3)
        y = (X[:, 0] + X[:, 1] * 0.5 > 0).astype(int)
        features = ["main_signal", "weak_signal", "noise"]

        result = train_classifier(X, y, features)
        importances = list(result["feature_importance"].values())
        # Should be sorted descending
        assert importances == sorted(importances, reverse=True)


class TestGenerateScreeningRule:
    def test_generates_rules(self):
        importance = {"rsi_14": 0.3, "macd": 0.25, "adx": 0.15, "volume": 0.1, "bb": 0.05}
        X = np.array([[45, 100, 20, 1.5, 0.5], [30, -50, 15, 0.8, 0.3]])
        features = ["rsi_14", "macd", "adx", "volume", "bb"]

        rule = generate_screening_rule(importance, X, features, top_n=3)
        assert "rules" in rule
        assert "min_match" in rule
        assert len(rule["rules"]) == 3
        assert rule["rules"][0]["factor"] == "rsi_14"

    def test_empty_importance(self):
        rule = generate_screening_rule({}, np.array([]), [])
        assert rule["rules"] == []
        assert rule["min_match"] == 0

    def test_rule_has_threshold(self):
        importance = {"rsi_14": 0.5}
        X = np.array([[45], [55], [35]])
        features = ["rsi_14"]

        rule = generate_screening_rule(importance, X, features, top_n=1)
        assert len(rule["rules"]) == 1
        r = rule["rules"][0]
        assert "threshold" in r
        assert "operator" in r
        assert "importance" in r


class TestGradePattern:
    def test_grade_a(self):
        assert grade_pattern({"f1": 0.75}) == "A"

    def test_grade_b(self):
        assert grade_pattern({"f1": 0.55}) == "B"

    def test_grade_c(self):
        assert grade_pattern({"f1": 0.35}) == "C"

    def test_grade_d(self):
        assert grade_pattern({"f1": 0.1}) == "D"

    def test_missing_f1(self):
        assert grade_pattern({}) == "D"
