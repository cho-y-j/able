"""Portfolio rebalancing service.

Computes recipe allocations, detects stock conflicts between
active recipes, and generates rebalancing suggestions.
"""

import math
import uuid
import logging
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trading_recipe import TradingRecipe
from app.models.position import Position

logger = logging.getLogger(__name__)

MAX_SINGLE_POSITION_PCT = 10.0  # from RiskLimits default
MAX_TOTAL_EXPOSURE_PCT = 80.0


class RebalancingService:
    """Computes recipe-level portfolio allocations and rebalancing suggestions."""

    @staticmethod
    async def compute_allocations(
        user_id: uuid.UUID,
        db: AsyncSession,
        available_cash: float | None = None,
    ) -> dict:
        """Compute target vs actual allocations for all active recipes.

        Returns a dict matching RecipeAllocationResponse schema.
        """
        # 1. Load active recipes
        recipe_result = await db.execute(
            select(TradingRecipe).where(
                TradingRecipe.user_id == user_id,
                TradingRecipe.is_active == True,  # noqa: E712
            )
        )
        recipes = recipe_result.scalars().all()

        # 2. Load open positions
        pos_result = await db.execute(
            select(Position).where(
                Position.user_id == user_id,
                Position.quantity > 0,
            )
        )
        positions = pos_result.scalars().all()

        # 3. Estimate total capital
        position_value = sum(
            float(p.current_price or p.avg_cost_price) * p.quantity
            for p in positions
        )
        cash = available_cash if available_cash is not None else position_value * 0.25
        total_capital = position_value + cash

        if not recipes:
            return {
                "total_capital": total_capital,
                "available_cash": cash,
                "allocated_capital": 0.0,
                "unallocated_pct": 100.0,
                "recipes": [],
                "warnings": [],
            }

        # 4. Build stock → position lookup
        pos_by_stock: dict[str, Position] = {}
        for p in positions:
            pos_by_stock[p.stock_code] = p

        # 5. Build stock → [recipe] map for overlap detection
        stock_to_recipes: dict[str, list[TradingRecipe]] = defaultdict(list)
        for r in recipes:
            for sc in (r.stock_codes or []):
                stock_to_recipes[sc].append(r)

        # 6. Compute per-recipe allocations
        warnings: list[str] = []
        recipe_allocations = []
        total_target_pct = 0.0

        for r in recipes:
            risk_config = r.risk_config or {}
            pos_size_pct = risk_config.get("position_size", 10)
            stock_codes = r.stock_codes or []
            target_weight_pct = pos_size_pct * len(stock_codes)
            target_value = total_capital * target_weight_pct / 100 if total_capital > 0 else 0.0
            total_target_pct += target_weight_pct

            # Compute actual value from positions
            recipe_positions = []
            actual_value = 0.0

            for sc in stock_codes:
                pos = pos_by_stock.get(sc)
                if not pos:
                    recipe_positions.append({
                        "stock_code": sc,
                        "quantity": 0,
                        "value": 0.0,
                        "weight_pct": 0.0,
                    })
                    continue

                pos_value = float(pos.current_price or pos.avg_cost_price) * pos.quantity
                # If stock is shared by multiple recipes, attribute proportionally
                sharing_recipes = stock_to_recipes.get(sc, [])
                if len(sharing_recipes) > 1:
                    total_target_for_stock = sum(
                        (sr.risk_config or {}).get("position_size", 10)
                        for sr in sharing_recipes
                    )
                    if total_target_for_stock > 0:
                        share = pos_size_pct / total_target_for_stock
                    else:
                        share = 1.0 / len(sharing_recipes)
                    attributed_value = pos_value * share
                    attributed_qty = int(pos.quantity * share)
                else:
                    attributed_value = pos_value
                    attributed_qty = pos.quantity

                weight_pct = (attributed_value / total_capital * 100) if total_capital > 0 else 0.0
                recipe_positions.append({
                    "stock_code": sc,
                    "quantity": attributed_qty,
                    "value": round(attributed_value, 0),
                    "weight_pct": round(weight_pct, 1),
                })
                actual_value += attributed_value

            actual_weight_pct = (actual_value / total_capital * 100) if total_capital > 0 else 0.0
            drift_pct = actual_weight_pct - target_weight_pct

            recipe_allocations.append({
                "recipe_id": str(r.id),
                "recipe_name": r.name,
                "is_active": r.is_active,
                "target_weight_pct": round(target_weight_pct, 1),
                "actual_weight_pct": round(actual_weight_pct, 1),
                "actual_value": round(actual_value, 0),
                "target_value": round(target_value, 0),
                "drift_pct": round(drift_pct, 1),
                "stock_codes": stock_codes,
                "positions": recipe_positions,
            })

        if total_target_pct > 100:
            warnings.append(
                f"합산 목표 배분({total_target_pct:.0f}%)이 100%를 초과합니다"
            )

        allocated_capital = sum(a["actual_value"] for a in recipe_allocations)
        unallocated_pct = ((total_capital - allocated_capital) / total_capital * 100) if total_capital > 0 else 100.0

        return {
            "total_capital": round(total_capital, 0),
            "available_cash": round(cash, 0),
            "allocated_capital": round(allocated_capital, 0),
            "unallocated_pct": round(unallocated_pct, 1),
            "recipes": recipe_allocations,
            "warnings": warnings,
        }

    @staticmethod
    async def detect_conflicts(
        user_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict:
        """Detect overlapping stock codes between active recipes.

        Returns a dict matching RecipeConflictResponse schema.
        """
        recipe_result = await db.execute(
            select(TradingRecipe).where(
                TradingRecipe.user_id == user_id,
                TradingRecipe.is_active == True,  # noqa: E712
            )
        )
        recipes = recipe_result.scalars().all()

        # Load positions for current value
        pos_result = await db.execute(
            select(Position).where(
                Position.user_id == user_id,
                Position.quantity > 0,
            )
        )
        positions = pos_result.scalars().all()
        pos_by_stock = {p.stock_code: p for p in positions}

        # Build stock → recipes map
        stock_to_recipes: dict[str, list[TradingRecipe]] = defaultdict(list)
        for r in recipes:
            for sc in (r.stock_codes or []):
                stock_to_recipes[sc].append(r)

        conflicts = []
        risk_warnings = []

        for sc, recipe_list in stock_to_recipes.items():
            if len(recipe_list) < 2:
                continue

            combined_pct = sum(
                (r.risk_config or {}).get("position_size", 10)
                for r in recipe_list
            )

            pos = pos_by_stock.get(sc)
            current_value = (
                float(pos.current_price or pos.avg_cost_price) * pos.quantity
                if pos else 0.0
            )

            if combined_pct >= MAX_SINGLE_POSITION_PCT * 2:
                risk_level = "high"
            elif combined_pct >= MAX_SINGLE_POSITION_PCT:
                risk_level = "medium"
            else:
                risk_level = "low"

            conflicts.append({
                "stock_code": sc,
                "recipes": [
                    {
                        "recipe_id": str(r.id),
                        "recipe_name": r.name,
                        "position_size_pct": (r.risk_config or {}).get("position_size", 10),
                    }
                    for r in recipe_list
                ],
                "combined_target_pct": combined_pct,
                "current_position_value": round(current_value, 0),
                "risk_level": risk_level,
            })

            if risk_level == "high":
                names = ", ".join(r.name for r in recipe_list)
                risk_warnings.append(
                    f"{sc}: 합산 목표({combined_pct}%)가 단일 종목 한도를 크게 초과 ({names})"
                )

        return {
            "conflicts": conflicts,
            "total_overlapping_stocks": len(conflicts),
            "risk_warnings": risk_warnings,
        }

    @staticmethod
    async def suggest_rebalancing(
        user_id: uuid.UUID,
        db: AsyncSession,
        available_cash: float | None = None,
    ) -> dict:
        """Generate rebalancing suggestions based on allocation drift.

        Returns a dict matching RebalancingSuggestionResponse schema.
        """
        alloc_data = await RebalancingService.compute_allocations(
            user_id, db, available_cash
        )
        total_capital = alloc_data["total_capital"]
        cash = alloc_data["available_cash"]

        if not alloc_data["recipes"]:
            return {
                "suggestions": [],
                "summary": {
                    "total_buys": 0,
                    "total_sells": 0,
                    "total_buy_value": 0.0,
                    "total_sell_value": 0.0,
                    "net_cash_required": 0.0,
                    "available_cash": cash,
                    "feasible": True,
                },
                "warnings": [],
            }

        # Load positions for current prices
        pos_result = await db.execute(
            select(Position).where(
                Position.user_id == user_id,
                Position.quantity > 0,
            )
        )
        positions = pos_result.scalars().all()
        pos_by_stock = {p.stock_code: p for p in positions}

        # Track which stocks have already been processed (for overlapping stocks)
        processed_stocks: set[str] = set()
        suggestions = []
        warnings = list(alloc_data["warnings"])

        for recipe_alloc in alloc_data["recipes"]:
            for pos_slice in recipe_alloc["positions"]:
                sc = pos_slice["stock_code"]
                if sc in processed_stocks:
                    continue

                pos = pos_by_stock.get(sc)
                current_price = float(pos.current_price or pos.avg_cost_price) if pos else 0.0
                current_qty = pos.quantity if pos else 0

                if current_price <= 0:
                    continue

                # Compute net target for this stock across all recipes
                # (handles overlapping stocks by summing targets)
                net_target_pct = 0.0
                recipe_name_parts = []
                recipe_id = recipe_alloc["recipe_id"]

                # Find all recipes targeting this stock
                for ra in alloc_data["recipes"]:
                    if sc in ra["stock_codes"]:
                        risk_pct = ra["target_weight_pct"] / max(len(ra["stock_codes"]), 1)
                        net_target_pct += risk_pct
                        if ra["recipe_id"] != recipe_alloc["recipe_id"]:
                            recipe_name_parts.append(ra["recipe_name"])

                # Cap at max single position
                capped = False
                if net_target_pct > MAX_SINGLE_POSITION_PCT:
                    net_target_pct = MAX_SINGLE_POSITION_PCT
                    capped = True

                target_value = total_capital * net_target_pct / 100
                target_qty = math.floor(target_value / current_price)
                delta_qty = target_qty - current_qty

                if delta_qty == 0:
                    action = "hold"
                    reason = "목표 수량에 도달"
                elif delta_qty > 0:
                    action = "buy"
                    reason = f"목표 대비 {abs(delta_qty)}주 부족"
                else:
                    action = "sell"
                    reason = f"목표 대비 {abs(delta_qty)}주 초과"

                if capped:
                    reason += f" (단일 종목 한도 {MAX_SINGLE_POSITION_PCT}%로 제한)"

                suggestions.append({
                    "recipe_id": recipe_id,
                    "recipe_name": recipe_alloc["recipe_name"],
                    "stock_code": sc,
                    "action": action,
                    "current_quantity": current_qty,
                    "target_quantity": target_qty,
                    "delta_quantity": delta_qty,
                    "estimated_value": round(abs(delta_qty) * current_price, 0),
                    "current_price": current_price,
                    "reason": reason,
                })
                processed_stocks.add(sc)

        # Compute summary
        buys = [s for s in suggestions if s["action"] == "buy"]
        sells = [s for s in suggestions if s["action"] == "sell"]
        total_buy_value = sum(s["estimated_value"] for s in buys)
        total_sell_value = sum(s["estimated_value"] for s in sells)
        net_cash_required = total_buy_value - total_sell_value
        feasible = net_cash_required <= cash

        if not feasible:
            warnings.append(
                f"필요 현금({net_cash_required:,.0f}원)이 가용 현금({cash:,.0f}원)을 초과합니다"
            )

        return {
            "suggestions": suggestions,
            "summary": {
                "total_buys": len(buys),
                "total_sells": len(sells),
                "total_buy_value": round(total_buy_value, 0),
                "total_sell_value": round(total_sell_value, 0),
                "net_cash_required": round(net_cash_required, 0),
                "available_cash": round(cash, 0),
                "feasible": feasible,
            },
            "warnings": warnings,
        }
