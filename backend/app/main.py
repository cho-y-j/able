import json
import logging
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.session import engine
from app.api.v1.router import api_router


# ── JSON Structured Logging ──────────────────────────────────


class JSONFormatter(logging.Formatter):
    """Outputs log records as single-line JSON for production log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        log = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log, ensure_ascii=False)


def setup_logging():
    """Configure structured JSON logging for production."""
    settings = get_settings()

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    if settings.debug:
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
    else:
        handler.setFormatter(JSONFormatter())

    root.handlers = [handler]

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


logger = logging.getLogger("able")


# ── Lifespan ─────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    from app.core.metrics import APP_INFO
    APP_INFO.info({"version": "0.1.0", "name": "ABLE"})
    logger.info("ABLE platform starting up")
    yield
    logger.info("ABLE platform shutting down")
    await engine.dispose()


# ── App Factory ──────────────────────────────────────────────


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "## ABLE — AI-Powered Korean Stock Auto-Trading Platform\n\n"
            "ABLE provides a full-stack autonomous trading system built on:\n\n"
            "- **LangGraph Agent Orchestration** — 6-node pipeline "
            "(Market Analysis → Strategy Search → Risk Management → "
            "Human Approval → Execution → Monitoring)\n"
            "- **KIS (한국투자증권) API Integration** — Real-time market data, "
            "order placement, balance & position management\n"
            "- **70+ Technical Indicators** with automated signal generation\n"
            "- **Advanced Execution** — Smart routing, TWAP, VWAP, slippage tracking\n"
            "- **Backtesting Engine** with Walk-Forward, Monte Carlo & OOS validation\n"
            "- **Paper Trading** — Risk-free simulation with realistic fills\n\n"
            "### Authentication\n"
            "All endpoints (except `/auth/register` and `/auth/login`) require a "
            "Bearer JWT token in the `Authorization` header.\n\n"
            "### Rate Limits\n"
            "| Endpoint | Limit |\n"
            "|----------|-------|\n"
            "| `/auth/login` | 10 req/min |\n"
            "| `/auth/register` | 3 req/min |\n"
            "| General API | 60 req/min |\n"
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=[
            {"name": "auth", "description": "User registration, login, JWT token management"},
            {"name": "api-keys", "description": "Encrypted KIS & LLM credential storage"},
            {"name": "strategies", "description": "Trading strategy CRUD and AI-powered search"},
            {"name": "backtests", "description": "Backtest results, equity curves, Monte Carlo & validation"},
            {"name": "trading", "description": "Live order placement, positions, balance, portfolio analytics"},
            {"name": "agents", "description": "LangGraph AI agent session management with HITL approval"},
            {"name": "market-data", "description": "Real-time prices, OHLCV, technical indicators from KIS"},
            {"name": "paper-trading", "description": "Risk-free paper trading simulation"},
            {"name": "notifications", "description": "In-app notifications, preferences, unread counts"},
            {"name": "websocket", "description": "Real-time WebSocket feeds for trading, agents, market data"},
        ],
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    )

    # Request timing middleware (runs first — outermost)
    @app.middleware("http")
    async def timing_middleware(request: Request, call_next):
        from app.core.metrics import HTTP_REQUESTS, HTTP_REQUEST_DURATION

        start = time.monotonic()
        response: Response = await call_next(request)
        duration = time.monotonic() - start

        path = request.url.path
        # Collapse parameterized paths for cardinality control
        if "/api/v1/" in path:
            parts = path.split("/")
            # Replace UUID-like segments
            parts = [
                "<id>" if len(p) > 20 and "-" in p else p
                for p in parts
            ]
            path = "/".join(parts)

        HTTP_REQUESTS.labels(
            method=request.method,
            path=path,
            status_code=str(response.status_code),
        ).inc()
        HTTP_REQUEST_DURATION.labels(
            method=request.method,
            path=path,
        ).observe(duration)

        return response

    # Security headers middleware
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if "server" in response.headers:
            del response.headers["server"]
        return response

    # Rate limiting middleware
    @app.middleware("http")
    async def rate_limiting(request: Request, call_next):
        from app.core.rate_limit import _find_config, _get_client_ip, get_rate_limiter

        path = request.url.path
        config = _find_config(path)
        if not config:
            return await call_next(request)

        ip = _get_client_ip(request)
        if path.startswith("/api/v1/auth/"):
            key = f"{ip}:{path}"
        else:
            key = f"{ip}:/api/v1/"

        limiter = get_rate_limiter()
        allowed, remaining = limiter.check(key, config)

        if not allowed:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={
                    "Retry-After": str(config.window),
                    "X-RateLimit-Limit": str(config.calls),
                    "X-RateLimit-Remaining": "0",
                },
            )

        limiter.record(key)
        response: Response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(config.calls)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    app.include_router(api_router, prefix="/api/v1")

    # ── Prometheus metrics endpoint ──────────────────────────

    @app.get("/metrics")
    async def metrics():
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    # ── Enhanced health check ────────────────────────────────

    @app.get("/health")
    async def health():
        from sqlalchemy import text
        from app.core.circuit_breaker import get_all_breakers

        checks = {"status": "ok"}
        overall_ok = True

        # DB check
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as e:
            checks["database"] = f"error: {e}"
            overall_ok = False

        # Redis check
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.redis_url)
            await r.ping()
            await r.aclose()
            checks["redis"] = "ok"
        except Exception as e:
            checks["redis"] = f"error: {e}"
            overall_ok = False

        # Circuit breakers
        breakers = {}
        for cb in get_all_breakers():
            breakers[cb.name] = cb.state.value
            if cb.is_open:
                overall_ok = False
        checks["circuit_breakers"] = breakers

        checks["status"] = "ok" if overall_ok else "degraded"
        return checks

    return app


app = create_app()
