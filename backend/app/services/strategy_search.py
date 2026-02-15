"""Synchronous strategy search service — no Celery/Redis required.

Runs the full pipeline: data fetch → signal generation → optimization →
validation → scoring → DB persistence, using FastAPI BackgroundTasks.
"""

import json
import logging
import uuid
import warnings
from datetime import datetime, timezone
from typing import Any

import numpy as np

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.strategy import Strategy
from app.models.backtest import Backtest
from app.analysis.backtest.engine import run_backtest
from app.analysis.validation.walk_forward import walk_forward_analysis
from app.analysis.validation.monte_carlo import monte_carlo_from_backtest
from app.analysis.validation.out_of_sample import out_of_sample_test
from app.analysis.validation.scoring import score_strategy
from app.analysis.signals.registry import (
    list_signal_generators,
    get_signal_generator,
    get_signal_param_space,
)

warnings.filterwarnings("ignore", category=FutureWarning)
logger = logging.getLogger("able.strategy_search")

# In-memory job store: job_id → {status, progress, step, result, error}
_search_jobs: dict[str, dict[str, Any]] = {}


async def fetch_ohlcv_data(
    stock_code: str,
    data_source: str = "yahoo",
    period: str = "1y",
    date_range_start: str | None = None,
    date_range_end: str | None = None,
) -> "pd.DataFrame | None":
    """Async helper to fetch OHLCV data for a stock.

    Returns a DataFrame with columns [open, high, low, close, volume]
    or None if data is insufficient (< 60 bars).
    """
    import asyncio
    import pandas as pd  # noqa: F811

    from app.integrations.data.factory import get_data_provider

    def _fetch():
        provider = get_data_provider(data_source)
        if date_range_start and date_range_end:
            return provider.get_ohlcv(stock_code, date_range_start, date_range_end)
        return provider.get_ohlcv(stock_code, period=period)

    df = await asyncio.to_thread(_fetch)
    if df is None or df.empty or len(df) < 60:
        return None
    return df


def get_job_status(job_id: str) -> dict | None:
    return _search_jobs.get(job_id)


def _update_job(job_id: str, **kwargs):
    if job_id in _search_jobs:
        _search_jobs[job_id].update(kwargs)


def _build_param_grid(param_space: dict) -> dict:
    """Convert param_space to discrete grid values for grid search."""
    grid = {}
    for name, spec in param_space.items():
        if spec["type"] == "int":
            low, high = spec["low"], spec["high"]
            step = max(1, (high - low) // 4)
            grid[name] = list(range(low, high + 1, step))
        elif spec["type"] == "float":
            low, high = spec["low"], spec["high"]
            grid[name] = [round(low + i * (high - low) / 4, 2) for i in range(5)]
        elif spec["type"] == "categorical":
            grid[name] = spec.get("choices", [])
    return grid


def _sanitize(obj: Any) -> Any:
    """Recursively convert numpy types to native Python for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


async def run_search(
    job_id: str,
    user_id: uuid.UUID,
    stock_code: str,
    date_range_start: str,
    date_range_end: str,
    optimization_method: str,
    data_source: str,
    db: AsyncSession,
):
    """Run the full strategy search pipeline."""
    import asyncio

    _search_jobs[job_id] = {
        "status": "running",
        "progress": 0,
        "step": "initializing",
        "result": None,
        "error": None,
    }

    try:
        # ── Step 0: Resolve stock code ────────────────────────
        from app.integrations.data.yahoo_provider import resolve_stock_code
        resolved_code, resolved_name = resolve_stock_code(stock_code)
        stock_code = resolved_code
        stock_name = resolved_name

        # ── Step 1: Fetch data ──────────────────────────────────
        _update_job(job_id, step="fetching_data", progress=5)
        from app.integrations.data.factory import get_data_provider

        def _fetch():
            provider = get_data_provider(data_source)
            return provider.get_ohlcv(stock_code, date_range_start, date_range_end)

        df = await asyncio.to_thread(_fetch)
        if df.empty or len(df) < 60:
            _update_job(job_id, status="error", error=f"데이터 부족: {len(df)}일")
            return

        logger.info("Fetched %d rows for %s", len(df), stock_code)
        _update_job(job_id, step="optimizing", progress=10)

        # ── Step 2: Run optimization for each signal ────────────
        sig_names = list_signal_generators()
        all_strategies = []
        total_sigs = len(sig_names)

        for idx, sig_name in enumerate(sig_names):
            progress = 10 + int((idx / total_sigs) * 50)
            _update_job(job_id, step=f"optimizing:{sig_name}", progress=progress)

            try:
                sig_gen = get_signal_generator(sig_name)
                param_space = get_signal_param_space(sig_name)
                if not param_space:
                    continue

                def _optimize(gen=sig_gen, ps=param_space):
                    if optimization_method == "genetic":
                        from app.analysis.optimization.genetic import genetic_optimize
                        return genetic_optimize(df, gen, ps, top_n=3)
                    elif optimization_method == "bayesian":
                        from app.analysis.optimization.bayesian import bayesian_optimize
                        return bayesian_optimize(df, gen, ps, n_trials=60, top_n=3)
                    else:
                        from app.analysis.optimization.grid_search import grid_search
                        grid = _build_param_grid(ps)
                        return grid_search(df, gen, grid, top_n=3)

                results = await asyncio.to_thread(_optimize)

                for rank, result in enumerate(results):
                    all_strategies.append({
                        "strategy_type": sig_name,
                        "params": result["params"],
                        "metrics": result["metrics"],
                        "backtest": result.get("backtest"),
                    })
            except Exception as e:
                logger.debug("Optimization failed for %s: %s", sig_name, e)

        if not all_strategies:
            _update_job(job_id, status="error", error="유효한 전략을 찾지 못했습니다")
            return

        # ── Step 3: Select top candidates ───────────────────────
        all_strategies.sort(key=lambda x: x["metrics"].get("sharpe_ratio", 0), reverse=True)
        top_candidates = all_strategies[:8]
        _update_job(job_id, step="validating", progress=65)

        # ── Step 4: Validate + Score + Save ─────────────────────
        saved = []
        for i, strat in enumerate(top_candidates):
            progress = 65 + int((i / len(top_candidates)) * 30)
            _update_job(job_id, step=f"validating:{strat['strategy_type']}", progress=progress)

            try:
                sig_gen = get_signal_generator(strat["strategy_type"])

                # Re-run backtest if not available
                bt = strat.get("backtest")
                if bt is None:
                    def _bt(gen=sig_gen, p=strat["params"]):
                        entry, exit_ = gen(df, **p)
                        return run_backtest(df, entry, exit_)
                    bt = await asyncio.to_thread(_bt)

                # Walk-Forward
                def _wfa(gen=sig_gen, p=strat["params"]):
                    return walk_forward_analysis(df, gen, p, n_splits=5)
                wfa_result = await asyncio.to_thread(_wfa)

                # Monte Carlo
                def _mc(b=bt):
                    return monte_carlo_from_backtest(b, n_simulations=500)
                mc_result = await asyncio.to_thread(_mc)
                mc_score = mc_result.get("mc_score", 0)

                # Out-of-Sample
                def _oos(gen=sig_gen, p=strat["params"]):
                    return out_of_sample_test(df, gen, p)
                oos_result = await asyncio.to_thread(_oos)
                oos_score = oos_result.get("oos_score", 0)

                # Composite score
                composite = score_strategy({
                    **strat["metrics"],
                    "mc_score": mc_score,
                    "oos_score": oos_score,
                    "wfa_score": wfa_result.get("wfa_score", 0),
                }, wfa_result=wfa_result)

                # Sanitize all data for JSON serialization
                params_clean = _sanitize(strat["params"])
                metrics_clean = _sanitize(strat["metrics"])
                vr_clean = _sanitize({
                    "wfa": {k: v for k, v in wfa_result.items() if k != "windows"},
                    "mc": {k: v for k, v in mc_result.items() if k not in ("confidence_bands", "equity_paths")},
                    "oos": {k: v for k, v in oos_result.items() if k not in ("in_sample", "out_of_sample")},
                    "oos_detail": {
                        "in_sample": oos_result.get("in_sample", {}),
                        "out_of_sample": oos_result.get("out_of_sample", {}),
                        "degradation": oos_result.get("degradation", {}),
                    },
                    "backtest": metrics_clean,
                })
                eq_curve = _sanitize(bt.equity_curve) if bt else None
                trade_log = _sanitize(bt.trade_log) if bt else None

                # Save Strategy (upsert: update if same user+type+stock exists)
                existing_result = await db.execute(
                    select(Strategy).where(
                        Strategy.user_id == user_id,
                        Strategy.strategy_type == strat["strategy_type"],
                        Strategy.stock_code == stock_code,
                    )
                )
                existing_strategy = existing_result.scalar_one_or_none()

                if existing_strategy:
                    strategy = existing_strategy
                    strategy.name = f"{strat['strategy_type']}_{stock_code}"
                    strategy.stock_name = stock_name
                    strategy.parameters = params_clean
                    strategy.composite_score = float(composite["total_score"])
                    strategy.validation_results = vr_clean
                    strategy.status = "validated"
                    strategy.entry_rules = {"signal": strat["strategy_type"]}
                    strategy.exit_rules = {"signal": strat["strategy_type"]}
                    strategy.risk_params = {"stop_loss_pct": 3.0, "take_profit_pct": 6.0}
                    # Delete old backtests for this strategy
                    for old_bt in list(strategy.backtests):
                        await db.delete(old_bt)
                    await db.flush()
                else:
                    strategy = Strategy(
                        user_id=user_id,
                        name=f"{strat['strategy_type']}_{stock_code}",
                        stock_code=stock_code,
                        stock_name=stock_name,
                        strategy_type=strat["strategy_type"],
                        indicators=[{"name": strat["strategy_type"]}],
                        parameters=params_clean,
                        entry_rules={"signal": strat["strategy_type"]},
                        exit_rules={"signal": strat["strategy_type"]},
                        risk_params={"stop_loss_pct": 3.0, "take_profit_pct": 6.0},
                        composite_score=float(composite["total_score"]),
                        validation_results=vr_clean,
                        status="validated",
                    )
                    db.add(strategy)
                    await db.flush()

                # Save Backtest
                backtest = Backtest(
                    strategy_id=strategy.id,
                    user_id=user_id,
                    status="completed",
                    parameters=params_clean,
                    date_range_start=df.index[0].date(),
                    date_range_end=df.index[-1].date(),
                    total_return=float(metrics_clean.get("total_return", 0)),
                    annual_return=float(metrics_clean.get("annual_return", 0)),
                    sharpe_ratio=float(metrics_clean.get("sharpe_ratio", 0)),
                    sortino_ratio=float(metrics_clean.get("sortino_ratio", 0)),
                    max_drawdown=float(metrics_clean.get("max_drawdown", 0)),
                    win_rate=float(metrics_clean.get("win_rate", 0)),
                    profit_factor=float(metrics_clean.get("profit_factor", 0)),
                    total_trades=int(metrics_clean.get("total_trades", 0)),
                    calmar_ratio=float(metrics_clean.get("calmar_ratio", 0)),
                    wfa_score=float(wfa_result.get("wfa_score", 0)),
                    mc_score=float(mc_score),
                    oos_score=float(oos_score),
                    equity_curve=eq_curve,
                    trade_log=trade_log,
                    completed_at=datetime.now(timezone.utc),
                )
                db.add(backtest)

                saved.append({
                    "id": str(strategy.id),
                    "name": strategy.name,
                    "strategy_type": strat["strategy_type"],
                    "score": float(composite["total_score"]),
                    "grade": composite["grade"],
                    "total_return": float(metrics_clean.get("total_return", 0)),
                    "sharpe_ratio": float(metrics_clean.get("sharpe_ratio", 0)),
                    "max_drawdown": float(metrics_clean.get("max_drawdown", 0)),
                    "mc_score": float(mc_score),
                    "oos_score": float(oos_score),
                })
            except Exception as e:
                logger.warning("Validation failed for %s: %s", strat["strategy_type"], e)

        await db.commit()

        _update_job(job_id, status="complete", progress=100, step="done", result={
            "strategies_found": len(saved),
            "strategies": saved,
            "stock_code": stock_code,
            "data_rows": len(df),
            "method": optimization_method,
        })
        logger.info("Strategy search complete: %d strategies saved for %s", len(saved), stock_code)

    except Exception as e:
        logger.error("Strategy search failed: %s", e, exc_info=True)
        _update_job(job_id, status="error", error=str(e))
        try:
            await db.rollback()
        except Exception:
            pass
