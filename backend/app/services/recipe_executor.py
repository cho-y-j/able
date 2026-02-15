"""Recipe execution service.

Bridges recipe signals to KIS orders via ExecutionEngine.
Used for manual execution triggers and can be called from
periodic tasks for automated trading.
"""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trading_recipe import TradingRecipe
from app.models.order import Order
from app.models.api_credential import ApiCredential
from app.core.encryption import get_vault
from app.integrations.kis.client import KISClient
from app.execution.engine import ExecutionEngine
from app.analysis.composer import SignalComposer
from app.services.strategy_search import fetch_ohlcv_data

logger = logging.getLogger(__name__)


class RecipeExecutor:
    """Execute trades based on recipe signals."""

    async def execute(
        self,
        user_id: str,
        recipe: TradingRecipe,
        db: AsyncSession,
        stock_code: str | None = None,
    ) -> list[dict]:
        """Evaluate recipe signals and place orders for matching stocks.

        Args:
            user_id: User UUID string
            recipe: Active TradingRecipe instance
            db: Async database session
            stock_code: Target a specific stock, or None for all recipe stocks

        Returns:
            List of order result dicts with keys: stock_code, side, quantity,
            kis_order_id, status, fill_price, error
        """
        # 1. Get KIS credentials
        kis_client = await self._get_kis_client(user_id, db)
        if not kis_client:
            raise ValueError("KIS credentials not found or could not be decrypted")

        # 2. Get balance for position sizing
        try:
            balance_info = await kis_client.get_balance()
            total_balance = balance_info.get("total_balance", 0)
        except Exception as e:
            logger.warning(f"Failed to get balance, using default: {e}")
            total_balance = 10_000_000  # Fallback

        # 3. Determine target stocks
        target_stocks = [stock_code] if stock_code else (recipe.stock_codes or [])
        if not target_stocks:
            return []

        # 4. Evaluate and execute for each stock
        composer = SignalComposer()
        engine = ExecutionEngine(kis_client)
        risk_config = recipe.risk_config or {}
        position_pct = risk_config.get("position_size", 10) / 100
        results = []

        for sc in target_stocks:
            result = await self._evaluate_and_execute(
                db=db,
                engine=engine,
                composer=composer,
                recipe=recipe,
                stock_code=sc,
                total_balance=total_balance,
                position_pct=position_pct,
            )
            if result:
                results.append(result)

        return results

    async def _evaluate_and_execute(
        self,
        db: AsyncSession,
        engine: ExecutionEngine,
        composer: SignalComposer,
        recipe: TradingRecipe,
        stock_code: str,
        total_balance: float,
        position_pct: float,
    ) -> dict | None:
        """Evaluate signals for a single stock and execute if triggered."""
        # Fetch OHLCV data
        try:
            df = await fetch_ohlcv_data(stock_code=stock_code)
        except Exception as e:
            logger.warning(f"OHLCV fetch failed for {stock_code}: {e}")
            return {"stock_code": stock_code, "status": "error", "error": f"Data fetch failed: {e}"}

        if df is None or df.empty or len(df) < 60:
            return {"stock_code": stock_code, "status": "skipped", "error": "Insufficient data"}

        # Compose signals
        try:
            entry, exit_ = composer.compose(df, recipe.signal_config)
        except Exception as e:
            logger.warning(f"Signal composition failed for {stock_code}: {e}")
            return {"stock_code": stock_code, "status": "error", "error": f"Signal error: {e}"}

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

        if not should_enter and not should_exit:
            return {"stock_code": stock_code, "status": "no_signal", "error": None}

        # Determine side and calculate quantity
        side = "buy" if should_enter else "sell"
        current_price = float(df.iloc[-1]["close"])

        if current_price <= 0:
            return {"stock_code": stock_code, "status": "error", "error": "Invalid price"}

        position_value = total_balance * position_pct
        quantity = int(position_value / current_price)
        if quantity <= 0:
            return {"stock_code": stock_code, "status": "error", "error": "Calculated quantity is 0"}

        # Execute order
        try:
            exec_result = await engine.execute(
                stock_code=stock_code,
                side=side,
                quantity=quantity,
            )
        except Exception as e:
            logger.error(f"Execution failed for {stock_code}: {e}")
            return {"stock_code": stock_code, "side": side, "quantity": quantity,
                    "status": "error", "error": str(e)}

        # Save Order to DB
        order = Order(
            user_id=recipe.user_id,
            recipe_id=recipe.id,
            stock_code=stock_code,
            side=side,
            order_type="market" if exec_result.execution_strategy == "direct" else "limit",
            quantity=quantity,
            kis_order_id=exec_result.kis_order_id,
            status="submitted" if exec_result.success else "failed",
            execution_strategy=exec_result.execution_strategy,
            expected_price=Decimal(str(current_price)),
            avg_fill_price=Decimal(str(exec_result.fill_price)) if exec_result.fill_price else None,
            slippage_bps=exec_result.slippage.slippage_bps if exec_result.slippage else None,
            submitted_at=datetime.now(timezone.utc),
            error_message=exec_result.error_message,
        )
        db.add(order)
        await db.flush()

        # Push order_update to user's WebSocket
        try:
            from app.api.v1.websocket import manager
            await manager.send_to_user(str(recipe.user_id), {
                "type": "order_update",
                "order_id": str(order.id),
                "recipe_id": str(recipe.id),
                "stock_code": stock_code,
                "side": side,
                "status": "submitted" if exec_result.success else "failed",
            })
        except Exception:
            pass  # Non-critical — don't break execution flow

        logger.info(
            f"Recipe '{recipe.name}' order: {side} {quantity} {stock_code} "
            f"status={'submitted' if exec_result.success else 'failed'}"
        )

        return {
            "stock_code": stock_code,
            "side": side,
            "quantity": quantity,
            "kis_order_id": exec_result.kis_order_id,
            "status": "submitted" if exec_result.success else "failed",
            "fill_price": exec_result.fill_price,
            "execution_strategy": exec_result.execution_strategy,
            "error": exec_result.error_message,
            "order_id": str(order.id),
        }

    async def _get_kis_client(self, user_id: str, db: AsyncSession) -> KISClient | None:
        """Get authenticated KIS client for user."""
        result = await db.execute(
            select(ApiCredential).where(
                ApiCredential.user_id == uuid.UUID(user_id),
                ApiCredential.service_type == "kis",
                ApiCredential.is_active == True,  # noqa: E712
            )
        )
        cred = result.scalar_one_or_none()
        if not cred:
            return None

        vault = get_vault()
        try:
            app_key = vault.decrypt(cred.encrypted_key)
            app_secret = vault.decrypt(cred.encrypted_secret)
        except Exception:
            logger.error(f"Failed to decrypt KIS credentials for user {user_id}")
            return None

        return KISClient(
            app_key=app_key,
            app_secret=app_secret,
            account_number=cred.account_number or "",
            is_paper=cred.is_paper_trading,
        )
