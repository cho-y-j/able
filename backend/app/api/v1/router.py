from fastapi import APIRouter
from app.api.v1 import auth, api_keys, strategies, backtests, trading, agents, market_data, websocket, paper, notifications, analysis, recipes

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(api_keys.router, prefix="/keys", tags=["api-keys"])
api_router.include_router(strategies.router, prefix="/strategies", tags=["strategies"])
api_router.include_router(backtests.router, prefix="/backtests", tags=["backtests"])
api_router.include_router(trading.router, prefix="/trading", tags=["trading"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(market_data.router, prefix="/market", tags=["market-data"])
api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
api_router.include_router(paper.router, prefix="/paper", tags=["paper-trading"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(recipes.router, prefix="/recipes", tags=["recipes"])
