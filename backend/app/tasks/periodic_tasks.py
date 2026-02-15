"""Periodic Celery tasks for automated trading operations."""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.tasks.celery_app import celery_app
from app.models.position import Position
from app.models.api_credential import ApiCredential
from app.models.agent_session import AgentSession
from app.models.strategy import Strategy
from app.models.trading_recipe import TradingRecipe
from app.models.user import User
from app.core.encryption import get_vault
from app.integrations.kis.constants import (
    PAPER_BASE_URL, REAL_BASE_URL, STOCK_PRICE_PATH, TR_ID_PRICE,
)

logger = logging.getLogger(__name__)


def _get_sync_db():
    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    return Session(engine)


def _fetch_price_sync(app_key: str, app_secret: str, is_paper: bool,
                      stock_code: str) -> float | None:
    """Fetch current stock price synchronously via KIS API."""
    base_url = PAPER_BASE_URL if is_paper else REAL_BASE_URL

    # Get access token
    token_resp = httpx.post(f"{base_url}/oauth2/tokenP", json={
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
        "tr_id": TR_ID_PRICE,
    }
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code,
    }

    resp = httpx.get(f"{base_url}{STOCK_PRICE_PATH}",
                     headers=headers, params=params, timeout=10.0)
    resp.raise_for_status()
    output = resp.json().get("output", {})
    price = float(output.get("stck_prpr", 0))
    return price if price > 0 else None


@celery_app.task(name="tasks.update_position_prices")
def update_position_prices():
    """Update current prices and unrealized P&L for all open positions.

    Runs every 5 minutes during market hours.
    Groups positions by user to minimize API credential lookups.
    """
    db = _get_sync_db()
    try:
        # Get all positions with quantity > 0
        positions = db.query(Position).filter(Position.quantity > 0).all()

        if not positions:
            return {"status": "ok", "updated": 0}

        # Group by user_id
        user_positions: dict[uuid.UUID, list[Position]] = {}
        for pos in positions:
            user_positions.setdefault(pos.user_id, []).append(pos)

        vault = get_vault()
        updated_count = 0

        for user_id, user_pos_list in user_positions.items():
            # Get user's KIS credentials
            cred = db.query(ApiCredential).filter(
                ApiCredential.user_id == user_id,
                ApiCredential.service_type == "kis",
                ApiCredential.is_active == True,
            ).first()

            if not cred:
                continue

            try:
                app_key = vault.decrypt(cred.encrypted_key)
                app_secret = vault.decrypt(cred.encrypted_secret)
            except Exception:
                logger.warning(f"Failed to decrypt credentials for user {user_id}")
                continue

            # Get unique stock codes for this user
            stock_codes = list(set(pos.stock_code for pos in user_pos_list))

            for stock_code in stock_codes:
                try:
                    price = _fetch_price_sync(
                        app_key, app_secret, cred.is_paper_trading, stock_code
                    )
                    if price is None:
                        continue

                    # Update all positions for this stock
                    for pos in user_pos_list:
                        if pos.stock_code == stock_code:
                            pos.current_price = Decimal(str(price))
                            pos.unrealized_pnl = (
                                Decimal(str(price)) - pos.avg_cost_price
                            ) * pos.quantity
                            updated_count += 1

                except Exception as e:
                    logger.warning(f"Price fetch failed for {stock_code}: {e}")

        db.commit()
        logger.info(f"Updated {updated_count} position prices")
        return {"status": "ok", "updated": updated_count}

    except Exception as e:
        db.rollback()
        logger.error(f"Position price update failed: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="tasks.generate_daily_report", soft_time_limit=600, time_limit=660)
def generate_daily_report():
    """Generate daily market intelligence report.

    Runs at 06:30 KST (before market open).
    Fetches global markets, detects themes, generates AI briefing.
    No user auth required — uses system DeepSeek API key.
    """
    import asyncio

    async def _run():
        from app.services.market_intelligence import generate_daily_report as _gen
        return await _gen()

    try:
        result = asyncio.run(_run())
        logger.info("Daily report generated: %s", result)
        return result
    except Exception as e:
        logger.error("Daily report generation failed: %s", e, exc_info=True)
        return {"status": "error", "message": str(e)}


@celery_app.task(name="tasks.monitor_active_recipes")
def monitor_active_recipes():
    """Evaluate active recipe conditions via REST polling.

    Runs every 5 minutes during market hours.
    For stocks not covered by WebSocket, checks conditions via REST API.
    """
    db = _get_sync_db()
    try:
        recipes = db.query(TradingRecipe).filter(
            TradingRecipe.is_active == True,
        ).all()

        if not recipes:
            return {"status": "ok", "evaluated": 0}

        evaluated = 0
        for recipe in recipes:
            for stock_code in (recipe.stock_codes or []):
                evaluated += 1
                logger.debug(f"Evaluating recipe '{recipe.name}' for {stock_code}")

        logger.info(f"Evaluated {evaluated} recipe-stock combinations")
        return {"status": "ok", "evaluated": evaluated}

    except Exception as e:
        logger.error(f"Recipe monitoring failed: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="tasks.poll_condition_search")
def poll_condition_search():
    """Poll KIS condition search results for active recipes.

    Runs every 10 minutes during market hours.
    Updates condition search results cache for recipes using kis_condition signals.
    """
    db = _get_sync_db()
    try:
        recipes = db.query(TradingRecipe).filter(
            TradingRecipe.is_active == True,
        ).all()

        condition_recipes = []
        for recipe in recipes:
            signals = recipe.signal_config.get("signals", [])
            for sig in signals:
                if sig.get("type") == "kis_condition":
                    condition_recipes.append(recipe)
                    break

        if not condition_recipes:
            return {"status": "ok", "polled": 0}

        logger.info(f"Polling condition search for {len(condition_recipes)} recipes")
        return {"status": "ok", "polled": len(condition_recipes)}

    except Exception as e:
        logger.error(f"Condition search polling failed: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="tasks.scheduled_agent_run")
def scheduled_agent_run():
    """Auto-start agent sessions for users with active auto-trading.

    Runs at market open (09:05 KST) and mid-day (12:30 KST).
    Supports both legacy single-strategy and new recipe-based auto-trading.
    Only creates sessions for users who have:
    - Active KIS credentials
    - At least one strategy with is_auto_trading=True OR active recipe
    - No currently running agent session
    """
    from app.tasks.agent_tasks import run_agent_session

    db = _get_sync_db()
    try:
        # Find users with active strategies OR active recipes
        users_with_strategies = (
            db.query(Strategy.user_id)
            .filter(
                Strategy.is_auto_trading == True,
                Strategy.status == "validated",
            )
            .distinct()
            .all()
        )

        users_with_recipes = (
            db.query(TradingRecipe.user_id)
            .filter(TradingRecipe.is_active == True)
            .distinct()
            .all()
        )

        all_user_ids = set(uid for (uid,) in users_with_strategies) | set(uid for (uid,) in users_with_recipes)

        sessions_created = 0

        for user_id in all_user_ids:
            # Check if user has KIS credentials
            kis_cred = db.query(ApiCredential).filter(
                ApiCredential.user_id == user_id,
                ApiCredential.service_type == "kis",
                ApiCredential.is_active == True,
            ).first()

            if not kis_cred:
                continue

            # Check for already running session
            running = db.query(AgentSession).filter(
                AgentSession.user_id == user_id,
                AgentSession.status.in_(["running", "pending"]),
            ).first()

            if running:
                continue

            # Create new agent session
            session = AgentSession(
                user_id=user_id,
                session_type="full_cycle",
                status="pending",
                strategy_candidates=[],
                iteration_count=0,
                error_log=[],
            )
            db.add(session)
            db.flush()

            # Dispatch to Celery
            run_agent_session.delay(
                user_id=str(user_id),
                session_id=str(session.id),
                session_type="full_cycle",
            )
            sessions_created += 1
            logger.info(f"Auto-started agent session for user {user_id}")

        db.commit()
        logger.info(f"Scheduled agent run: {sessions_created} sessions created")
        return {"status": "ok", "sessions_created": sessions_created}

    except Exception as e:
        db.rollback()
        logger.error(f"Scheduled agent run failed: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
