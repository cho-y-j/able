"""Circuit breaker pattern for external service protection.

States: CLOSED → OPEN → HALF_OPEN → CLOSED (or back to OPEN)
"""

import time
import logging
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Protects external calls with circuit breaker pattern.

    Args:
        name: Identifier for this breaker (e.g., "kis_order", "kis_data")
        failure_threshold: Failures before opening the circuit
        recovery_timeout: Seconds to wait before trying half-open
        half_open_max_calls: Max calls allowed in half-open state
    """
    name: str
    failure_threshold: int = 3
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 1

    state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    failure_count: int = field(default=0, init=False)
    success_count: int = field(default=0, init=False)
    last_failure_time: float = field(default=0.0, init=False)
    half_open_calls: int = field(default=0, init=False)

    def can_execute(self) -> bool:
        """Check if a call is allowed through the breaker."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if time.monotonic() - self.last_failure_time >= self.recovery_timeout:
                self._transition(CircuitState.HALF_OPEN)
                return True
            return False

        # HALF_OPEN: allow limited calls
        if self.half_open_calls < self.half_open_max_calls:
            return True
        return False

    def record_success(self) -> None:
        """Record a successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_max_calls:
                self._transition(CircuitState.CLOSED)
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.monotonic()

        if self.state == CircuitState.HALF_OPEN:
            self._transition(CircuitState.OPEN)
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self._transition(CircuitState.OPEN)

    def _transition(self, new_state: CircuitState) -> None:
        old = self.state
        self.state = new_state
        logger.warning(f"Circuit breaker '{self.name}': {old.value} → {new_state.value}")

        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
            self.half_open_calls = 0
        elif new_state == CircuitState.HALF_OPEN:
            self.half_open_calls = 0
            self.success_count = 0
        elif new_state == CircuitState.OPEN:
            self.half_open_calls = 0
            self.success_count = 0

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
        }


class CircuitBreakerOpen(Exception):
    """Raised when a call is blocked by an open circuit breaker."""
    def __init__(self, breaker_name: str):
        self.breaker_name = breaker_name
        super().__init__(f"Circuit breaker '{breaker_name}' is OPEN")


# ── Global breakers ──────────────────────────────────────────

kis_order_breaker = CircuitBreaker(
    name="kis_order",
    failure_threshold=3,
    recovery_timeout=30.0,
)

kis_data_breaker = CircuitBreaker(
    name="kis_data",
    failure_threshold=5,
    recovery_timeout=60.0,
)


def get_all_breakers() -> list[CircuitBreaker]:
    return [kis_order_breaker, kis_data_breaker]
