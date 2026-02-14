"""Tests for Prometheus metrics and health check endpoints."""

import json
import logging
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.core.metrics import (
    ORDERS_TOTAL,
    ORDER_LATENCY,
    SLIPPAGE_BPS,
    HTTP_REQUESTS,
    HTTP_REQUEST_DURATION,
    CIRCUIT_BREAKER_STATE,
    KIS_API_REQUESTS,
    AGENT_RUNS_TOTAL,
    APP_INFO,
)
from app.main import JSONFormatter, setup_logging


class TestMetricsDefinition:
    def test_orders_total_counter(self):
        """Counter increments correctly."""
        before = ORDERS_TOTAL.labels(side="buy", execution_strategy="direct", status="submitted")._value.get()
        ORDERS_TOTAL.labels(side="buy", execution_strategy="direct", status="submitted").inc()
        after = ORDERS_TOTAL.labels(side="buy", execution_strategy="direct", status="submitted")._value.get()
        assert after == before + 1

    def test_order_latency_histogram(self):
        """Histogram observes values."""
        ORDER_LATENCY.labels(execution_strategy="twap").observe(0.5)
        # Should not raise

    def test_slippage_histogram(self):
        SLIPPAGE_BPS.labels(side="buy", execution_strategy="direct").observe(5.0)

    def test_http_request_counter(self):
        before = HTTP_REQUESTS.labels(method="GET", path="/health", status_code="200")._value.get()
        HTTP_REQUESTS.labels(method="GET", path="/health", status_code="200").inc()
        after = HTTP_REQUESTS.labels(method="GET", path="/health", status_code="200")._value.get()
        assert after == before + 1

    def test_circuit_breaker_gauge(self):
        CIRCUIT_BREAKER_STATE.labels(name="kis_order").set(0)
        assert CIRCUIT_BREAKER_STATE.labels(name="kis_order")._value.get() == 0


class TestJSONFormatter:
    def test_format_produces_json(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello world", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["msg"] == "hello world"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test"

    def test_format_with_exception(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="test", level=logging.ERROR, pathname="", lineno=0,
                msg="failed", args=(), exc_info=sys.exc_info(),
            )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]


class TestSetupLogging:
    def test_setup_logging_debug_mode(self):
        with patch("app.main.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(debug=True)
            setup_logging()
            root = logging.getLogger()
            assert len(root.handlers) > 0

    def test_setup_logging_production_mode(self):
        with patch("app.main.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(debug=False)
            setup_logging()
            root = logging.getLogger()
            handler = root.handlers[0]
            assert isinstance(handler.formatter, JSONFormatter)
