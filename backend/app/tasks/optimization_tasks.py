"""Celery tasks for strategy optimization (long-running)."""

import logging
import uuid
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.tasks.celery_app import celery_app
from app.models.base import Base
from app.models.strategy import Strategy
from app.models.backtest import Backtest
from app.core.encryption import get_vault
from app.models.api_credential import ApiCredential
from app.analysis.indicators.registry import get_signal_generator
from app.analysis.backtest.engine import run_backtest
from app.analysis.validation.walk_forward import walk_forward_analysis
from app.analysis.validation.scoring import score_strategy
from app.integrations.data.factory import get_data_provider

logger = logging.getLogger(__name__)


def _get_sync_db():
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    return Session(engine)


def _fetch_ohlcv_via_provider(
    stock_code: str, start_date: str, end_date: str,
    data_source: str = "yahoo",
    app_key: str = "", app_secret: str = "",
    account_number: str = "", is_paper: bool = True,
) -> pd.DataFrame:
    """Fetch OHLCV data using the DataProvider abstraction."""
    provider = get_data_provider(
        source=data_source,
        app_key=app_key,
        app_secret=app_secret,
        account_number=account_number,
        is_paper=is_paper,
    )
    return provider.get_ohlcv(stock_code, start_date, end_date)


def _fetch_ohlcv_sync(app_key: str, app_secret: str, account_number: str,
                       is_paper: bool, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch OHLCV data synchronously (for Celery tasks) using httpx sync."""
    import httpx
    from app.integrations.kis.constants import (
        PAPER_BASE_URL, REAL_BASE_URL, STOCK_DAILY_PRICE_PATH, TR_ID_DAILY_PRICE,
    )

    base_url = PAPER_BASE_URL if is_paper else REAL_BASE_URL

    # Get access token synchronously
    token_url = f"{base_url}/oauth2/tokenP"
    token_resp = httpx.post(token_url, json={
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": app_secret,
    }, timeout=10.0)
    token_resp.raise_for_status()
    access_token = token_resp.json()["access_token"]

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": TR_ID_DAILY_PRICE,
    }
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code,
        "FID_INPUT_DATE_1": start_date,
        "FID_INPUT_DATE_2": end_date,
        "FID_PERIOD_DIV_CODE": "D",
        "FID_ORG_ADJ_PRC": "0",
    }

    resp = httpx.get(f"{base_url}{STOCK_DAILY_PRICE_PATH}",
                     headers=headers, params=params, timeout=10.0)
    resp.raise_for_status()
    items = resp.json().get("output2", [])

    rows = []
    for item in items:
        if not item.get("stck_bsop_date"):
            continue
        rows.append({
            "date": item["stck_bsop_date"],
            "open": float(item.get("stck_oprc", 0)),
            "high": float(item.get("stck_hgpr", 0)),
            "low": float(item.get("stck_lwpr", 0)),
            "close": float(item.get("stck_clpr", 0)),
            "volume": int(item.get("acml_vol", 0)),
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    return df


def _run_optimizer(df, signal_gen, param_space, method, scoring="sharpe_ratio", top_n=5):
    """Run the chosen optimizer (grid/bayesian/genetic) and return results."""
    if method == "genetic":
        from app.analysis.optimization.genetic import genetic_optimize
        return genetic_optimize(
            df, signal_gen, param_space,
            scoring=scoring, population_size=40, generations=20, top_n=top_n,
        )
    elif method == "bayesian":
        from app.analysis.optimization.bayesian import bayesian_optimize
        return bayesian_optimize(
            df, signal_gen, param_space,
            scoring=scoring, n_trials=80, top_n=top_n,
        )
    else:  # grid
        from app.analysis.optimization.grid_search import grid_search
        # Convert param_space to grid format (sample discrete values)
        grid = {}
        for name, spec in param_space.items():
            if spec["type"] == "int":
                step = max(1, (spec["high"] - spec["low"]) // 4)
                grid[name] = list(range(spec["low"], spec["high"] + 1, step))
            elif spec["type"] == "float":
                step = (spec["high"] - spec["low"]) / 4
                grid[name] = [round(spec["low"] + i * step, 2) for i in range(5)]
            elif spec["type"] == "categorical":
                grid[name] = spec["choices"]
        return grid_search(df, signal_gen, grid, scoring=scoring, top_n=top_n)


def _validate_strategy(df, signal_gen, params, backtest_result):
    """Run Monte Carlo + OOS validation and return scores."""
    mc_score = 0.0
    oos_score = 0.0

    try:
        from app.analysis.validation.monte_carlo import monte_carlo_from_backtest
        mc_result = monte_carlo_from_backtest(backtest_result, n_simulations=500)
        mc_score = mc_result.get("mc_score", 0)
    except Exception as e:
        logger.warning(f"Monte Carlo validation failed: {e}")

    try:
        from app.analysis.validation.out_of_sample import out_of_sample_test
        oos_result = out_of_sample_test(df, signal_gen, params)
        oos_score = oos_result.get("oos_score", 0)
    except Exception as e:
        logger.warning(f"OOS validation failed: {e}")

    return mc_score, oos_score


@celery_app.task(bind=True, name="tasks.run_strategy_search")
def run_strategy_search(self, user_id: str, stock_code: str, date_range_start: str,
                        date_range_end: str, method: str = "grid",
                        signal_generators: list[str] | None = None,
                        data_source: str = "yahoo"):
    """Run strategy search as a background task.

    1. Fetches OHLCV data for the stock via KIS API
    2. Runs optimization across all registered signal generators
    3. Validates top results with WFA + Monte Carlo + OOS
    4. Scores strategies with composite scoring
    5. Saves results to DB
    """
    db = _get_sync_db()
    try:
        self.update_state(state="PROGRESS", meta={"step": "fetching_data", "progress": 5})

        # Fetch OHLCV data via DataProvider
        if data_source == "kis":
            cred = db.query(ApiCredential).filter(
                ApiCredential.user_id == uuid.UUID(user_id),
                ApiCredential.service_type == "kis",
                ApiCredential.is_active == True,
            ).first()

            if not cred:
                return {"status": "error", "message": "No KIS credentials found"}

            vault = get_vault()
            app_key = vault.decrypt(cred.encrypted_key)
            app_secret = vault.decrypt(cred.encrypted_secret)

            df = _fetch_ohlcv_via_provider(
                stock_code, date_range_start, date_range_end,
                data_source="kis",
                app_key=app_key, app_secret=app_secret,
                account_number=cred.account_number, is_paper=cred.is_paper_trading,
            )
        else:
            df = _fetch_ohlcv_via_provider(
                stock_code, date_range_start, date_range_end,
                data_source=data_source,
            )

        if df.empty or len(df) < 60:
            return {"status": "error", "message": f"Insufficient data: {len(df)} rows"}

        self.update_state(state="PROGRESS", meta={"step": "optimizing", "progress": 20})

        # Build signal generator list from registry
        from app.analysis.signals.registry import (
            list_signal_generators as list_signals,
            get_signal_generator as get_signal,
            get_signal_param_space,
        )

        if signal_generators:
            sig_names = signal_generators
        else:
            sig_names = list_signals()

        all_strategies = []
        total_sigs = len(sig_names)

        for idx, sig_name in enumerate(sig_names):
            progress = 20 + int((idx / total_sigs) * 40)
            self.update_state(state="PROGRESS", meta={
                "step": f"optimizing_{sig_name}",
                "progress": progress,
            })

            try:
                sig_gen = get_signal(sig_name)
                param_space = get_signal_param_space(sig_name)
                if not param_space:
                    continue

                results = _run_optimizer(df, sig_gen, param_space, method, top_n=3)

                for rank, result in enumerate(results):
                    all_strategies.append({
                        "strategy_type": sig_name,
                        "signal_generator": sig_gen,
                        "params": result["params"],
                        "metrics": result["metrics"],
                        "backtest": result.get("backtest"),
                        "rank": rank + 1,
                    })
            except Exception as e:
                logger.warning(f"Optimization failed for {sig_name}: {e}")

        if not all_strategies:
            return {"status": "error", "message": "No viable strategies found"}

        # Sort by scoring metric and take top candidates
        all_strategies.sort(
            key=lambda x: x["metrics"].get("sharpe_ratio", 0), reverse=True,
        )
        top_candidates = all_strategies[:8]

        self.update_state(state="PROGRESS", meta={"step": "validating", "progress": 65})

        # Validate + score + save top strategies
        saved_strategies = []
        for i, strat in enumerate(top_candidates):
            progress = 65 + int((i / len(top_candidates)) * 30)
            self.update_state(state="PROGRESS", meta={
                "step": f"validating_{strat['strategy_type']}",
                "progress": progress,
            })

            try:
                sig_gen = strat["signal_generator"]

                # Walk-Forward Analysis
                wfa_result = walk_forward_analysis(df, sig_gen, strat["params"])

                # Re-run full backtest if not available (for MC validation)
                bt = strat.get("backtest")
                if bt is None:
                    entry_s, exit_s = sig_gen(df, **strat["params"])
                    bt = run_backtest(df, entry_s, exit_s)

                # Monte Carlo + OOS validation
                mc_score, oos_score = _validate_strategy(
                    df, sig_gen, strat["params"], bt,
                )

                # Composite scoring including MC and OOS
                composite = score_strategy({
                    **strat["metrics"],
                    "mc_score": mc_score,
                    "oos_score": oos_score,
                    "wfa_score": wfa_result.get("wfa_score", 0),
                })

                # Save to DB
                strategy = Strategy(
                    user_id=uuid.UUID(user_id),
                    name=f"{strat['strategy_type']}_{stock_code}",
                    stock_code=stock_code,
                    strategy_type=strat["strategy_type"],
                    indicators=[strat["strategy_type"]],
                    parameters=strat["params"],
                    entry_rules={"type": strat["strategy_type"]},
                    exit_rules={"type": "default"},
                    risk_params={"stop_loss_pct": 3.0, "take_profit_pct": 6.0},
                    composite_score=composite["total_score"],
                    validation_results={
                        "wfa": wfa_result,
                        "backtest": strat["metrics"],
                        "mc_score": mc_score,
                        "oos_score": oos_score,
                    },
                    status="validated",
                )
                db.add(strategy)
                db.flush()

                # Save backtest result
                backtest = Backtest(
                    strategy_id=strategy.id,
                    user_id=uuid.UUID(user_id),
                    status="completed",
                    parameters=strat["params"],
                    date_range_start=df.index[0].date(),
                    date_range_end=df.index[-1].date(),
                    total_trades=strat["metrics"].get("total_trades", 0),
                    win_rate=strat["metrics"].get("win_rate", 0),
                    sharpe_ratio=strat["metrics"].get("sharpe_ratio", 0),
                    sortino_ratio=strat["metrics"].get("sortino_ratio", 0),
                    max_drawdown=strat["metrics"].get("max_drawdown", 0),
                    annual_return=strat["metrics"].get("annual_return", 0),
                    profit_factor=strat["metrics"].get("profit_factor", 0),
                    calmar_ratio=strat["metrics"].get("calmar_ratio", 0),
                    total_return=strat["metrics"].get("total_return", 0),
                    wfa_score=wfa_result.get("wfa_score", 0),
                    mc_score=mc_score,
                    oos_score=oos_score,
                    equity_curve=bt.equity_curve if bt else None,
                    trade_log=bt.trade_log if bt else None,
                )
                db.add(backtest)

                saved_strategies.append({
                    "id": str(strategy.id),
                    "name": strategy.name,
                    "score": composite["total_score"],
                    "grade": composite["grade"],
                    "mc_score": mc_score,
                    "oos_score": oos_score,
                })

            except Exception as e:
                logger.warning(f"Validation failed for strategy: {e}")

        db.commit()

        self.update_state(state="PROGRESS", meta={"step": "complete", "progress": 100})
        return {
            "status": "complete",
            "strategies_found": len(saved_strategies),
            "strategies": saved_strategies,
            "method": method,
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Strategy search failed: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(bind=True, name="tasks.run_backtest")
def run_backtest_task(self, user_id: str, strategy_id: str, data_source: str = "yahoo"):
    """Run a single backtest as a background task."""
    db = _get_sync_db()
    try:
        self.update_state(state="PROGRESS", meta={"step": "loading_strategy", "progress": 10})

        strategy = db.query(Strategy).filter(
            Strategy.id == uuid.UUID(strategy_id),
            Strategy.user_id == uuid.UUID(user_id),
        ).first()

        if not strategy:
            return {"status": "error", "message": "Strategy not found"}

        self.update_state(state="PROGRESS", meta={"step": "fetching_data", "progress": 30})

        # Fetch data via DataProvider
        start_date = "2023-01-01"
        end_date = datetime.now().strftime("%Y-%m-%d")

        if data_source == "kis":
            cred = db.query(ApiCredential).filter(
                ApiCredential.user_id == uuid.UUID(user_id),
                ApiCredential.service_type == "kis",
                ApiCredential.is_active == True,
            ).first()

            if not cred:
                return {"status": "error", "message": "No KIS credentials found"}

            vault = get_vault()
            app_key = vault.decrypt(cred.encrypted_key)
            app_secret = vault.decrypt(cred.encrypted_secret)

            df = _fetch_ohlcv_via_provider(
                strategy.stock_code, start_date, end_date,
                data_source="kis",
                app_key=app_key, app_secret=app_secret,
                account_number=cred.account_number, is_paper=cred.is_paper_trading,
            )
        else:
            df = _fetch_ohlcv_via_provider(
                strategy.stock_code, start_date, end_date,
                data_source=data_source,
            )

        if df.empty:
            return {"status": "error", "message": "No OHLCV data"}

        self.update_state(state="PROGRESS", meta={"step": "running_backtest", "progress": 50})

        # Try to use signal registry first, then legacy detection
        signal_gen = get_signal_generator(
            strategy.parameters,
            name=strategy.strategy_type if strategy.strategy_type else None,
        )
        entry_signals, exit_signals = signal_gen(df, **strategy.parameters)
        result = run_backtest(df, entry_signals, exit_signals)

        self.update_state(state="PROGRESS", meta={"step": "validating", "progress": 70})

        # Run MC + OOS validation
        mc_score, oos_score = _validate_strategy(
            df, signal_gen, strategy.parameters, result,
        )

        self.update_state(state="PROGRESS", meta={"step": "scoring", "progress": 85})

        composite = score_strategy({
            "total_return": result.total_return,
            "annual_return": result.annual_return,
            "sharpe_ratio": result.sharpe_ratio,
            "sortino_ratio": result.sortino_ratio,
            "max_drawdown": result.max_drawdown,
            "win_rate": result.win_rate,
            "profit_factor": result.profit_factor,
            "calmar_ratio": result.calmar_ratio,
            "mc_score": mc_score,
            "oos_score": oos_score,
        })

        # Save results
        backtest = Backtest(
            strategy_id=strategy.id,
            user_id=uuid.UUID(user_id),
            status="completed",
            parameters=strategy.parameters,
            date_range_start=df.index[0].date(),
            date_range_end=df.index[-1].date(),
            total_trades=result.total_trades,
            win_rate=result.win_rate,
            sharpe_ratio=result.sharpe_ratio,
            sortino_ratio=result.sortino_ratio,
            max_drawdown=result.max_drawdown,
            annual_return=result.annual_return,
            profit_factor=result.profit_factor,
            calmar_ratio=result.calmar_ratio,
            total_return=result.total_return,
            wfa_score=0,
            mc_score=mc_score,
            oos_score=oos_score,
            equity_curve=result.equity_curve,
            trade_log=result.trade_log,
        )
        db.add(backtest)

        strategy.composite_score = composite["total_score"]
        db.commit()

        self.update_state(state="PROGRESS", meta={"step": "complete", "progress": 100})
        return {
            "status": "complete",
            "backtest_id": str(backtest.id),
            "score": composite["total_score"],
            "grade": composite["grade"],
            "mc_score": mc_score,
            "oos_score": oos_score,
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Backtest failed: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
