"""AI Analysis API endpoints."""

import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.models.strategy import Strategy
from app.models.backtest import Backtest
from app.api.v1.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory analysis job store
_analysis_jobs: dict[str, dict[str, Any]] = {}


class AnalysisRequest(BaseModel):
    stock_code: str
    date_range_start: str = "2024-01-01"
    date_range_end: str = "2025-12-31"
    include_macro: bool = True
    data_source: str = "yahoo"


class ParameterUpdateRequest(BaseModel):
    parameters: dict
    risk_params: dict | None = None


@router.post("/ai-report")
async def create_ai_report(
    req: AnalysisRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start an AI analysis report for a stock.

    Pipeline: Data Fetch → Feature Store → Fact Sheet → DeepSeek → Report
    """
    # Get user's LLM API key
    api_key = await _get_user_llm_key(user.id, db)
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="LLM API 키가 설정되지 않았습니다. 설정 페이지에서 등록하세요.",
        )

    job_id = str(uuid.uuid4())
    _analysis_jobs[job_id] = {
        "status": "running",
        "progress": 0,
        "result": None,
        "error": None,
    }

    async def _run():
        try:
            _analysis_jobs[job_id]["progress"] = 10

            # Fetch data
            from app.integrations.data.factory import get_data_provider
            from app.integrations.data.yahoo_provider import resolve_stock_code

            resolved_code, resolved_name = resolve_stock_code(req.stock_code)

            def _fetch():
                provider = get_data_provider(req.data_source)
                return provider.get_ohlcv(resolved_code, req.date_range_start, req.date_range_end)

            df = await asyncio.to_thread(_fetch)
            if df.empty or len(df) < 30:
                _analysis_jobs[job_id].update(
                    status="error",
                    error=f"데이터 부족: {len(df)}일 (최소 30일 필요)",
                )
                return

            _analysis_jobs[job_id]["progress"] = 30

            # Run full analysis
            from app.services.ai_analyst import run_full_analysis

            result = await run_full_analysis(
                stock_code=resolved_code,
                stock_name=resolved_name,
                df=df,
                api_key=api_key,
                include_macro=req.include_macro,
            )

            _analysis_jobs[job_id].update(
                status="complete",
                progress=100,
                result=result,
            )

        except Exception as e:
            logger.error("AI analysis failed: %s", e, exc_info=True)
            _analysis_jobs[job_id].update(status="error", error=str(e))

    asyncio.create_task(_run())

    return {"job_id": job_id, "status": "running"}


@router.get("/ai-report/{job_id}")
async def get_ai_report_status(job_id: str):
    """Poll AI analysis report progress."""
    job = _analysis_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "result": job.get("result"),
        "error": job.get("error"),
    }


@router.post("/strategies/{strategy_id}/rebacktest")
async def rebacktest_strategy(
    strategy_id: str,
    req: ParameterUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update strategy parameters and re-run backtest.

    This allows users to tweak parameters and immediately see the impact.
    """
    result = await db.execute(
        select(Strategy).where(
            Strategy.id == uuid.UUID(strategy_id),
            Strategy.user_id == user.id,
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Update parameters
    strategy.parameters = req.parameters
    if req.risk_params:
        strategy.risk_params = req.risk_params

    # Re-run backtest with new parameters
    try:
        from app.integrations.data.factory import get_data_provider
        from app.analysis.backtest.engine import run_backtest
        from app.analysis.signals.registry import get_signal_generator
        from app.analysis.validation.scoring import score_strategy
        from app.analysis.validation.walk_forward import walk_forward_analysis
        from app.analysis.validation.monte_carlo import monte_carlo_from_backtest
        from app.analysis.validation.out_of_sample import out_of_sample_test
        from app.services.strategy_search import _sanitize

        # Get latest backtest date range
        bt_result = await db.execute(
            select(Backtest)
            .where(Backtest.strategy_id == strategy.id)
            .order_by(Backtest.created_at.desc())
            .limit(1)
        )
        old_bt = bt_result.scalar_one_or_none()
        start = str(old_bt.date_range_start) if old_bt else "2024-01-01"
        end = str(old_bt.date_range_end) if old_bt else "2025-12-31"

        # Fetch data and run backtest
        def _run():
            provider = get_data_provider("yahoo")
            df = provider.get_ohlcv(strategy.stock_code, start, end)
            if df.empty or len(df) < 30:
                raise ValueError(f"데이터 부족: {len(df)}일")

            sig_gen = get_signal_generator(strategy.strategy_type)
            entry, exit_ = sig_gen(df, **req.parameters)
            bt = run_backtest(df, entry, exit_)

            # Validation
            wfa = walk_forward_analysis(df, sig_gen, req.parameters, n_splits=5)
            mc = monte_carlo_from_backtest(bt, n_simulations=500)
            oos = out_of_sample_test(df, sig_gen, req.parameters)

            return df, bt, wfa, mc, oos

        df, bt, wfa, mc, oos = await asyncio.to_thread(_run)

        metrics = _sanitize(bt.metrics)
        mc_score = float(mc.get("mc_score", 0))
        oos_score = float(oos.get("oos_score", 0))
        wfa_score = float(wfa.get("wfa_score", 0))

        composite = score_strategy({
            **metrics,
            "mc_score": mc_score,
            "oos_score": oos_score,
            "wfa_score": wfa_score,
        }, wfa_result=wfa)

        # Update strategy
        strategy.composite_score = float(composite["total_score"])
        vr = _sanitize({
            "wfa": {k: v for k, v in wfa.items() if k != "windows"},
            "mc": {k: v for k, v in mc.items() if k not in ("confidence_bands", "equity_paths")},
            "oos": {k: v for k, v in oos.items() if k not in ("in_sample", "out_of_sample")},
            "oos_detail": {
                "in_sample": oos.get("in_sample", {}),
                "out_of_sample": oos.get("out_of_sample", {}),
                "degradation": oos.get("degradation", {}),
            },
            "backtest": metrics,
        })
        strategy.validation_results = vr

        # Save new backtest
        from datetime import datetime, timezone
        new_bt = Backtest(
            strategy_id=strategy.id,
            user_id=user.id,
            status="completed",
            parameters=_sanitize(req.parameters),
            date_range_start=df.index[0].date(),
            date_range_end=df.index[-1].date(),
            total_return=float(metrics.get("total_return", 0)),
            annual_return=float(metrics.get("annual_return", 0)),
            sharpe_ratio=float(metrics.get("sharpe_ratio", 0)),
            sortino_ratio=float(metrics.get("sortino_ratio", 0)),
            max_drawdown=float(metrics.get("max_drawdown", 0)),
            win_rate=float(metrics.get("win_rate", 0)),
            profit_factor=float(metrics.get("profit_factor", 0)),
            total_trades=int(metrics.get("total_trades", 0)),
            calmar_ratio=float(metrics.get("calmar_ratio", 0)),
            wfa_score=wfa_score,
            mc_score=mc_score,
            oos_score=oos_score,
            equity_curve=_sanitize(bt.equity_curve),
            trade_log=_sanitize(bt.trade_log),
            completed_at=datetime.now(timezone.utc),
        )
        db.add(new_bt)
        await db.flush()

        return {
            "strategy_id": str(strategy.id),
            "parameters": req.parameters,
            "composite_score": strategy.composite_score,
            "grade": composite["grade"],
            "metrics": metrics,
            "validation": {
                "wfa_score": wfa_score,
                "mc_score": mc_score,
                "oos_score": oos_score,
            },
        }

    except Exception as e:
        logger.error("Rebacktest failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"재백테스트 실패: {str(e)}")


@router.get("/strategies/{strategy_id}/param-ranges")
async def get_param_ranges(
    strategy_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get adjustable parameter ranges for a strategy."""
    result = await db.execute(
        select(Strategy).where(
            Strategy.id == uuid.UUID(strategy_id),
            Strategy.user_id == user.id,
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    from app.analysis.signals.registry import get_signal_param_space

    param_space = get_signal_param_space(strategy.strategy_type)
    current_params = strategy.parameters or {}

    ranges = {}
    for name, spec in (param_space or {}).items():
        ranges[name] = {
            "type": spec["type"],
            "current": current_params.get(name),
            "min": spec.get("low"),
            "max": spec.get("high"),
            "choices": spec.get("choices"),
        }

    return {
        "strategy_id": str(strategy.id),
        "strategy_type": strategy.strategy_type,
        "parameters": ranges,
        "current_values": current_params,
        "risk_params": strategy.risk_params,
    }


async def _get_user_llm_key(user_id: uuid.UUID, db: AsyncSession) -> str | None:
    """Get user's decrypted LLM API key."""
    try:
        from app.models.api_key import ApiKey
        from app.core.encryption import decrypt_value

        result = await db.execute(
            select(ApiKey).where(
                ApiKey.user_id == user_id,
                ApiKey.provider == "llm",
                ApiKey.is_active == True,
            )
        )
        key = result.scalar_one_or_none()
        if key and key.api_key:
            return decrypt_value(key.api_key)
    except Exception as e:
        logger.warning("Failed to get LLM key: %s", e)

    # Fallback: check config for DeepSeek key
    from app.config import get_settings
    settings = get_settings()
    return settings.deepseek_api_key or None
