"""Prometheus metrics for ABLE trading platform.

Business metrics: orders, slippage, portfolio value
System metrics: KIS API latency, Celery tasks, DB/Redis health
"""

from prometheus_client import Counter, Histogram, Gauge, Info

# ── Business Metrics ─────────────────────────────────────────

ORDERS_TOTAL = Counter(
    "able_orders_total",
    "Total orders submitted",
    ["side", "execution_strategy", "status"],
)

ORDER_LATENCY = Histogram(
    "able_order_latency_seconds",
    "Order submission latency",
    ["execution_strategy"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

SLIPPAGE_BPS = Histogram(
    "able_slippage_bps",
    "Execution slippage in basis points",
    ["side", "execution_strategy"],
    buckets=[-50, -20, -10, -5, 0, 5, 10, 20, 50, 100],
)

PORTFOLIO_VALUE = Gauge(
    "able_portfolio_value_krw",
    "Current portfolio value in KRW",
    ["user_id"],
)

ACTIVE_POSITIONS = Gauge(
    "able_active_positions",
    "Number of active positions",
    ["user_id"],
)

# ── Agent Metrics ────────────────────────────────────────────

AGENT_RUNS_TOTAL = Counter(
    "able_agent_runs_total",
    "Total agent session runs",
    ["status"],
)

AGENT_NODE_DURATION = Histogram(
    "able_agent_node_duration_seconds",
    "Duration of individual agent node execution",
    ["node_name"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

# ── System Metrics ───────────────────────────────────────────

KIS_API_REQUESTS = Counter(
    "able_kis_api_requests_total",
    "Total KIS API requests",
    ["method", "endpoint", "status"],
)

KIS_API_LATENCY = Histogram(
    "able_kis_api_latency_seconds",
    "KIS API request latency",
    ["method", "endpoint"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

HTTP_REQUESTS = Counter(
    "able_http_requests_total",
    "Total HTTP requests to the API",
    ["method", "path", "status_code"],
)

HTTP_REQUEST_DURATION = Histogram(
    "able_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "path"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)

CIRCUIT_BREAKER_STATE = Gauge(
    "able_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["name"],
)

APP_INFO = Info("able_app", "ABLE application info")
