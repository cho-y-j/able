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


class TestIndividualNetBuyRestored:
    """Q-020b: individual_net_buy_qty was read at flow_signals.py:30 and dropped.

    ADR-0006's news-trap filter keys off "individual net buying dominance", so
    these keys must actually be present in the returned dict.
    """

    def test_individual_qty_is_returned(self):
        data = {
            "foreign_net_buy_qty": 50000,
            "institutional_net_buy_qty": -30000,
            "individual_net_buy_qty": -20000,
        }
        factors = extract_flow_factors(data, total_volume=1_000_000)
        assert "individual_net_buy_qty" in factors
        assert factors["individual_net_buy_qty"] == -20000.0

    def test_individual_ratio_follows_existing_normalisation(self):
        data = {
            "foreign_net_buy_qty": 0,
            "institutional_net_buy_qty": 0,
            "individual_net_buy_qty": -20000,
        }
        factors = extract_flow_factors(data, total_volume=1_000_000)
        assert factors["individual_net_buy_ratio"] == pytest.approx(-0.02)

    def test_individual_missing_key_defaults_to_zero(self):
        factors = extract_flow_factors({}, total_volume=100000)
        assert factors["individual_net_buy_qty"] == 0.0
        assert factors["individual_net_buy_ratio"] == 0.0

    def test_individual_ratio_zero_when_volume_zero(self):
        data = {"individual_net_buy_qty": -20000}
        factors = extract_flow_factors(data, total_volume=0)
        assert factors["individual_net_buy_ratio"] == 0.0


class TestSmartMoneyAggregate:
    def test_smart_money_is_foreign_plus_institutional(self):
        data = {
            "foreign_net_buy_qty": 50000,
            "institutional_net_buy_qty": -30000,
            "individual_net_buy_qty": -20000,
        }
        factors = extract_flow_factors(data, total_volume=1_000_000)
        assert factors["smart_money_net_buy_qty"] == 20000.0
        assert factors["smart_money_net_buy_ratio"] == pytest.approx(0.02)

    def test_smart_money_ratio_zero_when_volume_zero(self):
        data = {
            "foreign_net_buy_qty": 50000,
            "institutional_net_buy_qty": 30000,
        }
        factors = extract_flow_factors(data, total_volume=0)
        assert factors["smart_money_net_buy_qty"] == 80000.0
        assert factors["smart_money_net_buy_ratio"] == 0.0


class TestFlowOpposition:
    """Three-party opposition: (foreign + institutional) vs individual."""

    def test_foreign_buy_individual_sell_is_max_positive(self):
        """ADR-0006 'weight up' side: smart money accumulating, retail exiting."""
        data = {
            "foreign_net_buy_qty": 60000,
            "institutional_net_buy_qty": 20000,
            "individual_net_buy_qty": -80000,
        }
        factors = extract_flow_factors(data, total_volume=1_000_000)
        assert factors["flow_opposition_qty"] == 160000.0
        assert factors["flow_opposition_ratio"] == pytest.approx(0.16)
        assert factors["flow_opposition_score"] == pytest.approx(1.0)

    def test_individual_buy_smart_money_sell_is_max_negative(self):
        """ADR-0006 news-trap side: retail absorbing institutional supply."""
        data = {
            "foreign_net_buy_qty": -60000,
            "institutional_net_buy_qty": -20000,
            "individual_net_buy_qty": 80000,
        }
        factors = extract_flow_factors(data, total_volume=1_000_000)
        assert factors["flow_opposition_qty"] == -160000.0
        assert factors["flow_opposition_ratio"] == pytest.approx(-0.16)
        assert factors["flow_opposition_score"] == pytest.approx(-1.0)

    def test_sign_flips_between_the_two_opposing_cases(self):
        aligned = extract_flow_factors(
            {
                "foreign_net_buy_qty": 60000,
                "institutional_net_buy_qty": 20000,
                "individual_net_buy_qty": -80000,
            },
            total_volume=1_000_000,
        )
        trap = extract_flow_factors(
            {
                "foreign_net_buy_qty": -60000,
                "institutional_net_buy_qty": -20000,
                "individual_net_buy_qty": 80000,
            },
            total_volume=1_000_000,
        )
        assert aligned["flow_opposition_score"] > 0 > trap["flow_opposition_score"]
        assert aligned["flow_opposition_qty"] == -trap["flow_opposition_qty"]

    def test_same_direction_scores_strictly_below_saturation(self):
        """Both sides net buying (other corporates are the seller) is NOT the
        strongest case and must be numerically distinguishable from it."""
        data = {
            "foreign_net_buy_qty": 60000,
            "institutional_net_buy_qty": 20000,
            "individual_net_buy_qty": 40000,
        }
        factors = extract_flow_factors(data, total_volume=1_000_000)
        assert factors["flow_opposition_qty"] == 40000.0
        assert factors["flow_opposition_score"] == pytest.approx(40000 / 120000)
        assert factors["flow_opposition_score"] < 1.0

    def test_score_is_bounded(self):
        cases = [
            {"foreign_net_buy_qty": 1, "institutional_net_buy_qty": 0,
             "individual_net_buy_qty": -10_000_000},
            {"foreign_net_buy_qty": -10_000_000, "institutional_net_buy_qty": 0,
             "individual_net_buy_qty": 1},
            {"foreign_net_buy_qty": 500, "institutional_net_buy_qty": 500,
             "individual_net_buy_qty": 1000},
            {"foreign_net_buy_qty": -7, "institutional_net_buy_qty": 3,
             "individual_net_buy_qty": -4},
        ]
        for data in cases:
            score = extract_flow_factors(data, total_volume=1_000_000)["flow_opposition_score"]
            assert -1.0 <= score <= 1.0, data

    def test_score_is_scale_free(self):
        small = extract_flow_factors(
            {"foreign_net_buy_qty": 100, "institutional_net_buy_qty": 0,
             "individual_net_buy_qty": -50},
            total_volume=1_000_000,
        )
        large = extract_flow_factors(
            {"foreign_net_buy_qty": 100_000, "institutional_net_buy_qty": 0,
             "individual_net_buy_qty": -50_000},
            total_volume=1_000_000,
        )
        assert small["flow_opposition_score"] == pytest.approx(large["flow_opposition_score"])
        assert small["flow_opposition_ratio"] != large["flow_opposition_ratio"]

    def test_all_flat_gives_zero_score_not_division_error(self):
        factors = extract_flow_factors(
            {
                "foreign_net_buy_qty": 0,
                "institutional_net_buy_qty": 0,
                "individual_net_buy_qty": 0,
            },
            total_volume=1_000_000,
        )
        assert factors["flow_opposition_score"] == 0.0
        assert factors["flow_opposition_qty"] == 0.0
        assert factors["flow_opposition_ratio"] == 0.0

    def test_empty_data_gives_zero_score(self):
        factors = extract_flow_factors({}, total_volume=1_000_000)
        assert factors["flow_opposition_score"] == 0.0

    def test_opposition_ratio_zero_when_volume_zero_but_score_survives(self):
        """total_volume == 0 must zero the volume-normalised ratio only; the
        scale-free score needs no volume and must still carry the sign."""
        data = {
            "foreign_net_buy_qty": 60000,
            "institutional_net_buy_qty": 20000,
            "individual_net_buy_qty": -80000,
        }
        factors = extract_flow_factors(data, total_volume=0)
        assert factors["flow_opposition_ratio"] == 0.0
        assert factors["flow_opposition_qty"] == 160000.0
        assert factors["flow_opposition_score"] == pytest.approx(1.0)

    def test_negative_volume_treated_as_zero_volume(self):
        data = {"foreign_net_buy_qty": 100, "institutional_net_buy_qty": 0,
                "individual_net_buy_qty": -100}
        factors = extract_flow_factors(data, total_volume=-5)
        assert factors["foreign_net_buy_ratio"] == 0.0
        assert factors["individual_net_buy_ratio"] == 0.0
        assert factors["smart_money_net_buy_ratio"] == 0.0
        assert factors["flow_opposition_ratio"] == 0.0
