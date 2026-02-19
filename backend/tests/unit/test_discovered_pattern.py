"""Tests for DiscoveredPattern model."""

import pytest
from app.models.discovered_pattern import DiscoveredPattern


class TestDiscoveredPatternModel:
    def test_create_instance(self):
        p = DiscoveredPattern(
            name="RSI + MACD Golden Cross",
            description="Rising pattern with RSI bounce and MACD cross",
            pattern_type="rise_5pct_5day",
            feature_importance={"rsi_14": 0.3, "macd_signal_cross": 0.25},
            model_metrics={"accuracy": 0.72, "f1": 0.65},
            rule_config={"rules": [{"factor": "rsi_14", "operator": "<=", "threshold": 40}]},
            status="draft",
            sample_count=500,
            event_count=45,
        )
        assert p.name == "RSI + MACD Golden Cross"
        assert p.pattern_type == "rise_5pct_5day"
        assert p.feature_importance["rsi_14"] == 0.3
        assert p.status == "draft"
        assert p.sample_count == 500

    def test_tablename(self):
        assert DiscoveredPattern.__tablename__ == "discovered_patterns"

    def test_default_status(self):
        """Default status is 'draft' when explicitly set."""
        p = DiscoveredPattern(
            name="test",
            pattern_type="test",
            status="draft",
        )
        assert p.status == "draft"

    def test_explicit_counts(self):
        p = DiscoveredPattern(
            name="test",
            pattern_type="test",
            sample_count=0,
            event_count=0,
        )
        assert p.sample_count == 0
        assert p.event_count == 0

    def test_status_values(self):
        for status in ["draft", "validated", "active", "deprecated"]:
            p = DiscoveredPattern(
                name="test",
                pattern_type="test",
                status=status,
            )
            assert p.status == status
