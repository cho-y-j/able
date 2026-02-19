"""Tests for investor flow factor extractors."""

import pytest
from app.analysis.signals.flow_signals import extract_flow_factors, compute_foreign_3day_trend


class TestExtractFlowFactors:
    def test_basic_extraction(self):
        data = {
            "foreign_net_buy_qty": 50000,
            "institutional_net_buy_qty": -30000,
            "individual_net_buy_qty": -20000,
        }
        factors = extract_flow_factors(data, total_volume=1_000_000)
        assert factors["foreign_net_buy_qty"] == 50000.0
        assert factors["institutional_net_buy_qty"] == -30000.0
        assert factors["foreign_net_buy_ratio"] == pytest.approx(0.05)
        assert factors["institutional_net_buy_ratio"] == pytest.approx(-0.03)

    def test_zero_volume_returns_zero_ratios(self):
        data = {
            "foreign_net_buy_qty": 50000,
            "institutional_net_buy_qty": 30000,
        }
        factors = extract_flow_factors(data, total_volume=0)
        assert factors["foreign_net_buy_ratio"] == 0.0
        assert factors["institutional_net_buy_ratio"] == 0.0

    def test_empty_data_returns_zeros(self):
        factors = extract_flow_factors({}, total_volume=100000)
        assert factors["foreign_net_buy_qty"] == 0.0
        assert factors["institutional_net_buy_qty"] == 0.0

    def test_negative_foreign_buying(self):
        data = {
            "foreign_net_buy_qty": -100000,
            "institutional_net_buy_qty": 80000,
            "individual_net_buy_qty": 20000,
        }
        factors = extract_flow_factors(data, total_volume=500_000)
        assert factors["foreign_net_buy_qty"] == -100000.0
        assert factors["foreign_net_buy_ratio"] < 0

    def test_returns_all_required_keys(self):
        data = {
            "foreign_net_buy_qty": 1000,
            "institutional_net_buy_qty": 2000,
        }
        factors = extract_flow_factors(data, total_volume=100000)
        assert "foreign_net_buy_qty" in factors
        assert "institutional_net_buy_qty" in factors
        assert "foreign_net_buy_ratio" in factors
        assert "institutional_net_buy_ratio" in factors


class TestForeign3DayTrend:
    def test_3_days_buying(self):
        result = compute_foreign_3day_trend([100, 200, 50])
        assert result == 1.0

    def test_3_days_selling(self):
        result = compute_foreign_3day_trend([-100, -200, -50])
        assert result == -1.0

    def test_mixed_returns_zero(self):
        result = compute_foreign_3day_trend([100, -200, 50])
        assert result == 0.0

    def test_insufficient_data(self):
        assert compute_foreign_3day_trend([100, 200]) == 0.0
        assert compute_foreign_3day_trend([100]) == 0.0
        assert compute_foreign_3day_trend([]) == 0.0

    def test_zero_not_counted_as_buying(self):
        result = compute_foreign_3day_trend([0, 100, 200])
        assert result == 0.0

    def test_longer_list_uses_first_3(self):
        result = compute_foreign_3day_trend([100, 200, 300, -500, -600])
        assert result == 1.0
