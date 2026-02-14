"""Account lockout after repeated failed login attempts.

In-memory tracker. For multi-process deployments, swap to Redis.
"""

import time
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = 900  # 15 minutes in seconds

# Password policy
MIN_PASSWORD_LENGTH = 8
PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$"
)


@dataclass
class LockoutInfo:
    failed_count: int = 0
    locked_until: float = 0.0  # monotonic time


class AccountLockout:
    """Tracks failed login attempts per email."""

    def __init__(self):
        self._attempts: dict[str, LockoutInfo] = {}

    def is_locked(self, email: str) -> bool:
        """Check if account is currently locked."""
        info = self._attempts.get(email)
        if not info:
            return False
        if info.locked_until > 0 and time.monotonic() < info.locked_until:
            return True
        # Lock expired
        if info.locked_until > 0 and time.monotonic() >= info.locked_until:
            self._attempts.pop(email, None)
            return False
        return False

    def record_failure(self, email: str) -> bool:
        """Record a failed login. Returns True if account is now locked."""
        info = self._attempts.get(email)
        if not info:
            info = LockoutInfo()
            self._attempts[email] = info

        info.failed_count += 1
        if info.failed_count >= MAX_FAILED_ATTEMPTS:
            info.locked_until = time.monotonic() + LOCKOUT_DURATION
            logger.warning(f"Account locked: {email} after {info.failed_count} failures")
            return True
        return False

    def record_success(self, email: str) -> None:
        """Clear failed attempts on successful login."""
        self._attempts.pop(email, None)

    def get_remaining_attempts(self, email: str) -> int:
        info = self._attempts.get(email)
        if not info:
            return MAX_FAILED_ATTEMPTS
        return max(0, MAX_FAILED_ATTEMPTS - info.failed_count)

    def reset(self, email: str | None = None) -> None:
        """Reset lockout state."""
        if email is None:
            self._attempts.clear()
        else:
            self._attempts.pop(email, None)


# Singleton
_lockout = AccountLockout()


def get_account_lockout() -> AccountLockout:
    return _lockout


def validate_password_strength(password: str) -> str | None:
    """Validate password meets policy. Returns error message or None."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
    if not PASSWORD_PATTERN.match(password):
        return "Password must contain at least one uppercase letter, one lowercase letter, and one digit"
    return None
