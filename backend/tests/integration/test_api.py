"""Integration tests for ABLE Platform API endpoints.

These tests use a real database (if available) or skip gracefully.
They test the full request → response cycle including authentication.
"""

import os
import uuid
import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

# Set test environment before importing app
from cryptography.fernet import Fernet as _Fernet
_test_fernet_key = _Fernet.generate_key().decode()
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests")
os.environ.setdefault("ENCRYPTION_KEY", _test_fernet_key)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://able:able_secret@localhost:15432/able")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://able:able_secret@localhost:15432/able")
os.environ.setdefault("REDIS_URL", "redis://localhost:16379/1")

from app.core.security import create_access_token, hash_password
from app.core.encryption import KeyVault


# ─── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def test_user_id():
    return str(uuid.uuid4())


@pytest.fixture
def auth_token(test_user_id):
    """Create a valid JWT token for testing."""
    return create_access_token({"sub": test_user_id})


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ─── Unit-level tests (no DB required) ──────────────────────────────

class TestSecurity:
    """Test security module (JWT, password hashing)."""

    def test_password_hash_verify(self):
        from app.core.security import hash_password, verify_password
        hashed = hash_password("test123")
        assert verify_password("test123", hashed)
        assert not verify_password("wrong", hashed)

    def test_create_access_token(self):
        from app.core.security import create_access_token, decode_token
        token = create_access_token({"sub": "user-123"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"

    def test_create_refresh_token(self):
        from app.core.security import create_refresh_token, decode_token
        token = create_refresh_token({"sub": "user-123"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["type"] == "refresh"

    def test_decode_invalid_token(self):
        from app.core.security import decode_token
        assert decode_token("invalid-token") is None


class TestEncryption:
    """Test Fernet encryption module."""

    def test_encrypt_decrypt(self):
        vault = KeyVault()
        original = "my-secret-api-key"
        encrypted = vault.encrypt(original)
        assert isinstance(encrypted, bytes)
        assert encrypted != original.encode()
        decrypted = vault.decrypt(encrypted)
        assert decrypted == original

    def test_encrypt_different_values(self):
        vault = KeyVault()
        enc1 = vault.encrypt("key-1")
        enc2 = vault.encrypt("key-2")
        assert enc1 != enc2
        assert vault.decrypt(enc1) == "key-1"
        assert vault.decrypt(enc2) == "key-2"


class TestConfigLoading:
    """Test configuration loading."""

    def test_settings_load(self):
        from app.config import Settings
        settings = Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            database_url_sync="postgresql://test:test@localhost/test",
            secret_key="test-key",
        )
        assert settings.app_name == "ABLE"
        assert settings.access_token_expire_minutes == 15
        assert settings.refresh_token_expire_days == 7


class TestKISConstants:
    """Test KIS API constants are properly defined."""

    def test_all_constants_exist(self):
        from app.integrations.kis.constants import (
            REAL_BASE_URL, PAPER_BASE_URL,
            TOKEN_PATH, STOCK_PRICE_PATH, STOCK_DAILY_PRICE_PATH,
            ORDER_PATH, ORDER_CANCEL_PATH, BALANCE_PATH,
            TR_ID_BUY, TR_ID_SELL, TR_ID_BUY_PAPER, TR_ID_SELL_PAPER,
            TR_ID_BALANCE, TR_ID_BALANCE_PAPER, TR_ID_PRICE, TR_ID_DAILY_PRICE,
        )
        assert "openapi" in REAL_BASE_URL
        assert "openapivts" in PAPER_BASE_URL
        assert TR_ID_BUY.startswith("T")
        assert TR_ID_BUY_PAPER.startswith("V")


class TestKISClient:
    """Test KIS client initialization and request building."""

    def test_client_init_paper(self):
        from app.integrations.kis.client import KISClient
        client = KISClient("key", "secret", "1234567801", is_paper=True)
        assert client.is_paper
        assert "vts" in client.base_url
        assert client.account_prefix == "12345678"
        assert client.account_suffix == "01"

    def test_client_init_real(self):
        from app.integrations.kis.client import KISClient
        client = KISClient("key", "secret", "1234567801", is_paper=False)
        assert not client.is_paper
        assert "vts" not in client.base_url

    @pytest.mark.asyncio
    async def test_validate_credentials_failure(self):
        from app.integrations.kis.client import KISClient
        client = KISClient("invalid_key", "invalid_secret", "1234567801")
        valid = await client.validate_credentials()
        assert not valid


class TestLLMProviderFactory:
    """Test LLM provider factory."""

    def test_openai_provider(self):
        from app.integrations.llm.openai_provider import OpenAIProvider
        provider = OpenAIProvider()
        model = provider.create_chat_model("fake-key", "gpt-4o")
        assert model is not None

    def test_anthropic_provider(self):
        from app.integrations.llm.anthropic_provider import AnthropicProvider
        provider = AnthropicProvider()
        model = provider.create_chat_model("fake-key", "claude-sonnet-4-5-20250929")
        assert model is not None

    def test_google_provider(self):
        from app.integrations.llm.google_provider import GoogleProvider
        provider = GoogleProvider()
        model = provider.create_chat_model("fake-key", "gemini-2.0-flash")
        assert model is not None

    def test_supported_providers(self):
        from app.integrations.llm.factory import get_supported_providers
        providers = get_supported_providers()
        assert "openai" in providers
        assert "anthropic" in providers
        assert "google" in providers


class TestStrategyScoring:
    """Test strategy scoring system."""

    def test_score_strategy_good(self):
        from app.analysis.validation.scoring import score_strategy
        result = score_strategy({
            "sharpe_ratio": 2.0,
            "sortino_ratio": 2.5,
            "max_drawdown": -5,
            "win_rate": 65,
            "profit_factor": 2.0,
            "total_trades": 100,
            "calmar_ratio": 3.0,
            "annual_return": 30,
            "mc_score": 75,
            "oos_score": 65,
        })
        assert result["total_score"] > 50
        assert result["grade"] in ("A+", "A", "B+", "B", "C+", "C", "D", "F")

    def test_score_strategy_poor(self):
        from app.analysis.validation.scoring import score_strategy
        result = score_strategy({
            "sharpe_ratio": -0.5,
            "sortino_ratio": -0.5,
            "max_drawdown": -40,
            "win_rate": 30,
            "profit_factor": 0.5,
            "total_trades": 5,
            "calmar_ratio": -1.0,
            "annual_return": -10,
        })
        assert result["total_score"] < 40

    def test_calculate_composite_score(self):
        from app.analysis.validation.scoring import calculate_composite_score
        result = calculate_composite_score({"sharpe_ratio": 1.5, "annual_return": 20})
        assert "composite_score" in result
        assert "grade" in result
        assert "individual_scores" in result


class TestCeleryAppConfig:
    """Test Celery configuration."""

    def test_celery_config(self):
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.timezone == "Asia/Seoul"
        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.enable_utc is True

    def test_beat_schedule_defined(self):
        from app.tasks.celery_app import celery_app
        schedule = celery_app.conf.beat_schedule
        assert "update-position-prices" in schedule
        assert "auto-agent-market-open" in schedule
        assert "midday-portfolio-check" in schedule


class TestAgentNodes:
    """Test agent node functions."""

    @pytest.mark.asyncio
    async def test_market_analyst_fallback(self):
        """Market analyst should fall back to rule-based when no LLM."""
        from app.agents.nodes.market_analyst import market_analyst_node
        state = {
            "messages": [],
            "watchlist": ["005930"],
            "market_regime": None,
            "strategy_candidates": [],
        }
        result = await market_analyst_node(state)
        assert "market_regime" in result
        regime = result["market_regime"]
        assert regime["classification"] in ("bull", "bear", "sideways", "volatile", "crisis")

    @pytest.mark.asyncio
    async def test_risk_manager_no_candidates(self):
        """Risk manager with no candidates should still return valid state."""
        from app.agents.nodes.risk_manager import risk_manager_node
        state = {
            "messages": [],
            "strategy_candidates": [],
            "risk_assessment": None,
            "portfolio_snapshot": {},
            "market_regime": {"classification": "sideways"},
        }
        result = await risk_manager_node(state)
        assert "risk_assessment" in result

    @pytest.mark.asyncio
    async def test_execution_no_approved(self):
        """Execution with no approved stocks should return empty orders."""
        from app.agents.nodes.execution import execution_node
        state = {
            "messages": [],
            "risk_assessment": {"approved_stocks": [], "max_position_size": 0},
            "pending_orders": [],
        }
        result = await execution_node(state)
        assert "pending_orders" in result

    @pytest.mark.asyncio
    async def test_monitor_node(self):
        """Monitor should set should_continue and portfolio snapshot."""
        from app.agents.nodes.monitor import monitor_node
        state = {
            "messages": [],
            "pending_orders": [],
            "executed_orders": [],
            "portfolio_snapshot": {},
            "alerts": [],
            "iteration_count": 0,
            "should_continue": True,
        }
        result = await monitor_node(state)
        assert "should_continue" in result
        assert "portfolio_snapshot" in result
        assert result["should_continue"] is True  # iteration 0 < MAX_ITERATIONS


class TestFastAPIAppCreation:
    """Test FastAPI app factory."""

    def test_app_creation(self):
        from app.main import create_app
        app = create_app()
        assert app.title == "ABLE"
        # Check that routes are registered
        route_paths = [getattr(r, "path", "") for r in app.routes]
        assert "/health" in route_paths
        # Auth routes are under /api/v1
        assert any("/api/v1" in p for p in route_paths)
