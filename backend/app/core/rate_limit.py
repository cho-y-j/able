"""In-memory rate limiter using sliding window counters.

No external dependencies — uses a simple dict with timestamps.
Suitable for single-process deployments. For multi-process,
swap the storage backend to Redis.
"""

import time
import logging
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import Request, HTTPException, status

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration: max `calls` per `window` seconds."""
    calls: int
    window: int  # seconds


# Default rate limits per route prefix
RATE_LIMITS: dict[str, RateLimitConfig] = {
    "/api/v1/auth/login": RateLimitConfig(calls=10, window=60),
    "/api/v1/auth/register": RateLimitConfig(calls=3, window=60),
    "/api/v1/auth/refresh": RateLimitConfig(calls=10, window=60),
    "/api/v1/keys": RateLimitConfig(calls=10, window=60),
    # General API: generous limit
    "/api/v1/": RateLimitConfig(calls=60, window=60),
}


class RateLimiter:
    """Sliding window counter rate limiter."""

    def __init__(self):
        # key -> list of timestamps
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _clean(self, key: str, window: int) -> None:
        """Remove expired timestamps."""
        cutoff = time.monotonic() - window
        self._requests[key] = [
            ts for ts in self._requests[key] if ts > cutoff
        ]

    def check(self, key: str, config: RateLimitConfig) -> tuple[bool, int]:
        """Check if request is allowed.

        Returns (allowed, remaining_calls).
        """
        self._clean(key, config.window)
        count = len(self._requests[key])
        if count >= config.calls:
            return False, 0
        return True, config.calls - count - 1

    def record(self, key: str) -> None:
        """Record a request."""
        self._requests[key].append(time.monotonic())

    def reset(self, key: str | None = None) -> None:
        """Reset rate limit state. If key is None, reset all."""
        if key is None:
            self._requests.clear()
        else:
            self._requests.pop(key, None)


# Singleton
_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _limiter


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _find_config(path: str) -> RateLimitConfig | None:
    """Find the most specific rate limit config for a path."""
    best_match = None
    best_len = 0
    for prefix, config in RATE_LIMITS.items():
        if path.startswith(prefix) and len(prefix) > best_len:
            best_match = config
            best_len = len(prefix)
    return best_match


async def rate_limit_middleware(request: Request, call_next):
    """FastAPI middleware that enforces rate limits."""
    path = request.url.path
    config = _find_config(path)

    if not config:
        return await call_next(request)

    ip = _get_client_ip(request)
    key = f"{ip}:{path}"

    # For more specific paths, use exact match; for general, use prefix
    # Auth endpoints: per-IP per-endpoint
    # General API: per-IP
    if path.startswith("/api/v1/auth/"):
        key = f"{ip}:{path}"
    else:
        key = f"{ip}:/api/v1/"

    limiter = get_rate_limiter()
    allowed, remaining = limiter.check(key, config)

    if not allowed:
        logger.warning(f"Rate limit exceeded: {ip} on {path}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
            headers={
                "Retry-After": str(config.window),
                "X-RateLimit-Limit": str(config.calls),
                "X-RateLimit-Remaining": "0",
            },
        )

    limiter.record(key)
    response = await call_next(request)

    # Add rate limit headers
    response.headers["X-RateLimit-Limit"] = str(config.calls)
    response.headers["X-RateLimit-Remaining"] = str(remaining)

    return response
