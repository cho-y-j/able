from app.analysis.validation.scoring import calculate_composite_score, normalize_metric


class TestScoring:
    def test_normalize_metric(self):
        assert normalize_metric(2.0, "sharpe_ratio") == 60.0  # (2 - (-1)) / (4 - (-1)) * 100
        assert normalize_metric(0, "sharpe_ratio") == 20.0
        assert normalize_metric(50, "win_rate") == 50.0  # (50-20)/(80-20)*100

    def test_composite_score(self):
        metrics = {
            "annual_return": 30,
            "sharpe_ratio": 2.0,
            "sortino_ratio": 3.0,
            "max_drawdown": -10,
            "calmar_ratio": 3.0,
            "win_rate": 55,
            "profit_factor": 2.0,
        }
        result = calculate_composite_score(metrics)
        assert "composite_score" in result
        assert "grade" in result
        assert 0 <= result["composite_score"] <= 100
        assert result["grade"] in ("A+", "A", "B+", "B", "C+", "C", "D", "F")

    def test_poor_strategy(self):
        metrics = {
            "annual_return": -10,
            "sharpe_ratio": -0.5,
            "sortino_ratio": -0.3,
            "max_drawdown": -40,
            "calmar_ratio": -0.2,
            "win_rate": 25,
            "profit_factor": 0.5,
        }
        result = calculate_composite_score(metrics)
        assert result["composite_score"] < 40
        assert result["grade"] in ("D", "F")
