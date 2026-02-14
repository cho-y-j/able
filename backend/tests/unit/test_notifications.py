"""Tests for notification system: service, API, channels."""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.notification_service import (
    NotificationService, NotificationPayload, NotificationCategory,
    notify_order_filled, notify_order_rejected,
    notify_agent_started, notify_agent_completed, notify_agent_error,
    notify_pending_approval, notify_pnl_alert,
)


# ── NotificationPayload Tests ──


class TestNotificationPayload:
    def test_basic_payload(self):
        p = NotificationPayload(
            user_id="user1",
            category=NotificationCategory.ORDER,
            title="Order Filled",
            message="Bought 10 shares",
        )
        assert p.user_id == "user1"
        assert p.category == NotificationCategory.ORDER
        assert p.send_email is False
        assert p.data is None

    def test_payload_with_data(self):
        p = NotificationPayload(
            user_id="user1",
            category=NotificationCategory.ALERT,
            title="Alert",
            message="Test",
            data={"key": "val"},
            link="/dashboard",
            send_email=True,
        )
        assert p.data == {"key": "val"}
        assert p.link == "/dashboard"
        assert p.send_email is True


class TestNotificationCategories:
    def test_all_categories(self):
        cats = [c.value for c in NotificationCategory]
        assert "trade" in cats
        assert "agent" in cats
        assert "order" in cats
        assert "position" in cats
        assert "system" in cats
        assert "alert" in cats


# ── NotificationService Tests ──


class TestNotificationService:
    @pytest.mark.asyncio
    async def test_send_saves_to_db(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        payload = NotificationPayload(
            user_id=str(uuid.uuid4()),
            category=NotificationCategory.ORDER,
            title="Test",
            message="Test msg",
        )

        with patch.object(NotificationService, "_send_websocket", new_callable=AsyncMock):
            results = await NotificationService.send(payload, db=mock_db)

        assert results["in_app"]["status"] == "ok"
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_pushes_websocket(self):
        payload = NotificationPayload(
            user_id="user1",
            category=NotificationCategory.AGENT,
            title="Agent Started",
            message="Test",
        )

        with patch("app.services.notification_service.NotificationService._send_websocket", new_callable=AsyncMock) as mock_ws:
            results = await NotificationService.send(payload)

        assert results["websocket"]["status"] == "ok"
        mock_ws.assert_called_once_with(payload)

    @pytest.mark.asyncio
    async def test_send_without_db(self):
        payload = NotificationPayload(
            user_id="user1",
            category=NotificationCategory.SYSTEM,
            title="Test",
            message="Test",
        )

        with patch.object(NotificationService, "_send_websocket", new_callable=AsyncMock):
            results = await NotificationService.send(payload, db=None)

        assert "in_app" not in results  # No DB, no in-app save
        assert results["websocket"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_send_email_when_requested(self):
        payload = NotificationPayload(
            user_id="user1",
            category=NotificationCategory.ALERT,
            title="Critical",
            message="Alert!",
            send_email=True,
        )

        with patch.object(NotificationService, "_send_websocket", new_callable=AsyncMock), \
             patch.object(NotificationService, "_send_email") as mock_email:
            results = await NotificationService.send(payload)

        mock_email.assert_called_once_with(payload)

    @pytest.mark.asyncio
    async def test_send_no_email_by_default(self):
        payload = NotificationPayload(
            user_id="user1",
            category=NotificationCategory.ORDER,
            title="Order",
            message="Filled",
        )

        with patch.object(NotificationService, "_send_websocket", new_callable=AsyncMock), \
             patch.object(NotificationService, "_send_email") as mock_email:
            await NotificationService.send(payload)

        mock_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_websocket_channel_calls_manager(self):
        payload = NotificationPayload(
            user_id="user1",
            category=NotificationCategory.TRADE,
            title="Trade",
            message="Executed",
            data={"stock": "005930"},
        )

        with patch("app.api.v1.websocket.manager") as mock_manager:
            mock_manager.send_to_user = AsyncMock()
            await NotificationService._send_websocket(payload)

            mock_manager.send_to_user.assert_called_once()
            call_args = mock_manager.send_to_user.call_args
            assert call_args[0][0] == "user1"
            msg = call_args[0][1]
            assert msg["type"] == "notification"
            assert msg["category"] == "trade"

    @pytest.mark.asyncio
    async def test_db_error_doesnt_crash(self):
        mock_db = AsyncMock()
        mock_db.add = MagicMock(side_effect=Exception("DB error"))

        payload = NotificationPayload(
            user_id=str(uuid.uuid4()),
            category=NotificationCategory.SYSTEM,
            title="Test",
            message="msg",
        )

        with patch.object(NotificationService, "_send_websocket", new_callable=AsyncMock):
            results = await NotificationService.send(payload, db=mock_db)

        assert results["in_app"]["status"] == "error"
        assert results["websocket"]["status"] == "ok"


# ── Convenience Function Tests ──


class TestConvenienceFunctions:
    @pytest.mark.asyncio
    async def test_notify_order_filled(self):
        with patch.object(NotificationService, "send", new_callable=AsyncMock) as mock:
            await notify_order_filled("user1", "005930", "buy", 10, 70000.0)

        mock.assert_called_once()
        payload = mock.call_args[0][0]
        assert payload.category == NotificationCategory.ORDER
        assert "005930" in payload.title
        assert "BUY" in payload.title

    @pytest.mark.asyncio
    async def test_notify_order_rejected(self):
        with patch.object(NotificationService, "send", new_callable=AsyncMock) as mock:
            await notify_order_rejected("user1", "005930", "buy", "insufficient cash")

        payload = mock.call_args[0][0]
        assert "Rejected" in payload.title
        assert "insufficient cash" in payload.message

    @pytest.mark.asyncio
    async def test_notify_agent_started(self):
        with patch.object(NotificationService, "send", new_callable=AsyncMock) as mock:
            await notify_agent_started("user1", "session-1", "full_cycle")

        payload = mock.call_args[0][0]
        assert payload.category == NotificationCategory.AGENT
        assert "Started" in payload.title

    @pytest.mark.asyncio
    async def test_notify_agent_completed(self):
        with patch.object(NotificationService, "send", new_callable=AsyncMock) as mock:
            await notify_agent_completed("user1", "session-1", 3)

        payload = mock.call_args[0][0]
        assert "Completed" in payload.title
        assert "3" in payload.message

    @pytest.mark.asyncio
    async def test_notify_agent_error_sends_email(self):
        with patch.object(NotificationService, "send", new_callable=AsyncMock) as mock:
            await notify_agent_error("user1", "session-1", "timeout")

        payload = mock.call_args[0][0]
        assert payload.send_email is True
        assert "Error" in payload.title

    @pytest.mark.asyncio
    async def test_notify_pending_approval_sends_email(self):
        with patch.object(NotificationService, "send", new_callable=AsyncMock) as mock:
            await notify_pending_approval("user1", "session-1", 3, 15_000_000)

        payload = mock.call_args[0][0]
        assert payload.send_email is True
        assert payload.category == NotificationCategory.TRADE
        assert "Pending" in payload.title

    @pytest.mark.asyncio
    async def test_notify_pnl_alert(self):
        with patch.object(NotificationService, "send", new_callable=AsyncMock) as mock:
            await notify_pnl_alert("user1", "005930", -500000, -5.2)

        payload = mock.call_args[0][0]
        assert payload.category == NotificationCategory.ALERT
        assert "005930" in payload.title
        assert "-5.2%" in payload.title


# ── Notification API Tests ──


@pytest.mark.asyncio
class TestNotificationAPI:
    @pytest.fixture
    async def client(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import create_app
        from app.db.session import get_db
        from app.api.v1.deps import get_current_user

        app = create_app()
        user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        class FakeUser:
            id = user_id
            email = "test@test.com"

        # Mock notifications in DB
        fake_notif = MagicMock()
        fake_notif.id = uuid.uuid4()
        fake_notif.user_id = user_id
        fake_notif.category = "order"
        fake_notif.title = "Test Notification"
        fake_notif.message = "Test message"
        fake_notif.is_read = False
        fake_notif.data = None
        fake_notif.link = None
        fake_notif.created_at = MagicMock()
        fake_notif.created_at.isoformat.return_value = "2024-01-01T00:00:00"

        # Scalars mock for notification list
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [fake_notif]

        mock_result_list = MagicMock()
        mock_result_list.scalars.return_value = mock_scalars

        mock_result_count = MagicMock()
        mock_result_count.scalar.return_value = 1

        # Fake preference object
        fake_pref = MagicMock()
        fake_pref.in_app_enabled = True
        fake_pref.email_enabled = False
        fake_pref.trade_alerts = True
        fake_pref.agent_alerts = True
        fake_pref.order_alerts = True
        fake_pref.position_alerts = True
        fake_pref.system_alerts = True
        fake_pref.email_address = None

        # Universal mock result that supports both .scalars().all() and .scalar_one_or_none() and .scalar()
        class UniversalResult:
            def __init__(self, items, scalar_val=None, single=None):
                self._items = items
                self._scalar_val = scalar_val
                self._single = single

            def scalars(self):
                m = MagicMock()
                m.all.return_value = self._items
                return m

            def scalar(self):
                return self._scalar_val

            def scalar_one_or_none(self):
                return self._single

        mock_db = AsyncMock()

        async def dynamic_execute(*args, **kwargs):
            # Inspect the query to return appropriate result
            query_str = str(args[0]) if args else ""
            if "notification_preferences" in query_str:
                return UniversalResult([], scalar_val=None, single=fake_pref)
            elif "COUNT" in query_str or "count" in query_str:
                return UniversalResult([], scalar_val=1, single=None)
            else:
                return UniversalResult([fake_notif], scalar_val=None, single=fake_notif)

        mock_db.execute = dynamic_execute
        mock_db.add = MagicMock()

        async def override_db():
            yield mock_db

        async def override_user():
            return FakeUser()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    async def test_list_notifications(self, client):
        res = await client.get("/api/v1/notifications")
        assert res.status_code == 200
        data = res.json()
        assert "notifications" in data
        assert "unread_count" in data
        assert len(data["notifications"]) >= 1

    async def test_unread_count(self, client):
        res = await client.get("/api/v1/notifications/unread-count")
        assert res.status_code == 200
        assert "unread_count" in res.json()

    async def test_mark_all_read(self, client):
        res = await client.post("/api/v1/notifications/read-all")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

    async def test_get_preferences(self, client):
        res = await client.get("/api/v1/notifications/preferences")
        assert res.status_code == 200
        data = res.json()
        assert "in_app_enabled" in data
        assert "email_enabled" in data
        assert "trade_alerts" in data

    async def test_update_preferences(self, client):
        res = await client.put("/api/v1/notifications/preferences", json={
            "email_enabled": True,
            "trade_alerts": False,
        })
        assert res.status_code == 200
