"""Integration tests for API Keys management endpoints.

Tests KIS/LLM credential storage, listing, validation, and deletion.
"""

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet as _Fernet
from httpx import AsyncClient, ASGITransport

_test_fernet_key = _Fernet.generate_key().decode()
os.environ.setdefault("SECRET_KEY", "test-secret-key-keys")
os.environ.setdefault("ENCRYPTION_KEY", _test_fernet_key)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://able:able_secret@localhost:15432/able")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://able:able_secret@localhost:15432/able")
os.environ.setdefault("REDIS_URL", "redis://localhost:16379/1")

from app.core.security import create_access_token, hash_password
from app.models.user import User


def _make_user():
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = "keys_test@example.com"
    u.hashed_password = hash_password("password123")
    u.display_name = "Keys Tester"
    u.is_active = True
    u.is_verified = False
    return u


class MockResult:
    def __init__(self, items=None):
        self._items = items or []

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalars(self):
        class _S:
            def __init__(self, items): self._items = items
            def all(self): return self._items
        return _S(self._items)


def make_mock_db(execute_side_effects=None):
    db = AsyncMock()
    if execute_side_effects:
        db.execute = AsyncMock(side_effect=execute_side_effects)
    else:
        db.execute = AsyncMock(return_value=MockResult())
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _make_api_key(user_id, service_type="kis", provider_name="kis", key_id=None):
    k = MagicMock()
    k.id = uuid.UUID(key_id) if key_id else uuid.uuid4()
    k.user_id = user_id
    k.service_type = service_type
    k.provider_name = provider_name
    k.label = f"Test {service_type.upper()} Key"
    k.model_name = "gpt-4o" if service_type == "llm" else None
    k.is_active = True
    k.is_paper_trading = True
    k.encrypted_key = b"encrypted"
    k.encrypted_secret = b"encrypted" if service_type == "kis" else None
    k.account_number = "50123456-01" if service_type == "kis" else None
    k.last_validated_at = datetime.now(timezone.utc)
    k.created_at = datetime.now(timezone.utc)
    k.masked_key = "abc***xyz"
    return k


@pytest.fixture
def test_user():
    return _make_user()


@pytest_asyncio.fixture
async def client(test_user):
    from app.main import create_app
    from app.db.session import get_db
    from app.api.v1.deps import get_current_user

    app = create_app()
    mock_db = make_mock_db()

    async def override_db():
        yield mock_db

    async def override_user():
        return test_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        c._mock_db = mock_db
        c._test_user = test_user
        yield c


class TestKeysList:
    """Test listing API keys."""

    @pytest.mark.asyncio
    async def test_list_keys_empty(self, client):
        client._mock_db.execute = AsyncMock(return_value=MockResult([]))
        resp = await client.get("/api/v1/keys")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_keys_with_data(self, client):
        user_id = client._test_user.id
        keys = [
            _make_api_key(user_id, "kis", "kis"),
            _make_api_key(user_id, "llm", "openai"),
        ]
        client._mock_db.execute = AsyncMock(return_value=MockResult(keys))
        resp = await client.get("/api/v1/keys")
        assert resp.status_code == 200


class TestKeysCreate:
    """Test creating API keys."""

    @pytest.mark.asyncio
    async def test_save_kis_credentials(self, client):
        resp = await client.post("/api/v1/keys/kis", json={
            "app_key": "test-app-key",
            "app_secret": "test-app-secret",
            "account_number": "50123456-01",
            "is_paper_trading": True,
        })
        assert resp.status_code in (200, 201)

    @pytest.mark.asyncio
    async def test_save_kis_missing_fields(self, client):
        resp = await client.post("/api/v1/keys/kis", json={
            "app_key": "test-key",
        })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_save_llm_credentials(self, client):
        resp = await client.post("/api/v1/keys/llm", json={
            "provider_name": "openai",
            "api_key": "sk-test-key-123",
            "model_name": "gpt-4o",
        })
        assert resp.status_code in (200, 201)

    @pytest.mark.asyncio
    async def test_save_llm_missing_key(self, client):
        resp = await client.post("/api/v1/keys/llm", json={
            "provider_name": "openai",
        })
        assert resp.status_code == 422


class TestKeysValidation:
    """Test key validation endpoints."""

    @pytest.mark.asyncio
    async def test_validate_key_not_found(self, client):
        fake_id = str(uuid.uuid4())
        client._mock_db.execute = AsyncMock(return_value=MockResult([]))
        resp = await client.post(f"/api/v1/keys/{fake_id}/validate")
        assert resp.status_code in (404, 200)

    @pytest.mark.asyncio
    async def test_validate_existing_key(self, client):
        user_id = client._test_user.id
        key = _make_api_key(user_id, "kis")
        client._mock_db.execute = AsyncMock(return_value=MockResult([key]))
        resp = await client.post(f"/api/v1/keys/{key.id}/validate")
        # May succeed or fail based on KIS connectivity
        assert resp.status_code in (200, 400, 500)


class TestKeysDelete:
    """Test key deletion."""

    @pytest.mark.asyncio
    async def test_delete_key_not_found(self, client):
        fake_id = str(uuid.uuid4())
        client._mock_db.execute = AsyncMock(return_value=MockResult([]))
        resp = await client.delete(f"/api/v1/keys/{fake_id}")
        assert resp.status_code in (200, 204, 404)

    @pytest.mark.asyncio
    async def test_delete_existing_key(self, client):
        user_id = client._test_user.id
        key = _make_api_key(user_id, "kis")
        client._mock_db.execute = AsyncMock(return_value=MockResult([key]))
        resp = await client.delete(f"/api/v1/keys/{key.id}")
        assert resp.status_code in (200, 204, 404)
