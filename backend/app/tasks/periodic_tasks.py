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

# P&L alert thresholds (percentage) and dedup tracking
PNL_ALERT_THRESHOLDS = [5, 10, 20]
_last_pnl_alert: dict[tuple[str, str], int] = {}  # (user_id, stock_code) → last alerted threshold
_PNL_DEDUP_MAX_SIZE = 500  # max entries before cleanup


def _get_pnl_threshold(pnl_pct: float) -> int | None:
    """Return the highest threshold crossed by pnl_pct, or None."""
    abs_pct = abs(pnl_pct)
    crossed = None
    for t in PNL_ALERT_THRESHOLDS:
        if abs_pct >= t:
            crossed = t
    return crossed


def _send_pnl_notification(user_id_str: str, stock_code: str, pnl: float, pnl_pct: float):
    """Send P&L alert notification (sync wrapper)."""
    import asyncio
    from app.services.notification_service import notify_pnl_alert
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(notify_pnl_alert(user_id_str, stock_code, pnl, pnl_pct))
        loop.close()
    except Exception as exc:
        logger.warning(f"P&L notification failed for {stock_code}: {exc}")


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

                            # Check P&L alert thresholds
                            if pos.avg_cost_price and pos.avg_cost_price > 0:
                                pnl_pct = float(
                                    (Decimal(str(price)) - pos.avg_cost_price)
                                    / pos.avg_cost_price * 100
                                )
                                threshold = _get_pnl_threshold(pnl_pct)
                                uid_str = str(user_id)
                                key = (uid_str, stock_code)
                                if threshold and _last_pnl_alert.get(key) != threshold:
                                    _last_pnl_alert[key] = threshold
                                    _send_pnl_notification(
                                        uid_str, stock_code,
                                        float(pos.unrealized_pnl), pnl_pct,
                                    )

                            # Prune dedup cache if too large
                            if len(_last_pnl_alert) > _PNL_DEDUP_MAX_SIZE:
                                # Keep only recent half
                                keys = list(_last_pnl_alert.keys())
                                for k in keys[: len(keys) // 2]:
                                    _last_pnl_alert.pop(k, None)

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


def _send_signal_notification(db, recipe, stock_code: str, signal_type: str) -> int:
    """Save a recipe signal notification to sync DB and push via WebSocket.

    Returns 1 on success, 0 on failure.
    """
    import asyncio
    from app.models.notification import Notification
    from app.services.notification_service import (
        NotificationService, NotificationPayload, NotificationCategory,
    )

    action = "진입" if signal_type == "entry" else "청산"
    title = f"[{recipe.name}] {stock_code} {action} 시그널"
    message = f"레시피 '{recipe.name}'에서 {stock_code}의 {action} 시그널이 감지되었습니다."
    data = {
        "recipe_id": str(recipe.id),
        "recipe_name": recipe.name,
        "stock_code": stock_code,
        "signal_type": signal_type,
    }
    link = f"/dashboard/recipes/{recipe.id}"

    try:
        notif = Notification(
            user_id=recipe.user_id,
            category="alert",
            title=title,
            message=message,
            data=data,
            link=link,
        )
        db.add(notif)
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to save signal notification: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return 0

    # WebSocket push (best-effort)
    try:
        payload = NotificationPayload(
            user_id=str(recipe.user_id),
            category=NotificationCategory.ALERT,
            title=title,
            message=message,
            data=data,
            link=link,
        )
        asyncio.run(NotificationService._send_websocket(payload))
    except Exception:
        pass  # WebSocket is best-effort

    # Email for entry signals only (sync)
    if signal_type == "entry":
        try:
            payload = NotificationPayload(
                user_id=str(recipe.user_id),
                category=NotificationCategory.ALERT,
                title=title,
                message=message,
                data=data,
                link=link,
                send_email=True,
            )
            NotificationService._send_email(payload)
        except Exception:
            pass  # Email is best-effort

    return 1


def _send_condition_notification(db, user_id, condition_id: str, condition_name: str, results: list) -> int:
    """Save a condition match notification to sync DB and push via WebSocket.

    Returns 1 on success, 0 on failure.
    """
    import asyncio
    from app.models.notification import Notification
    from app.services.notification_service import (
        NotificationService, NotificationPayload, NotificationCategory,
    )

    count = len(results)
    if count == 0:
        return 0

    codes = [r.get("stock_code", "") for r in results[:10] if isinstance(r, dict)]
    title = f"조건검색 '{condition_name}': {count}개 종목 매칭"
    message = f"조건검색 '{condition_name}'에서 {count}개 종목이 매칭되었습니다."
    data = {
        "condition_id": condition_id,
        "condition_name": condition_name,
        "match_count": count,
        "stock_codes": codes,
    }
    link = "/dashboard/recipes"

    try:
        notif = Notification(
            user_id=user_id,
            category="alert",
            title=title,
            message=message,
            data=data,
            link=link,
        )
        db.add(notif)
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to save condition notification: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return 0

    # WebSocket push (best-effort)
    try:
        payload = NotificationPayload(
            user_id=str(user_id),
            category=NotificationCategory.ALERT,
            title=title,
            message=message,
            data=data,
            link=link,
        )
        asyncio.run(NotificationService._send_websocket(payload))
    except Exception:
        pass

    return 1


@celery_app.task(name="tasks.monitor_active_recipes", soft_time_limit=300, time_limit=360)
def monitor_active_recipes():
    """Evaluate active recipe conditions via REST polling.

    Runs every 5 minutes during market hours.
    Fetches OHLCV data (Yahoo Finance), runs SignalComposer,
    and caches entry/exit signals to Redis.
    """
    import asyncio
    import json
    import redis
    from datetime import datetime as dt, timedelta
    from app.analysis.composer import SignalComposer
    from app.integrations.data.factory import get_data_provider

    settings = get_settings()
    db = _get_sync_db()
    try:
        recipes = db.query(TradingRecipe).filter(
            TradingRecipe.is_active == True,
        ).all()

        if not recipes:
            return {"status": "ok", "evaluated": 0, "signals": 0}

        composer = SignalComposer()
        provider = get_data_provider("yahoo")
        r = redis.from_url(settings.redis_url)

        end_date = dt.now().strftime("%Y-%m-%d")
        start_date = (dt.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        evaluated = 0
        signals_found = 0
        notifications_sent = 0
        auto_executed = 0

        for recipe in recipes:
            stock_codes = recipe.stock_codes or []
            if not stock_codes:
                continue

            for stock_code in stock_codes:
                evaluated += 1
                try:
                    df = provider.get_ohlcv(stock_code, start_date, end_date)
                    if df is None or df.empty or len(df) < 60:
                        logger.debug(f"Insufficient data for {stock_code}, skipping")
                        continue

                    entry, exit_ = composer.compose(df, recipe.signal_config)

                    should_enter = bool(entry.iloc[-1]) if len(entry) > 0 else False
                    should_exit = bool(exit_.iloc[-1]) if len(exit_) > 0 else False

                    # Apply custom filters on entry
                    if should_enter and recipe.custom_filters:
                        latest = df.iloc[-1]
                        volume_min = recipe.custom_filters.get("volume_min")
                        if volume_min and latest["volume"] < volume_min:
                            should_enter = False
                        price_range = recipe.custom_filters.get("price_range")
                        if should_enter and price_range and len(price_range) == 2:
                            price = latest["close"]
                            if price < price_range[0] or price > price_range[1]:
                                should_enter = False

                    if should_enter or should_exit:
                        signals_found += 1
                        signal_type = "entry" if should_enter else "exit"
                        signal_data = {
                            "recipe_id": str(recipe.id),
                            "recipe_name": recipe.name,
                            "stock_code": stock_code,
                            "should_enter": should_enter,
                            "should_exit": should_exit,
                            "signal_type": signal_type,
                            "timestamp": dt.now().isoformat(),
                        }
                        r.set(
                            f"recipe:{recipe.id}:signal:{stock_code}",
                            json.dumps(signal_data),
                            ex=600,  # 10 min TTL
                        )
                        logger.info(
                            f"Signal detected: recipe='{recipe.name}' stock={stock_code} "
                            f"enter={should_enter} exit={should_exit}"
                        )

                        # Send notification
                        notifications_sent += _send_signal_notification(
                            db, recipe, stock_code, signal_type,
                        )

                        # Auto-execute if enabled
                        if recipe.auto_execute:
                            from app.models.order import Order
                            cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
                            existing = db.query(Order).filter(
                                Order.recipe_id == recipe.id,
                                Order.stock_code == stock_code,
                                Order.submitted_at >= cutoff,
                            ).first()

                            if existing:
                                logger.info(
                                    f"Skip auto-exec: duplicate order for recipe='{recipe.name}' "
                                    f"stock={stock_code} within 5 min"
                                )
                            else:
                                try:
                                    from app.db.session import async_session_factory
                                    from app.services.recipe_executor import RecipeExecutor

                                    async def _auto_exec():
                                        async with async_session_factory() as async_db:
                                            executor = RecipeExecutor()
                                            results = await executor.execute(
                                                user_id=str(recipe.user_id),
                                                recipe=recipe,
                                                db=async_db,
                                                stock_code=stock_code,
                                            )
                                            await async_db.commit()
                                            return results

                                    exec_results = asyncio.run(_auto_exec())
                                    for er in (exec_results or []):
                                        if er.get("status") == "submitted":
                                            auto_executed += 1
                                            logger.info(
                                                f"Auto-executed: recipe='{recipe.name}' "
                                                f"stock={stock_code} side={er.get('side')} "
                                                f"qty={er.get('quantity')} "
                                                f"kis_order={er.get('kis_order_id')}"
                                            )
                                        else:
                                            logger.warning(
                                                f"Auto-exec result: recipe='{recipe.name}' "
                                                f"stock={stock_code} status={er.get('status')} "
                                                f"error={er.get('error')}"
                                            )
                                except Exception as e:
                                    logger.error(
                                        f"Auto-execute failed: recipe='{recipe.name}' "
                                        f"stock={stock_code}: {e}",
                                        exc_info=True,
                                    )

                except Exception as e:
                    logger.warning(f"Evaluation failed for recipe '{recipe.name}' stock={stock_code}: {e}")
                    continue

        logger.info(
            f"Recipe monitoring: evaluated={evaluated}, signals={signals_found}, "
            f"notifications={notifications_sent}, auto_executed={auto_executed}"
        )
        return {
            "status": "ok", "evaluated": evaluated, "signals": signals_found,
            "notifications": notifications_sent, "auto_executed": auto_executed,
        }

    except Exception as e:
        logger.error(f"Recipe monitoring failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


@celery_app.task(name="tasks.poll_condition_search", soft_time_limit=300, time_limit=360)
def poll_condition_search():
    """Poll KIS condition search results for active recipes.

    Runs every 10 minutes during market hours.
    Executes condition searches via KIS API and caches results in Redis.
    """
    import asyncio
    import json
    import redis
    from app.integrations.kis.client import KISClient

    settings = get_settings()
    db = _get_sync_db()
    try:
        recipes = db.query(TradingRecipe).filter(
            TradingRecipe.is_active == True,
        ).all()

        # Collect unique (user_id, condition_id) pairs to avoid duplicate API calls
        condition_tasks: dict[str, dict] = {}  # condition_id -> {"user_id", "recipe_ids", "condition_name"}
        for recipe in recipes:
            signals = recipe.signal_config.get("signals", [])
            for sig in signals:
                if sig.get("type") == "kis_condition":
                    cid = sig.get("condition_id", "")
                    if not cid:
                        continue
                    if cid not in condition_tasks:
                        condition_tasks[cid] = {
                            "user_id": recipe.user_id,
                            "condition_name": sig.get("condition_name", cid),
                            "recipe_ids": [],
                        }
                    condition_tasks[cid]["recipe_ids"].append(str(recipe.id))

        if not condition_tasks:
            return {"status": "ok", "polled": 0}

        vault = get_vault()
        r = redis.from_url(settings.redis_url)
        polled = 0
        errors = 0
        notifications_sent = 0

        # Group condition_ids by user_id (one KIS client per user)
        user_conditions: dict[str, list[str]] = {}
        for cid, info in condition_tasks.items():
            uid = str(info["user_id"])
            user_conditions.setdefault(uid, []).append(cid)

        for user_id_str, condition_ids in user_conditions.items():
            # Get KIS credentials
            cred = db.query(ApiCredential).filter(
                ApiCredential.user_id == user_id_str,
                ApiCredential.service_type == "kis",
                ApiCredential.is_active == True,
            ).first()

            if not cred:
                logger.warning(f"No KIS credentials for user {user_id_str}, skipping condition search")
                continue

            try:
                app_key = vault.decrypt(cred.encrypted_key)
                app_secret = vault.decrypt(cred.encrypted_secret)
            except Exception:
                logger.warning(f"Failed to decrypt credentials for user {user_id_str}")
                continue

            kis = KISClient(
                app_key=app_key,
                app_secret=app_secret,
                account_number=cred.account_number or "",
                is_paper=cred.is_paper_trading,
            )

            for cid in condition_ids:
                try:
                    results = asyncio.run(kis.run_condition_search(cid))
                    r.set(
                        f"condition:{cid}:results",
                        json.dumps(results),
                        ex=900,  # 15 min TTL
                    )
                    polled += 1
                    logger.info(f"Condition search {cid}: {len(results)} stocks matched")

                    # Send notification if matches found
                    if results:
                        cond_name = condition_tasks[cid].get("condition_name", cid)
                        user_id_val = condition_tasks[cid]["user_id"]
                        notifications_sent += _send_condition_notification(
                            db, user_id_val, cid, cond_name, results,
                        )
                except Exception as e:
                    errors += 1
                    logger.warning(f"Condition search failed for {cid}: {e}")

        logger.info(f"Condition search polling: polled={polled}, errors={errors}, notifications={notifications_sent}")
        return {"status": "ok", "polled": polled, "errors": errors, "notifications": notifications_sent}

    except Exception as e:
        logger.error(f"Condition search polling failed: {e}", exc_info=True)
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


@celery_app.task(name="tasks.collect_factor_snapshots", soft_time_limit=300, time_limit=360)
def collect_factor_snapshots():
    """Collect technical factor snapshots for monitored stocks.

    Runs every 30 minutes during market hours.
    Extracts 20+ technical factors from OHLCV data for each stock
    in active recipes and stores them in factor_snapshots table.
    """
    from datetime import date as date_type
    from app.services.factor_collector import extract_technical_factors, _safe_float
    from app.models.factor_snapshot import FactorSnapshot
    from app.integrations.data.factory import get_data_provider

    db = _get_sync_db()
    try:
        # Get all stock codes from active recipes
        recipes = db.query(TradingRecipe).filter(
            TradingRecipe.is_active == True,
        ).all()

        stock_codes = set()
        for r in recipes:
            for code in (r.stock_codes or []):
                stock_codes.add(code)

        # Also include stocks from open positions
        positions = db.query(Position).filter(Position.quantity > 0).all()
        for p in positions:
            stock_codes.add(p.stock_code)

        if not stock_codes:
            logger.info("Factor collector: no stocks to monitor")
            return {"status": "ok", "stocks": 0, "factors": 0}

        provider = get_data_provider()
        today = date_type.today()
        total_factors = 0

        for code in stock_codes:
            try:
                df = provider.get_ohlcv(code, period="3mo")
                if df is None or len(df) < 20:
                    continue

                factors = extract_technical_factors(df)
                for name, value in factors.items():
                    safe = _safe_float(value)
                    if safe is None:
                        continue

                    from app.services.factor_collector import _FACTOR_REGISTRY
                    entry = _FACTOR_REGISTRY.get(name, {})
                    # Check existing
                    existing = db.query(FactorSnapshot).filter(
                        FactorSnapshot.snapshot_date == today,
                        FactorSnapshot.stock_code == code,
                        FactorSnapshot.timeframe == "daily",
                        FactorSnapshot.factor_name == name,
                    ).first()

                    if existing:
                        existing.value = safe
                    else:
                        snap = FactorSnapshot(
                            snapshot_date=today,
                            stock_code=code,
                            timeframe="daily",
                            factor_name=name,
                            value=safe,
                            metadata_={"category": entry.get("category", ""), "source": "collector"},
                        )
                        db.add(snap)
                    total_factors += 1

                db.commit()
            except Exception as e:
                logger.warning(f"Factor collection failed for {code}: {e}")
                db.rollback()

        logger.info(f"Factor collector: {len(stock_codes)} stocks, {total_factors} factors saved")
        return {"status": "ok", "stocks": len(stock_codes), "factors": total_factors}

    except Exception as e:
        db.rollback()
        logger.error(f"Factor collection failed: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
