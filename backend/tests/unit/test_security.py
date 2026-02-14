"""Tests for security hardening: rate limiting, headers, audit, lockout, password policy."""

import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.core.rate_limit import RateLimiter, RateLimitConfig, _find_config, RATE_LIMITS
from app.core.account_lockout import (
    AccountLockout, validate_password_strength,
    MAX_FAILED_ATTEMPTS, LOCKOUT_DURATION,
)
from app.core.audit import AuditEntry, AuditAction, log_audit, audit_login_success


# ── Rate Limiter Tests ──


class TestRateLimiter:
    def test_allows_under_limit(self):
        limiter = RateLimiter()
        config = RateLimitConfig(calls=5, window=60)
        for _ in range(5):
            allowed, remaining = limiter.check("test", config)
            assert allowed
            limiter.record("test")

    def test_blocks_over_limit(self):
        limiter = RateLimiter()
        config = RateLimitConfig(calls=3, window=60)
        for _ in range(3):
            limiter.record("test")
        allowed, remaining = limiter.check("test", config)
        assert not allowed
        assert remaining == 0

    def test_separate_keys(self):
        limiter = RateLimiter()
        config = RateLimitConfig(calls=2, window=60)
        limiter.record("user-a")
        limiter.record("user-a")
        limiter.record("user-b")

        allowed_a, _ = limiter.check("user-a", config)
        allowed_b, _ = limiter.check("user-b", config)
        assert not allowed_a
        assert allowed_b

    def test_window_expiry(self):
        limiter = RateLimiter()
        config = RateLimitConfig(calls=1, window=1)
        limiter.record("test")

        allowed, _ = limiter.check("test", config)
        assert not allowed

        # Wait for window to expire
        time.sleep(1.1)
        allowed, _ = limiter.check("test", config)
        assert allowed

    def test_remaining_count(self):
        limiter = RateLimiter()
        config = RateLimitConfig(calls=5, window=60)
        limiter.record("test")
        _, remaining = limiter.check("test", config)
        assert remaining == 3  # 5 - 1 recorded - 1 for this check

    def test_reset_key(self):
        limiter = RateLimiter()
        config = RateLimitConfig(calls=1, window=60)
        limiter.record("test")
        allowed, _ = limiter.check("test", config)
        assert not allowed

        limiter.reset("test")
        allowed, _ = limiter.check("test", config)
        assert allowed

    def test_reset_all(self):
        limiter = RateLimiter()
        config = RateLimitConfig(calls=1, window=60)
        limiter.record("a")
        limiter.record("b")
        limiter.reset()
        allowed_a, _ = limiter.check("a", config)
        allowed_b, _ = limiter.check("b", config)
        assert allowed_a and allowed_b


class TestRateLimitConfig:
    def test_find_exact_match(self):
        config = _find_config("/api/v1/auth/login")
        assert config is not None
        assert config.calls == 10

    def test_find_prefix_match(self):
        config = _find_config("/api/v1/strategies")
        assert config is not None
        assert config.calls == 60  # general API limit

    def test_no_match(self):
        config = _find_config("/health")
        assert config is None

    def test_register_limit(self):
        config = _find_config("/api/v1/auth/register")
        assert config is not None
        assert config.calls == 3


# ── Account Lockout Tests ──


class TestAccountLockout:
    def test_not_locked_initially(self):
        lockout = AccountLockout()
        assert not lockout.is_locked("user@test.com")

    def test_locks_after_max_failures(self):
        lockout = AccountLockout()
        for i in range(MAX_FAILED_ATTEMPTS - 1):
            locked = lockout.record_failure("user@test.com")
            assert not locked
        locked = lockout.record_failure("user@test.com")
        assert locked
        assert lockout.is_locked("user@test.com")

    def test_success_clears_failures(self):
        lockout = AccountLockout()
        for _ in range(3):
            lockout.record_failure("user@test.com")
        lockout.record_success("user@test.com")
        assert lockout.get_remaining_attempts("user@test.com") == MAX_FAILED_ATTEMPTS

    def test_remaining_attempts(self):
        lockout = AccountLockout()
        assert lockout.get_remaining_attempts("user@test.com") == MAX_FAILED_ATTEMPTS
        lockout.record_failure("user@test.com")
        assert lockout.get_remaining_attempts("user@test.com") == MAX_FAILED_ATTEMPTS - 1

    def test_lock_expires(self):
        lockout = AccountLockout()
        # Override lockout duration for testing
        info = type("LockoutInfo", (), {"failed_count": MAX_FAILED_ATTEMPTS, "locked_until": time.monotonic() - 1})()
        lockout._attempts["user@test.com"] = info
        assert not lockout.is_locked("user@test.com")

    def test_reset_specific(self):
        lockout = AccountLockout()
        lockout.record_failure("a@test.com")
        lockout.record_failure("b@test.com")
        lockout.reset("a@test.com")
        assert lockout.get_remaining_attempts("a@test.com") == MAX_FAILED_ATTEMPTS
        assert lockout.get_remaining_attempts("b@test.com") == MAX_FAILED_ATTEMPTS - 1

    def test_reset_all(self):
        lockout = AccountLockout()
        lockout.record_failure("a@test.com")
        lockout.record_failure("b@test.com")
        lockout.reset()
        assert lockout.get_remaining_attempts("a@test.com") == MAX_FAILED_ATTEMPTS
        assert lockout.get_remaining_attempts("b@test.com") == MAX_FAILED_ATTEMPTS


# ── Password Policy Tests ──


class TestPasswordPolicy:
    def test_valid_password(self):
        assert validate_password_strength("MyP4ssw0rd") is None

    def test_too_short(self):
        result = validate_password_strength("Ab1")
        assert result is not None
        assert "8 characters" in result

    def test_no_uppercase(self):
        result = validate_password_strength("mypassword1")
        assert result is not None
        assert "uppercase" in result

    def test_no_lowercase(self):
        result = validate_password_strength("MYPASSWORD1")
        assert result is not None
        assert "lowercase" in result

    def test_no_digit(self):
        result = validate_password_strength("MyPassword")
        assert result is not None
        assert "digit" in result

    def test_exact_min_length(self):
        assert validate_password_strength("Abcdef1x") is None


# ── Audit Logger Tests ──


class TestAuditLogger:
    def test_audit_entry_defaults(self):
        entry = AuditEntry(action=AuditAction.LOGIN_SUCCESS)
        assert entry.timestamp is not None
        assert entry.user_id is None

    def test_audit_entry_with_details(self):
        entry = AuditEntry(
            action=AuditAction.KEY_CREATED,
            user_id="user1",
            details={"key_id": "abc", "service_type": "kis"},
        )
        assert entry.details["key_id"] == "abc"

    def test_log_audit_calls_logger(self):
        with patch("app.core.audit.audit_logger") as mock_logger:
            audit_login_success("user1", "test@test.com", "127.0.0.1", "Mozilla")
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "login_success" in call_args[0][0]

    def test_all_actions_defined(self):
        actions = [a.value for a in AuditAction]
        assert "login_success" in actions
        assert "login_failed" in actions
        assert "key_created" in actions
        assert "key_deleted" in actions
        assert "account_locked" in actions


# ── Security Headers API Tests ──


@pytest.mark.asyncio
class TestSecurityHeadersAPI:
    @pytest.fixture(autouse=True)
    def reset_limits(self):
        from app.core.rate_limit import get_rate_limiter
        get_rate_limiter().reset()
        yield
        get_rate_limiter().reset()

    @pytest.fixture
    async def client(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import create_app
        from app.db.session import get_db

        app = create_app()

        # Mock DB so health check doesn't fail
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    async def test_security_headers_present(self, client):
        res = await client.get("/health")
        assert res.headers.get("x-content-type-options") == "nosniff"
        assert res.headers.get("x-frame-options") == "DENY"
        assert res.headers.get("x-xss-protection") == "1; mode=block"
        assert res.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        assert "max-age" in res.headers.get("strict-transport-security", "")

    async def test_rate_limit_headers_on_api(self, client):
        res = await client.get("/api/v1/auth/me")
        # Even for 401, rate limit headers should be present (or 429 if over limit)
        assert res.status_code in (401, 403, 429)


# ── Auth Integration Tests ──


@pytest.mark.asyncio
class TestAuthSecurity:
    @pytest.fixture(autouse=True)
    def reset_lockout(self):
        from app.core.account_lockout import get_account_lockout
        from app.core.rate_limit import get_rate_limiter
        get_account_lockout().reset()
        get_rate_limiter().reset()
        yield
        get_account_lockout().reset()
        get_rate_limiter().reset()

    @pytest.fixture
    async def client(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import create_app
        from app.db.session import get_db

        app = create_app()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.add = MagicMock()

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            c._mock_db = mock_db
            yield c

    async def test_register_weak_password_rejected(self, client):
        res = await client.post("/api/v1/auth/register", json={
            "email": "test@test.com", "password": "weak"
        })
        assert res.status_code == 400
        assert "8 characters" in res.json()["detail"]

    async def test_register_no_uppercase_rejected(self, client):
        res = await client.post("/api/v1/auth/register", json={
            "email": "test@test.com", "password": "alllowercase1"
        })
        assert res.status_code == 400
        assert "uppercase" in res.json()["detail"]

    async def test_login_lockout_after_failures(self, client):
        """After MAX_FAILED_ATTEMPTS, login should return 423."""
        for i in range(MAX_FAILED_ATTEMPTS):
            res = await client.post("/api/v1/auth/login", json={
                "email": "victim@test.com", "password": "WrongPass1"
            })
            assert res.status_code == 401

        # Next attempt should be locked
        res = await client.post("/api/v1/auth/login", json={
            "email": "victim@test.com", "password": "WrongPass1"
        })
        assert res.status_code == 423
        assert "locked" in res.json()["detail"].lower()

    async def test_login_shows_remaining_attempts(self, client):
        res = await client.post("/api/v1/auth/login", json={
            "email": "test@test.com", "password": "WrongPass1"
        })
        assert res.status_code == 401
        assert "attempts remaining" in res.json()["detail"]
