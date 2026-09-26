"""Tests for validation schemas and Monte Carlo / OOS / CPCV functions."""

import pytest
import numpy as np
import pandas as pd

from app.schemas.validation import (
    MonteCarloRequest, MonteCarloResponse,
    OOSRequest, OOSResponse,
    CPCVRequest, CPCVResponse,
    StrategyCompareResponse,
)
from app.analysis.validation.monte_carlo import monte_carlo_simulation
from app.analysis.validation.out_of_sample import (
    out_of_sample_test,
    combinatorial_purged_cv,
)


class TestValidationSchemas:
    def test_monte_carlo_request_defaults(self):
        req = MonteCarloRequest()
        assert req.n_simulations == 1000
        assert req.initial_capital == 10_000_000

    def test_monte_carlo_response(self):
        resp = MonteCarloResponse(mc_score=85.5, simulations_run=1000, n_trades=50)
        assert resp.mc_score == 85.5

    def test_oos_request_defaults(self):
        req = OOSRequest()
        assert req.oos_ratio == 0.3
        assert req.data_source == "yahoo"

    def test_cpcv_request_defaults(self):
        req = CPCVRequest()
        assert req.n_splits == 5
        assert req.purge_days == 5

    def test_compare_response(self):
        resp = StrategyCompareResponse(
            strategies=[{"strategy_id": "abc", "name": "test"}],
            ranking=[{"rank": 1, "strategy_id": "abc", "name": "test", "score": 80}],
        )
        assert len(resp.strategies) == 1
        assert resp.ranking[0]["rank"] == 1


class TestMonteCarloSimulation:
    def test_basic_simulation(self):
        np.random.seed(42)
        returns = [2.5, -1.2, 3.1, -0.5, 1.8, -2.0, 0.9, 1.5, -0.8, 2.2]
        result = monte_carlo_simulation(returns, n_simulations=100)

        assert result["mc_score"] > 0
        assert result["simulations_run"] == 100
        assert result["n_trades"] == 10
        assert "statistics" in result
        assert "drawdown_stats" in result
        assert "confidence_bands" in result
        assert "percentiles" in result

    def test_insufficient_trades(self):
        result = monte_carlo_simulation([1.0, 2.0], n_simulations=100)
        assert result["mc_score"] == 0
        assert "Insufficient" in result.get("message", "")

    def test_empty_trades(self):
        result = monte_carlo_simulation([], n_simulations=100)
        assert result["mc_score"] == 0

    def test_profitable_strategy(self):
        np.random.seed(42)
        # Mostly positive returns
        returns = [3.0, 2.0, 1.5, -1.0, 2.5, -0.5, 3.0, 1.0, 2.0, -0.8]
        result = monte_carlo_simulation(returns, n_simulations=500)
        assert result["mc_score"] > 50  # Should be mostly profitable

    def test_losing_strategy(self):
        np.random.seed(42)
        # Mostly negative returns
        returns = [-3.0, -2.0, 0.5, -1.5, -2.5, 0.3, -3.0, -1.0, -2.0, 0.2]
        result = monte_carlo_simulation(returns, n_simulations=500)
        assert result["mc_score"] < 50  # Should be mostly unprofitable

    def test_statistics_keys(self):
        np.random.seed(42)
        returns = [1.0, -0.5, 2.0, -1.0, 1.5, 0.5, -0.3, 1.2, -0.8, 0.7]
        result = monte_carlo_simulation(returns, n_simulations=100)

        stats = result["statistics"]
        assert "mean_return" in stats
        assert "median_return" in stats
        assert "profitable_pct" in stats
        assert "risk_of_ruin_pct" in stats

        dd = result["drawdown_stats"]
        assert "mean_max_dd" in dd
        assert "worst_max_dd" in dd


class TestOutOfSample:
    def test_basic_oos(self, sample_ohlcv):
        from app.analysis.signals.registry import get_signal_generator
        signal_gen = get_signal_generator("sma_crossover")
        params = {"fast_period": 10, "slow_period": 30}

        result = out_of_sample_test(sample_ohlcv, signal_gen, params)
        assert "oos_score" in result
        assert result["oos_score"] >= 0

    def test_oos_has_is_and_oos_sections(self, sample_ohlcv):
        from app.analysis.signals.registry import get_signal_generator
        signal_gen = get_signal_generator("sma_crossover")
        params = {"fast_period": 10, "slow_period": 30}

        result = out_of_sample_test(sample_ohlcv, signal_gen, params)
        if "message" not in result:
            assert "in_sample" in result
            assert "out_of_sample" in result
            assert "degradation" in result

    def test_oos_insufficient_data(self):
        short_df = pd.DataFrame({
            "open": [100] * 20,
            "high": [105] * 20,
            "low": [95] * 20,
            "close": [100] * 20,
            "volume": [1000] * 20,
        }, index=pd.date_range("2024-01-01", periods=20, freq="B"))

        def dummy_sig(df, **kwargs):
            return pd.Series(False, index=df.index), pd.Series(False, index=df.index)

        result = out_of_sample_test(short_df, dummy_sig, {})
        assert result["oos_score"] == 0


class TestCPCV:
    """하부 함수 `combinatorial_purged_cv` 의 **현재 동작**을 고정하는 테스트.

    보강 경위 (Q-002b): 이 클래스의 원래 두 테스트는 키 존재와 `total_folds > 0` 만
    단정했다. 그 단정은 **비작동 구현에서도 통과한다** — 학습 경로가 없고
    (`out_of_sample.py:139-144` 의 `train_data` 가 소비되지 않는다), 조합형이 아니며
    (`:134` 반복당 테스트 그룹 1개), 예외를 전부 삼켜도(`:162-168`) 응답 키는 그대로 존재한다.
    즉 "CPCV 가 수행되었는가"를 전혀 검사하지 않는다.

    **테스트를 수정해 통과시킨 것이 아니다.** 원래 두 테스트는 한 줄도 바꾸지 않고 남겼고,
    아래에 결함을 드러내는 단정만 **추가**했다. 알고리즘 재작성은 Q-010a 범위이므로 여기서
    추가한 단정은 "현재 구현이 CPCV 가 아니다"라는 사실을 고정한다. Q-010a 가 착수되면
    `train_days`/경로 수 단정은 **깨지는 것이 정상**이며, 그때 이 클래스를 교체한다.
    """

    def test_basic_cpcv(self, sample_ohlcv):
        from app.analysis.signals.registry import get_signal_generator
        signal_gen = get_signal_generator("sma_crossover")
        params = {"fast_period": 10, "slow_period": 30}

        result = combinatorial_purged_cv(sample_ohlcv, signal_gen, params, n_splits=3)
        assert "cpcv_score" in result
        assert "folds" in result
        assert result["total_folds"] > 0

    def test_cpcv_fold_details(self, sample_ohlcv):
        from app.analysis.signals.registry import get_signal_generator
        signal_gen = get_signal_generator("rsi_mean_reversion")
        params = {"period": 14, "oversold": 30, "overbought": 70}

        result = combinatorial_purged_cv(sample_ohlcv, signal_gen, params, n_splits=4)
        for fold in result["folds"]:
            assert "fold" in fold
            assert "sharpe_ratio" in fold

    # ── 아래는 Q-002b 로 추가한 단정 ──────────────────────

    def test_cpcv_path_count_is_not_combinatorial(self, sample_ohlcv):
        """경로 수가 `n_splits` 이하다. AFML CPCV 라면 `k·C(N,k)/N` 이어야 한다."""
        from app.analysis.signals.registry import get_signal_generator
        signal_gen = get_signal_generator("sma_crossover")
        params = {"fast_period": 10, "slow_period": 30}

        for n_splits in (3, 5):
            result = combinatorial_purged_cv(
                sample_ohlcv, signal_gen, params, n_splits=n_splits
            )
            assert result["total_folds"] <= n_splits

    def test_cpcv_reports_no_training_period(self, sample_ohlcv):
        """학습 경로가 없다는 증거: 폴드가 학습 구간을 전혀 보고하지 않는다."""
        from app.analysis.signals.registry import get_signal_generator
        signal_gen = get_signal_generator("sma_crossover")
        params = {"fast_period": 10, "slow_period": 30}

        result = combinatorial_purged_cv(sample_ohlcv, signal_gen, params, n_splits=3)
        assert result["folds"]
        for fold in result["folds"]:
            assert "train_days" not in fold
            assert "train_period" not in fold

    def test_cpcv_returns_zero_score_when_every_fold_fails(self, sample_ohlcv):
        """전량 실패해도 정상 형태의 `cpcv_score: 0.0` 을 반환한다 (조용한 실패)."""
        def always_raises(df, **kwargs):
            raise ValueError("signal generation failed")

        result = combinatorial_purged_cv(sample_ohlcv, always_raises, {}, n_splits=3)
        assert result["cpcv_score"] == 0.0
        assert result["total_folds"] == 3
        assert all(f.get("error") for f in result["folds"])
        # 센티넬 0 이 평균에 섞인다 — 이것이 엔드포인트에서 교정되어야 하는 값이다
        assert result["mean_sharpe"] == 0.0


class TestCPCVEndpointHonesty:
    """Q-002b: 엔드포인트가 비작동 절차를 검증으로 제시하지 않음을 단정한다."""

    @staticmethod
    def _raw(folds, cpcv_score=0.0, mean_sharpe=0.0, std_sharpe=0.0):
        evaluated = len(folds)
        positive = sum(1 for f in folds if f.get("sharpe_ratio", 0) > 0)
        return {
            "cpcv_score": cpcv_score,
            "mean_sharpe": mean_sharpe,
            "std_sharpe": std_sharpe,
            "positive_folds": positive,
            "total_folds": evaluated,
            "folds": folds,
        }

    def test_status_is_never_verified_even_on_good_looking_result(self):
        from app.api.v1.backtests import _assess_cpcv

        folds = [
            {"fold": i + 1, "sharpe_ratio": 2.0, "total_return": 30.0}
            for i in range(5)
        ]
        out = _assess_cpcv(self._raw(folds, cpcv_score=100.0, mean_sharpe=2.0), 5)

        assert out["validation_status"] == "미검증"
        assert out["validation_status"] != "검증됨"
        assert out["is_validated"] is False
        assert out["score_is_meaningful"] is False
        assert out["failed_folds"] == 0
        assert out["succeeded_folds"] == 5

    def test_all_folds_failed_is_not_verified_and_score_is_none(self):
        from app.api.v1.backtests import _assess_cpcv
        from app.schemas.validation import (
            CPCV_REASON_ALL_FOLDS_FAILED,
            CPCV_REASON_SENTINEL_ZERO_IN_RAW_MEAN,
        )

        folds = [
            {"fold": i + 1, "sharpe_ratio": 0, "total_return": 0, "error": True}
            for i in range(3)
        ]
        out = _assess_cpcv(self._raw(folds), 3)

        assert out["validation_status"] == "미검증"
        assert out["is_validated"] is False
        # 전량 실패 시 0.0 을 점수로 내보내지 않는다
        assert out["cpcv_score"] is None
        assert out["mean_sharpe"] is None
        assert out["std_sharpe"] is None
        # 원값은 보존되지만 별도 필드로 격리된다
        assert out["cpcv_score_raw"] == 0.0
        assert out["failed_folds"] == 3
        assert out["succeeded_folds"] == 0
        assert CPCV_REASON_ALL_FOLDS_FAILED in out["reason_codes"]
        assert CPCV_REASON_SENTINEL_ZERO_IN_RAW_MEAN in out["reason_codes"]

    def test_failed_fold_count_is_exposed_and_excluded_from_mean(self):
        from app.api.v1.backtests import _assess_cpcv
        from app.schemas.validation import CPCV_REASON_SOME_FOLDS_FAILED

        folds = [
            {"fold": 1, "sharpe_ratio": 1.0, "total_return": 10.0},
            {"fold": 2, "sharpe_ratio": 3.0, "total_return": 30.0},
            {"fold": 3, "sharpe_ratio": 0, "total_return": 0, "error": True},
            {"fold": 4, "sharpe_ratio": 0, "total_return": 0, "error": True},
        ]
        # 하부 함수의 원 평균은 센티넬 0 두 개가 섞여 (1+3+0+0)/4 = 1.0
        out = _assess_cpcv(self._raw(folds, cpcv_score=50.0, mean_sharpe=1.0), 4)

        assert out["failed_folds"] == 2
        assert out["succeeded_folds"] == 2
        assert out["evaluated_folds"] == 4
        assert CPCV_REASON_SOME_FOLDS_FAILED in out["reason_codes"]
        # 센티넬 0 이 평균에 섞이지 않는다: (1+3)/2 = 2.0
        assert out["mean_sharpe"] == 2.0
        assert out["mean_sharpe_raw"] == 1.0
        # 점수도 성공 폴드만으로 재계산된다: 2/2 = 100%
        assert out["cpcv_score"] == 100.0
        assert out["cpcv_score_raw"] == 50.0

    def test_structural_reason_codes_always_present(self):
        from app.api.v1.backtests import _assess_cpcv
        from app.schemas.validation import CPCV_STRUCTURAL_REASON_CODES

        folds = [{"fold": 1, "sharpe_ratio": 1.0}]
        out = _assess_cpcv(self._raw(folds, cpcv_score=100.0, mean_sharpe=1.0), 1)

        for code in CPCV_STRUCTURAL_REASON_CODES:
            assert code in out["reason_codes"]
        assert out["is_combinatorial"] is False
        assert out["purge_applied"] is False
        assert out["train_path_present"] is False

    def test_name_does_not_claim_validation(self):
        from app.api.v1.backtests import _assess_cpcv

        out = _assess_cpcv(self._raw([{"fold": 1, "sharpe_ratio": 1.0}]), 1)

        assert out["procedure_claimed_by_name"] == "combinatorial_purged_cv"
        assert out["procedure_performed"] != out["procedure_claimed_by_name"]
        assert "검증 근거가 아니다" in out["integrity_message"]

    def test_no_folds_evaluated(self):
        from app.api.v1.backtests import _assess_cpcv
        from app.schemas.validation import CPCV_REASON_NO_FOLDS_EVALUATED

        out = _assess_cpcv({"cpcv_score": 0, "folds": []}, 5)

        assert out["validation_status"] == "미검증"
        assert out["cpcv_score"] is None
        assert out["evaluated_folds"] == 0
        assert out["skipped_folds"] == 5
        assert CPCV_REASON_NO_FOLDS_EVALUATED in out["reason_codes"]

    def test_response_schema_accepts_assessment(self):
        from app.api.v1.backtests import _assess_cpcv

        folds = [{"fold": 1, "sharpe_ratio": 0, "error": True}]
        resp = CPCVResponse(**_assess_cpcv(self._raw(folds), 3))

        assert resp.validation_status == "미검증"
        assert resp.is_validated is False
        assert resp.cpcv_score is None
        assert resp.failed_folds == 1
        assert resp.skipped_folds == 2

    @pytest.mark.asyncio
    async def test_endpoint_returns_unverified_when_all_folds_fail(self):
        """엔드포인트 경로 전체: 전량 실패 입력에서 `검증됨` 을 반환하지 않는다."""
        import uuid
        from unittest.mock import AsyncMock, MagicMock, patch
        from app.api.v1 import backtests as bt_api

        bt = MagicMock()
        bt.id = uuid.uuid4()
        bt.strategy_id = uuid.uuid4()
        bt.date_range_start = "2023-01-01"
        bt.date_range_end = "2024-12-31"

        strategy = MagicMock()
        strategy.stock_code = "005930"
        strategy.strategy_type = "sma_crossover"
        strategy.parameters = {"fast_period": 10, "slow_period": 30}

        df = pd.DataFrame({
            "open": [100.0] * 200,
            "high": [105.0] * 200,
            "low": [95.0] * 200,
            "close": [100.0] * 200,
            "volume": [1000] * 200,
        }, index=pd.date_range("2023-01-01", periods=200, freq="B"))

        def always_raises(_df, **kwargs):
            raise ValueError("signal generation failed")

        with patch.object(bt_api, "_get_backtest", AsyncMock(return_value=bt)), \
             patch.object(bt_api, "_get_strategy", AsyncMock(return_value=strategy)), \
             patch.object(bt_api, "_fetch_data", AsyncMock(return_value=df)), \
             patch.object(bt_api, "_get_signal_gen", MagicMock(return_value=always_raises)):
            resp = await bt_api.run_cpcv(
                str(bt.id),
                CPCVRequest(n_splits=3),
                db=MagicMock(),
                user=MagicMock(),
            )

        assert resp.validation_status == "미검증"
        assert resp.validation_status != "검증됨"
        assert resp.is_validated is False
        assert resp.score_is_meaningful is False
        assert resp.failed_folds == 3
        assert resp.succeeded_folds == 0
        assert resp.cpcv_score is None
        assert resp.cpcv_score_raw == 0.0
        assert "ALL_FOLDS_FAILED" in resp.reason_codes
