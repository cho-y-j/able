import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.models.backtest import Backtest
from app.models.strategy import Strategy
from app.api.v1.deps import get_current_user
from app.schemas.validation import (
    MonteCarloRequest, MonteCarloResponse,
    OOSRequest, OOSResponse,
    CPCVRequest, CPCVResponse,
    StrategyCompareResponse,
    VALIDATION_STATUS_UNVERIFIED,
    CPCV_STRUCTURAL_REASON_CODES,
    CPCV_PROCEDURE_PERFORMED,
    CPCV_PROCEDURE_CLAIMED,
    CPCV_REASON_ALL_FOLDS_FAILED,
    CPCV_REASON_FOLDS_SKIPPED,
    CPCV_REASON_NO_FOLDS_EVALUATED,
    CPCV_REASON_SENTINEL_ZERO_IN_RAW_MEAN,
    CPCV_REASON_SOME_FOLDS_FAILED,
)

router = APIRouter()


@router.get("/compare", response_model=StrategyCompareResponse)
async def compare_strategies(
    strategy_ids: str = Query(..., description="Comma-separated strategy IDs"),
    include_curves: bool = Query(False, description="Include equity curve data"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Compare multiple strategies side by side using their latest backtests."""
    ids = [uuid.UUID(sid.strip()) for sid in strategy_ids.split(",") if sid.strip()]
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 strategy IDs to compare")
    if len(ids) > 10:
        raise HTTPException(status_code=400, detail="Max 10 strategies for comparison")

    strategies = []
    for sid in ids:
        result = await db.execute(
            select(Strategy).where(Strategy.id == sid, Strategy.user_id == user.id)
        )
        s = result.scalar_one_or_none()
        if not s:
            continue

        bt_result = await db.execute(
            select(Backtest)
            .where(Backtest.strategy_id == sid, Backtest.status == "completed")
            .order_by(Backtest.created_at.desc())
            .limit(1)
        )
        bt = bt_result.scalar_one_or_none()

        entry = {
            "strategy_id": str(s.id),
            "name": s.name,
            "stock_code": s.stock_code,
            "strategy_type": s.strategy_type,
            "composite_score": s.composite_score,
            "status": s.status,
        }
        if bt:
            entry["backtest"] = {
                "id": str(bt.id),
                "total_return": bt.total_return,
                "annual_return": bt.annual_return,
                "sharpe_ratio": bt.sharpe_ratio,
                "sortino_ratio": bt.sortino_ratio,
                "max_drawdown": bt.max_drawdown,
                "win_rate": bt.win_rate,
                "profit_factor": bt.profit_factor,
                "calmar_ratio": bt.calmar_ratio,
                "wfa_score": bt.wfa_score,
                "mc_score": bt.mc_score,
                "oos_score": bt.oos_score,
            }
            if include_curves and bt.equity_curve:
                entry["backtest"]["equity_curve"] = bt.equity_curve
                entry["backtest"]["date_range_start"] = str(bt.date_range_start)
        strategies.append(entry)

    ranked = sorted(strategies, key=lambda x: x.get("composite_score") or 0, reverse=True)
    ranking = [
        {"rank": i + 1, "strategy_id": s["strategy_id"], "name": s["name"], "score": s.get("composite_score")}
        for i, s in enumerate(ranked)
    ]

    return StrategyCompareResponse(strategies=strategies, ranking=ranking)


@router.get("/{backtest_id}")
async def get_backtest(
    backtest_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Backtest).where(
            Backtest.id == uuid.UUID(backtest_id),
            Backtest.user_id == user.id,
        )
    )
    bt = result.scalar_one_or_none()
    if not bt:
        raise HTTPException(status_code=404, detail="Backtest not found")

    return {
        "id": str(bt.id),
        "strategy_id": str(bt.strategy_id),
        "status": bt.status,
        "date_range_start": str(bt.date_range_start),
        "date_range_end": str(bt.date_range_end),
        "metrics": {
            "total_return": bt.total_return,
            "annual_return": bt.annual_return,
            "sharpe_ratio": bt.sharpe_ratio,
            "sortino_ratio": bt.sortino_ratio,
            "max_drawdown": bt.max_drawdown,
            "win_rate": bt.win_rate,
            "profit_factor": bt.profit_factor,
            "total_trades": bt.total_trades,
            "calmar_ratio": bt.calmar_ratio,
        },
        "validation": {
            "wfa_score": bt.wfa_score,
            "oos_score": bt.oos_score,
            "mc_score": bt.mc_score,
        },
        "equity_curve": bt.equity_curve,
        "trade_log": bt.trade_log,
        "error_message": bt.error_message,
    }


@router.get("/{backtest_id}/equity-curve")
async def get_equity_curve(
    backtest_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Backtest.equity_curve).where(
            Backtest.id == uuid.UUID(backtest_id),
            Backtest.user_id == user.id,
        )
    )
    curve = result.scalar_one_or_none()
    if curve is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return {"equity_curve": curve}


@router.post("/{backtest_id}/monte-carlo", response_model=MonteCarloResponse)
async def run_monte_carlo(
    backtest_id: str,
    req: MonteCarloRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run Monte Carlo simulation on a completed backtest's trade log."""
    bt = await _get_backtest(db, user, backtest_id)

    if not bt.trade_log:
        raise HTTPException(status_code=400, detail="Backtest has no trade log")

    trade_returns = [t.get("pnl_percent", 0) for t in bt.trade_log]
    if len(trade_returns) < 5:
        raise HTTPException(status_code=400, detail="Need at least 5 trades for Monte Carlo")

    from app.analysis.validation.monte_carlo import monte_carlo_simulation
    result = monte_carlo_simulation(
        trade_returns,
        n_simulations=req.n_simulations,
        initial_capital=req.initial_capital,
    )

    # Update stored mc_score
    bt.mc_score = result.get("mc_score", 0)
    await db.flush()

    return MonteCarloResponse(**result)


@router.post("/{backtest_id}/oos-validate", response_model=OOSResponse)
async def run_oos_validation(
    backtest_id: str,
    req: OOSRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run Out-of-Sample validation on a backtest's strategy."""
    bt = await _get_backtest(db, user, backtest_id)
    strategy = await _get_strategy(db, user, str(bt.strategy_id))

    df = await _fetch_data(
        strategy.stock_code,
        str(bt.date_range_start).replace("-", ""),
        str(bt.date_range_end).replace("-", ""),
        req.data_source,
    )

    signal_gen = _get_signal_gen(strategy)
    from app.analysis.validation.out_of_sample import out_of_sample_test
    result = out_of_sample_test(df, signal_gen, strategy.parameters, oos_ratio=req.oos_ratio)

    bt.oos_score = result.get("oos_score", 0)
    await db.flush()

    return OOSResponse(**result)


@router.post("/{backtest_id}/cpcv", response_model=CPCVResponse)
async def run_cpcv(
    backtest_id: str,
    req: CPCVRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run the procedure currently named `combinatorial_purged_cv` — **not a validation**.

    이 엔드포인트는 `미검증` 상태와 사유 코드를 함께 반환한다. 하부 함수의 결함은
    `_assess_cpcv` docstring 에 파일:행과 함께 적어 두었다. 알고리즘 재작성은 Q-010a 다.
    """
    bt = await _get_backtest(db, user, backtest_id)
    strategy = await _get_strategy(db, user, str(bt.strategy_id))

    df = await _fetch_data(
        strategy.stock_code,
        str(bt.date_range_start).replace("-", ""),
        str(bt.date_range_end).replace("-", ""),
        req.data_source,
    )

    signal_gen = _get_signal_gen(strategy)
    from app.analysis.validation.out_of_sample import combinatorial_purged_cv
    raw = combinatorial_purged_cv(
        df, signal_gen, strategy.parameters,
        n_splits=req.n_splits, purge_days=req.purge_days,
    )

    # 하부 함수의 출력을 그대로 반환하지 않는다. Q-002b 참조.
    return CPCVResponse(**_assess_cpcv(raw, requested_splits=req.n_splits))


# ── Helpers ──────────────────────────────────────────────

def _cpcv_fold_failed(fold: dict) -> bool:
    """실패 폴드 판정.

    `out_of_sample.py:162-168` 은 예외를 삼키고 `{"sharpe_ratio": 0, "error": True}` 를
    기록한다. 즉 실패 폴드의 0 은 측정값이 아니라 센티넬이다.
    """
    return bool(fold.get("error")) or "sharpe_ratio" not in fold


def _assess_cpcv(raw: dict, requested_splits: int) -> dict:
    """비작동 CPCV 결과에 명시적 `미검증` 판정을 붙인다 (Q-002b).

    하부 함수 `analysis/validation/out_of_sample.py:111-184` 의
    `combinatorial_purged_cv` 는 이름이 약속하는 절차를 수행하지 않는다 (L-0013):

    1. **학습 경로가 없다** — `train_mask`(:139) `purge_start`(:140) `purge_end`(:141)
       `train_data`(:144) 가 전부 죽은 계산이고, 소비되는 것은 `test_data`(:145) 뿐이다.
       purge 가 "미적용"이 아니라 적용 대상 자체가 없다.
    2. **조합형이 아니다** — `:134` 는 반복당 테스트 그룹 1개만 만들어 경로가 `n_splits` 개다.
       AFML CPCV 는 k>1 로 `C(N,k)` 분할과 `k·C(N,k)/N` 경로를 만든다.
    3. **모든 예외를 삼킨다** — `:162-168` 이 실패 폴드를 `sharpe_ratio: 0` 센티넬로 기록하고
       `:179` 의 `mean_sharpe` 평균에 섞는다. 전량 실패해도 `cpcv_score: 0.0` 이 나온다.
    4. **누출을 탐지할 수 없다** — 모든 폴드가 같은 `params`(:151) 를 쓰고, 그 값은 이미 다른
       곳에서 적합된 `strategy.parameters` 다. 누출은 이 함수 밖에서 일어난다.

    `out_of_sample.py` 는 수정하지 않는다(Q-010a 범위). 여기서는 결과를 **검사해** 판정하고,
    센티넬 0 을 제외한 값을 재계산한다.
    """
    import statistics

    folds = [f for f in (raw.get("folds") or []) if isinstance(f, dict)]
    failed = [f for f in folds if _cpcv_fold_failed(f)]
    succeeded = [f for f in folds if not _cpcv_fold_failed(f)]
    evaluated = len(folds)
    skipped = max(0, int(requested_splits) - evaluated)

    reason_codes = list(CPCV_STRUCTURAL_REASON_CODES)
    if evaluated == 0:
        reason_codes.append(CPCV_REASON_NO_FOLDS_EVALUATED)
    elif not succeeded:
        reason_codes.append(CPCV_REASON_ALL_FOLDS_FAILED)
    elif failed:
        reason_codes.append(CPCV_REASON_SOME_FOLDS_FAILED)
    if failed:
        # 원값 평균은 센티넬 0 에 오염되어 있다. 재계산값과 구분해 노출한다.
        reason_codes.append(CPCV_REASON_SENTINEL_ZERO_IN_RAW_MEAN)
    if skipped:
        reason_codes.append(CPCV_REASON_FOLDS_SKIPPED)

    # 센티넬 0 을 제외한 재계산. 성공 폴드가 없으면 수치를 만들지 않고 None 을 반환한다.
    sharpes = [float(f["sharpe_ratio"]) for f in succeeded]
    if sharpes:
        positive = sum(1 for s in sharpes if s > 0)
        clean_score = round(positive / len(sharpes) * 100, 2)
        clean_mean = round(statistics.fmean(sharpes), 4)
        clean_std = round(statistics.pstdev(sharpes), 4)
    else:
        positive = 0
        clean_score = None
        clean_mean = None
        clean_std = None

    parts = [
        "이 결과는 검증 근거가 아니다 (Q-002b).",
        f"엔드포인트 이름이 주장하는 '{CPCV_PROCEDURE_CLAIMED}' 는 실제로 수행되지 않았다 — "
        "학습 경로가 없고(train_data 미소비), 조합형이 아니며(경로 수 = n_splits), "
        "purge 를 적용할 대상이 없고, 파라미터는 이 절차 밖에서 적합되었다.",
        f"실제 수행 절차: {CPCV_PROCEDURE_PERFORMED}.",
    ]
    if evaluated == 0:
        parts.append("평가된 폴드가 0개다. 어떤 것도 측정되지 않았다.")
    elif not succeeded:
        parts.append(
            f"평가된 폴드 {evaluated}개가 **전부 실패**했다. "
            "하부 함수의 점수 0.0 은 성과가 아니라 실패 센티넬의 산물이다."
        )
    elif failed:
        parts.append(
            f"평가된 폴드 {evaluated}개 중 {len(failed)}개가 실패했다. "
            f"점수·평균은 성공 {len(succeeded)}개만으로 재계산했다."
        )
    if skipped:
        parts.append(f"요청 {requested_splits}개 중 {skipped}개는 데이터 부족으로 건너뛰었다.")
    parts.append("이 점수를 전략 승인·활성화 근거로 사용하지 마라 (ADR-0001).")

    assessed = dict(raw)
    assessed.update({
        # 센티넬 0 을 제외한 재계산값
        "cpcv_score": clean_score,
        "mean_sharpe": clean_mean,
        "std_sharpe": clean_std,
        "positive_folds": positive,
        "total_folds": evaluated,
        "folds": folds,
        # 하부 함수 원값 보존
        "cpcv_score_raw": raw.get("cpcv_score"),
        "mean_sharpe_raw": raw.get("mean_sharpe"),
        "std_sharpe_raw": raw.get("std_sharpe"),
        # 판정
        "validation_status": VALIDATION_STATUS_UNVERIFIED,
        "is_validated": False,
        "score_is_meaningful": False,
        "reason_codes": reason_codes,
        "integrity_message": " ".join(parts),
        "procedure_performed": CPCV_PROCEDURE_PERFORMED,
        "procedure_claimed_by_name": CPCV_PROCEDURE_CLAIMED,
        "is_combinatorial": False,
        "purge_applied": False,
        "train_path_present": False,
        # 조용한 실패 노출
        "requested_splits": int(requested_splits),
        "evaluated_folds": evaluated,
        "succeeded_folds": len(succeeded),
        "failed_folds": len(failed),
        "skipped_folds": skipped,
    })
    return assessed



async def _get_backtest(db: AsyncSession, user: User, backtest_id: str) -> Backtest:
    result = await db.execute(
        select(Backtest).where(
            Backtest.id == uuid.UUID(backtest_id),
            Backtest.user_id == user.id,
            Backtest.status == "completed",
        )
    )
    bt = result.scalar_one_or_none()
    if not bt:
        raise HTTPException(status_code=404, detail="Completed backtest not found")
    return bt


async def _get_strategy(db: AsyncSession, user: User, strategy_id: str) -> Strategy:
    result = await db.execute(
        select(Strategy).where(
            Strategy.id == uuid.UUID(strategy_id),
            Strategy.user_id == user.id,
        )
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return s


async def _fetch_data(stock_code: str, start_date: str, end_date: str, data_source: str = "yahoo"):
    """Fetch OHLCV data in a thread (blocking I/O)."""
    import asyncio
    from app.integrations.data.factory import get_data_provider

    provider = get_data_provider(data_source)

    def _fetch():
        return provider.get_ohlcv(stock_code, start_date, end_date)

    df = await asyncio.to_thread(_fetch)
    if df.empty or len(df) < 60:
        raise HTTPException(status_code=400, detail=f"Insufficient data: {len(df)} rows")
    return df


def _get_signal_gen(strategy: Strategy):
    """Get signal generator for a strategy."""
    from app.analysis.indicators.registry import get_signal_generator
    return get_signal_generator(
        strategy.parameters,
        name=strategy.strategy_type if strategy.strategy_type else None,
    )
