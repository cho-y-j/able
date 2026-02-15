"""Integration tests for Notification API endpoints.

Tests list, mark read, mark all read, unread count, and preferences CRUD.
"""

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet as _Fernet
from httpx import AsyncClient, ASGITransport

_test_fernet_key = _Fernet.generate_key().decode()
os.environ.setdefault("SECRET_KEY", "test-secret-key-notif")
os.environ.setdefault("ENCRYPTION_KEY", _test_fernet_key)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://able:able_secret@localhost:15432/able")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://able:able_secret@localhost:15432/able")
os.environ.setdefault("REDIS_URL", "redis://localhost:16379/1")

from app.core.security import hash_password
from app.models.user import User
from app.models.notification import Notification, NotificationPreference


# ─── Helpers ─────────────────────────────────────────────────

def _make_user():
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.email = "notif_test@example.com"
    u.hashed_password = hash_password("password123")
    u.display_name = "Notif Tester"
    u.is_active = True
    u.is_verified = False
    return u


class MockScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


class MockResult:
    def __init__(self, items=None, scalar_val=None):
        self._items = items or []
        self._scalar_val = scalar_val

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalar(self):
        return self._scalar_val

    def scalars(self):
        return MockScalarResult(self._items)


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
    return db


def _make_notification(user_id, category="trade", is_read=False, notif_id=None):
    n = MagicMock(spec=Notification)
    n.id = uuid.UUID(notif_id) if notif_id else uuid.uuid4()
    n.user_id = user_id
    n.category = category
    n.title = f"Test {category} notification"
    n.message = f"This is a test {category} message"
    n.is_read = is_read
    n.data = {"test": True}
    n.link = "/dashboard/trading"
    n.created_at = datetime.now(timezone.utc)
    return n


def _make_preference(user_id):
    p = MagicMock(spec=NotificationPreference)
    p.user_id = user_id
    p.in_app_enabled = True
    p.email_enabled = False
    p.trade_alerts = True
    p.agent_alerts = True
    p.order_alerts = True
    p.position_alerts = True
    p.system_alerts = True
    p.email_address = None
    return p


# ─── Fixtures ────────────────────────────────────────────────

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


# ─── Tests ───────────────────────────────────────────────────

class TestNotificationsList:
    """Test listing notifications."""

    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        async def _side(*a, **k):
            return MockResult([], scalar_val=0)
        client._mock_db.execute = AsyncMock(side_effect=_side)
        resp = await client.get("/api/v1/notifications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unread_count"] == 0

    @pytest.mark.asyncio
    async def test_list_with_notifications(self, client):
        user_id = client._test_user.id
        notifs = [
            _make_notification(user_id, "trade"),
            _make_notification(user_id, "agent", is_read=True),
        ]
        call_count = 0
        async def _side(*a, **k):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MockResult(notifs)
            return MockResult(scalar_val=1 if call_count == 2 else 2)
        client._mock_db.execute = AsyncMock(side_effect=_side)
        resp = await client.get("/api/v1/notifications")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_filter_by_category(self, client):
        async def _side(*a, **k):
            return MockResult([], scalar_val=0)
        client._mock_db.execute = AsyncMock(side_effect=_side)
        resp = await client.get("/api/v1/notifications?category=agent")
        assert resp.status_code == 200


class TestUnreadCount:
    """Test unread count endpoint."""

    @pytest.mark.asyncio
    async def test_unread_count_zero(self, client):
        client._mock_db.execute = AsyncMock(return_value=MockResult(scalar_val=0))
        resp = await client.get("/api/v1/notifications/unread-count")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 0

    @pytest.mark.asyncio
    async def test_unread_count_nonzero(self, client):
        client._mock_db.execute = AsyncMock(return_value=MockResult(scalar_val=5))
        resp = await client.get("/api/v1/notifications/unread-count")
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 5


class TestMarkRead:
    """Test mark read endpoints."""

    @pytest.mark.asyncio
    async def test_mark_read_success(self, client):
        user_id = client._test_user.id
        notif = _make_notification(user_id, is_read=False)
        client._mock_db.execute = AsyncMock(return_value=MockResult([notif]))
        resp = await client.post(f"/api/v1/notifications/{notif.id}/read")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        # Verify commit was called (bug fix)
        assert client._mock_db.commit.called

    @pytest.mark.asyncio
    async def test_mark_read_not_found(self, client):
        fake_id = str(uuid.uuid4())
        client._mock_db.execute = AsyncMock(return_value=MockResult([]))
        resp = await client.post(f"/api/v1/notifications/{fake_id}/read")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_mark_all_read(self, client):
        client._mock_db.execute = AsyncMock(return_value=MockResult())
        resp = await client.post("/api/v1/notifications/read-all")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        # Verify commit was called (bug fix)
        assert client._mock_db.commit.called


class TestPreferences:
    """Test notification preferences CRUD."""

    @pytest.mark.asyncio
    async def test_get_preferences_default(self, client):
        client._mock_db.execute = AsyncMock(return_value=MockResult([]))
        resp = await client.get("/api/v1/notifications/preferences")
        assert resp.status_code == 200
        data = resp.json()
        assert data["in_app_enabled"] is True
        assert data["email_enabled"] is False

    @pytest.mark.asyncio
    async def test_get_preferences_existing(self, client):
        pref = _make_preference(client._test_user.id)
        pref.email_enabled = True
        pref.email_address = "test@example.com"
        client._mock_db.execute = AsyncMock(return_value=MockResult([pref]))
        resp = await client.get("/api/v1/notifications/preferences")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email_enabled"] is True

    @pytest.mark.asyncio
    async def test_update_preferences(self, client):
        pref = _make_preference(client._test_user.id)
        client._mock_db.execute = AsyncMock(return_value=MockResult([pref]))
        resp = await client.put("/api/v1/notifications/preferences", json={
            "email_enabled": True,
            "email_address": "new@example.com",
        })
        assert resp.status_code == 200
        # Verify commit was called
        assert client._mock_db.commit.called

    @pytest.mark.asyncio
    async def test_create_preferences_if_not_exists(self, client):
        client._mock_db.execute = AsyncMock(return_value=MockResult([]))
        resp = await client.put("/api/v1/notifications/preferences", json={
            "trade_alerts": False,
        })
        assert resp.status_code == 200
        # Verify add was called for new preference
        assert client._mock_db.add.called
