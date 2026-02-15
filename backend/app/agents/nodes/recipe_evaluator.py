"""Recipe Evaluator node for the trading orchestrator.

Evaluates user's active TradingRecipes using SignalComposer
and adds results to the trading state for risk management.
"""

import logging

from app.agents.state import TradingState

logger = logging.getLogger(__name__)


async def recipe_evaluator_node(state: TradingState) -> dict:
    """Evaluate active recipes and generate trading signals.

    1. Load user's active recipes from DB
    2. For each recipe, compose signals using SignalComposer
    3. Store results in state for risk_manager to process
    """
    from langchain_core.messages import AIMessage

    user_id = state.get("user_id")
    if not user_id:
        return {"messages": [AIMessage(content="No user_id in state, skipping recipe evaluation.")]}

    active_recipes = state.get("active_recipes", [])
    recipe_signals = {}

    if not active_recipes:
        # Try to load from DB
        try:
            from app.db.session import async_session_factory
            from app.models.trading_recipe import TradingRecipe
            from sqlalchemy import select
            import uuid

            async with async_session_factory() as db:
                result = await db.execute(
                    select(TradingRecipe).where(
                        TradingRecipe.user_id == uuid.UUID(user_id),
                        TradingRecipe.is_active == True,  # noqa: E712
                    )
                )
                recipes = result.scalars().all()
                active_recipes = [
                    {
                        "id": str(r.id),
                        "name": r.name,
                        "signal_config": r.signal_config,
                        "custom_filters": r.custom_filters,
                        "stock_codes": r.stock_codes or [],
                        "risk_config": r.risk_config,
                    }
                    for r in recipes
                ]
        except Exception as e:
            logger.error(f"Failed to load recipes: {e}")
            return {
                "messages": [AIMessage(content=f"Recipe loading failed: {e}")],
                "recipe_signals": {},
            }

    if not active_recipes:
        return {
            "messages": [AIMessage(content="No active recipes found.")],
            "active_recipes": [],
            "recipe_signals": {},
        }

    # Evaluate each recipe
    from app.analysis.composer import SignalComposer
    from app.services.strategy_search import fetch_ohlcv_data

    composer = SignalComposer()

    for recipe in active_recipes:
        recipe_id = recipe["id"]
        recipe_name = recipe["name"]
        signal_config = recipe["signal_config"]
        stock_codes = recipe.get("stock_codes", [])

        recipe_results = {}

        for stock_code in stock_codes:
            try:
                df = await fetch_ohlcv_data(stock_code=stock_code)
                if df is None or df.empty:
                    recipe_results[stock_code] = {"error": "no_data"}
                    continue

                entry, exit_ = composer.compose(df, signal_config)
                latest_entry = bool(entry.iloc[-1]) if len(entry) > 0 else False
                latest_exit = bool(exit_.iloc[-1]) if len(exit_) > 0 else False

                recipe_results[stock_code] = {
                    "entry": latest_entry,
                    "exit": latest_exit,
                    "entry_count_last_10": int(entry.tail(10).sum()),
                    "exit_count_last_10": int(exit_.tail(10).sum()),
                }

                if latest_entry:
                    logger.info(f"Recipe '{recipe_name}' entry signal for {stock_code}")

            except Exception as e:
                logger.error(f"Recipe evaluation failed for {stock_code}: {e}")
                recipe_results[stock_code] = {"error": str(e)}

        recipe_signals[recipe_id] = {
            "name": recipe_name,
            "results": recipe_results,
            "risk_config": recipe.get("risk_config", {}),
        }

    summary = []
    for rid, data in recipe_signals.items():
        entries = [sc for sc, r in data["results"].items() if r.get("entry")]
        if entries:
            summary.append(f"Recipe '{data['name']}': entry signals for {', '.join(entries)}")

    msg = "Recipe evaluation complete. " + ("; ".join(summary) if summary else "No entry signals detected.")

    return {
        "messages": [AIMessage(content=msg)],
        "active_recipes": active_recipes,
        "recipe_signals": recipe_signals,
    }
