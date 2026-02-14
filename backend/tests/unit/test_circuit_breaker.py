"""Tests for circuit breaker pattern implementation."""

import time
import pytest
from unittest.mock import patch

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
    get_all_breakers,
    kis_order_breaker,
    kis_data_breaker,
)


class TestCircuitBreakerStates:
    def test_initial_state_closed(self):
        cb = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=10)
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=10)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()  # 3rd failure → OPEN
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_blocks_calls_when_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=100)
        cb.record_failure()
        assert cb.is_open is True
        assert cb.can_execute() is False

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        cb.can_execute()  # transitions to HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        time.sleep(0.02)
        cb.can_execute()  # transitions to HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=10)
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2
        cb.record_success()
        assert cb.failure_count == 0

    def test_get_status(self):
        cb = CircuitBreaker(name="test_breaker", failure_threshold=3)
        status = cb.get_status()
        assert status["name"] == "test_breaker"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0


class TestGlobalBreakers:
    def test_get_all_breakers(self):
        breakers = get_all_breakers()
        assert len(breakers) == 2
        names = {b.name for b in breakers}
        assert "kis_order" in names
        assert "kis_data" in names

    def test_kis_order_breaker_config(self):
        assert kis_order_breaker.failure_threshold == 3
        assert kis_order_breaker.recovery_timeout == 30.0

    def test_kis_data_breaker_config(self):
        assert kis_data_breaker.failure_threshold == 5
        assert kis_data_breaker.recovery_timeout == 60.0


class TestCircuitBreakerOpen:
    def test_exception_message(self):
        exc = CircuitBreakerOpen("kis_order")
        assert "kis_order" in str(exc)
        assert exc.breaker_name == "kis_order"
