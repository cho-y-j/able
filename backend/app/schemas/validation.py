"""Schemas for validation API endpoints (Monte Carlo, OOS, CPCV)."""

from pydantic import BaseModel


class MonteCarloRequest(BaseModel):
    n_simulations: int = 1000
    initial_capital: float = 10_000_000


class MonteCarloResponse(BaseModel):
    mc_score: float
    simulations_run: int
    n_trades: int = 0
    statistics: dict = {}
    drawdown_stats: dict = {}
    confidence_bands: dict = {}
    percentiles: dict = {}
    message: str | None = None


class OOSRequest(BaseModel):
    oos_ratio: float = 0.3
    data_source: str = "yahoo"


class OOSResponse(BaseModel):
    oos_score: float
    oos_profitable: bool = False
    in_sample: dict = {}
    out_of_sample: dict = {}
    degradation: dict = {}
    message: str | None = None


class CPCVRequest(BaseModel):
    n_splits: int = 5
    purge_days: int = 5
    data_source: str = "yahoo"


# ── 검증 상태 어휘 (CLAUDE.md 1.3절) ──────────────────────
# `구현됨`/`검증됨`/`반증됨` 은 사람(독립 검수)이 부여한다. API 가 자동으로 부여할 수 있는
# 것은 "이 절차의 출력은 검증 근거가 아니다" 뿐이므로 `미검증` 만 둔다.
VALIDATION_STATUS_UNVERIFIED = "미검증"

# ── CPCV 사유 코드 (Q-002b) ───────────────────────────────
# 기계가 읽는 코드. 사람이 읽는 문장은 CPCVResponse.integrity_message 에 담긴다.
CPCV_REASON_NO_TRAIN_PATH = "NO_TRAIN_PATH"
CPCV_REASON_NOT_COMBINATORIAL = "NOT_COMBINATORIAL"
CPCV_REASON_PURGE_HAS_NO_TARGET = "PURGE_HAS_NO_TARGET"
CPCV_REASON_PARAMS_FITTED_OUTSIDE = "PARAMS_FITTED_OUTSIDE"
CPCV_REASON_NO_FOLDS_EVALUATED = "NO_FOLDS_EVALUATED"
CPCV_REASON_ALL_FOLDS_FAILED = "ALL_FOLDS_FAILED"
CPCV_REASON_SOME_FOLDS_FAILED = "SOME_FOLDS_FAILED"
CPCV_REASON_SENTINEL_ZERO_IN_RAW_MEAN = "SENTINEL_ZERO_IN_RAW_MEAN"
CPCV_REASON_FOLDS_SKIPPED = "FOLDS_SKIPPED"

# 입력과 무관하게 항상 적용되는 구조적 결함 (L-0013, out_of_sample.py:111-184).
CPCV_STRUCTURAL_REASON_CODES: tuple[str, ...] = (
    CPCV_REASON_NO_TRAIN_PATH,
    CPCV_REASON_NOT_COMBINATORIAL,
    CPCV_REASON_PURGE_HAS_NO_TARGET,
    CPCV_REASON_PARAMS_FITTED_OUTSIDE,
)

# 이름 교정: 함수명 변경은 Q-010a 범위이므로 응답 필드로 실제 절차를 밝힌다.
CPCV_PROCEDURE_PERFORMED = "per_block_test_backtest_no_training"
CPCV_PROCEDURE_CLAIMED = "combinatorial_purged_cv"


class CPCVResponse(BaseModel):
    """CPCV 엔드포인트 응답.

    **주의 (Q-002b)**: 이 응답은 검증 통과의 근거가 아니다. 하부 함수
    `analysis/validation/out_of_sample.py:111` 의 `combinatorial_purged_cv` 는
    조합형(combinatorial)도 purge 적용도 아니며 학습 경로가 없다. 점수 필드는
    `validation_status`/`reason_codes` 와 **함께만** 해석해야 한다.

    기존 필드는 삭제하지 않았다. 단 `cpcv_score`/`mean_sharpe`/`std_sharpe` 는
    실패 폴드의 센티넬 0 을 제외해 재계산한 값이며(계산 불가 시 `None`),
    하부 함수가 반환한 원값은 `*_raw` 필드에 그대로 보존한다.
    """

    # ── 기존 필드 (의미 변경분은 위 docstring 참조) ──
    cpcv_score: float | None
    mean_sharpe: float | None = None
    std_sharpe: float | None = None
    positive_folds: int = 0
    total_folds: int = 0
    folds: list[dict] = []

    # ── Q-002b 추가: 정직성 판정 ──
    validation_status: str = VALIDATION_STATUS_UNVERIFIED
    is_validated: bool = False
    score_is_meaningful: bool = False
    reason_codes: list[str] = []
    integrity_message: str | None = None

    # ── Q-002b 추가: 이름과 실제 절차의 불일치 ──
    procedure_performed: str = CPCV_PROCEDURE_PERFORMED
    procedure_claimed_by_name: str = CPCV_PROCEDURE_CLAIMED
    is_combinatorial: bool = False
    purge_applied: bool = False
    train_path_present: bool = False

    # ── Q-002b 추가: 조용한 실패 노출 ──
    requested_splits: int | None = None
    evaluated_folds: int = 0
    succeeded_folds: int = 0
    failed_folds: int = 0
    skipped_folds: int = 0

    # ── Q-002b 추가: 하부 함수 원값 보존 (센티넬 0 포함) ──
    cpcv_score_raw: float | None = None
    mean_sharpe_raw: float | None = None
    std_sharpe_raw: float | None = None


class StrategyCompareResponse(BaseModel):
    strategies: list[dict]
    ranking: list[dict]
