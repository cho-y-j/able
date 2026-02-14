"""End-to-End integration tests for the full ABLE Platform API.

Tests the complete user journey through the API:
- Auth flow (register → login → refresh → me)
- Strategy CRUD lifecycle
- Agent session lifecycle with HITL
- Trading operations (orders, positions, portfolio analytics)
- Health and metrics endpoints
- Error handling and edge cases
"""

import os
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import patch, AsyncMock, MagicMock, PropertyMock

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet as _Fernet
from httpx import AsyncClient, ASGITransport

# Set test environment before importing app
_test_fernet_key = _Fernet.generate_key().decode()
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-e2e")
os.environ.setdefault("ENCRYPTION_KEY", _test_fernet_key)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://able:able_secret@localhost:15432/able")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://able:able_secret@localhost:15432/able")
os.environ.setdefault("REDIS_URL", "redis://localhost:16379/1")

from app.core.security import create_access_token, hash_password
from app.models.user import User
from app.models.strategy import Strategy
from app.models.order import Order
from app.models.position import Position
from app.models.trade import Trade
from app.models.agent_session import AgentSession, AgentAction


# ─── Helpers ─────────────────────────────────────────────────

def _make_user(user_id=None, email="test@example.com", display_name="Tester"):
    """Create a mock User instance."""
    u = MagicMock(spec=User)
    u.id = uuid.UUID(user_id) if user_id else uuid.uuid4()
    u.email = email
    u.hashed_password = hash_password("password123")
    u.display_name = display_name
    u.is_active = True
    u.is_verified = False
    return u


def _make_strategy(user_id, name="RSI Momentum", stock_code="005930", strategy_id=None):
    """Create a mock Strategy instance."""
    s = MagicMock(spec=Strategy)
    s.id = uuid.UUID(strategy_id) if strategy_id else uuid.uuid4()
    s.user_id = user_id
    s.name = name
    s.stock_code = stock_code
    s.stock_name = "Samsung Electronics"
    s.strategy_type = "indicator_based"
    s.indicators = [{"name": "RSI", "params": {"period": 14}}]
    s.parameters = {"rsi_oversold": 30, "rsi_overbought": 70}
    s.entry_rules = {"type": "rsi_crossover"}
    s.exit_rules = {"type": "rsi_exit"}
    s.risk_params = {"stop_loss_pct": 3}
    s.composite_score = 72.5
    s.validation_results = {"grade": "B+"}
    s.status = "draft"
    s.is_auto_trading = False
    s.created_at = datetime.now(timezone.utc)
    s.updated_at = datetime.now(timezone.utc)
    s.description = None
    return s


def _make_order(user_id, stock_code="005930", side="buy", status="submitted", order_id=None):
    """Create a mock Order instance."""
    o = MagicMock(spec=Order)
    o.id = uuid.UUID(order_id) if order_id else uuid.uuid4()
    o.user_id = user_id
    o.stock_code = stock_code
    o.stock_name = "Samsung"
    o.side = side
    o.order_type = "market"
    o.quantity = 10
    o.limit_price = None
    o.filled_quantity = 0
    o.avg_fill_price = None
    o.kis_order_id = "KIS12345" if status == "submitted" else None
    o.status = status
    o.submitted_at = datetime.now(timezone.utc) if status == "submitted" else None
    o.filled_at = None
    o.created_at = datetime.now(timezone.utc)
    o.strategy_id = None
    return o


def _make_position(user_id, stock_code="005930", quantity=100, strategy_id=None):
    """Create a mock Position instance."""
    p = MagicMock(spec=Position)
    p.id = uuid.uuid4()
    p.user_id = user_id
    p.stock_code = stock_code
    p.stock_name = "Samsung"
    p.quantity = quantity
    p.avg_cost_price = Decimal("65000")
    p.current_price = Decimal("68000")
    p.unrealized_pnl = Decimal("300000")
    p.realized_pnl = Decimal("0")
    p.strategy_id = strategy_id
    return p


def _make_trade(user_id, pnl=50000, pnl_percent=5.0, stock_code="005930", strategy_id=None):
    """Create a mock Trade instance."""
    t = MagicMock(spec=Trade)
    t.id = uuid.uuid4()
    t.user_id = user_id
    t.strategy_id = strategy_id
    t.stock_code = stock_code
    t.side = "buy"
    t.entry_price = Decimal("65000")
    t.exit_price = Decimal("68000")
    t.quantity = 10
    t.pnl = Decimal(str(pnl))
    t.pnl_percent = pnl_percent
    t.entry_at = datetime.now(timezone.utc) - timedelta(days=1)
    t.exit_at = datetime.now(timezone.utc)
    return t


def _make_session(user_id, status="active", session_id=None):
    """Create a mock AgentSession instance."""
    s = MagicMock(spec=AgentSession)
    s.id = uuid.UUID(session_id) if session_id else uuid.uuid4()
    s.user_id = user_id
    s.session_type = "full_cycle"
    s.status = status
    s.market_regime = "bull"
    s.iteration_count = 2
    s.started_at = datetime.now(timezone.utc)
    s.ended_at = None
    s.created_at = datetime.now(timezone.utc)
    return s


# ─── Mock DB helper ─────────────────────────────────────────

class MockScalarResult:
    """Mock for scalars().all() and scalar_one_or_none()."""
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


class MockResult:
    """Mock for db.execute() result."""
    def __init__(self, items=None):
        self._items = items or []

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalars(self):
        return MockScalarResult(self._items)


def make_mock_db(execute_side_effects=None):
    """Create a mock async DB session."""
    db = AsyncMock()
    if execute_side_effects:
        db.execute = AsyncMock(side_effect=execute_side_effects)
    else:
        db.execute = AsyncMock(return_value=MockResult())
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    return db


# ─── Fixtures ────────────────────────────────────────────────

@pytest.fixture
def test_user():
    return _make_user()


@pytest.fixture
def auth_token(test_user):
    return create_access_token({"sub": str(test_user.id)})


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest_asyncio.fixture
async def client(test_user):
    """Create httpx AsyncClient with mocked DB and auth."""
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
        c._mock_db = mock_db  # attach for test access
        c._test_user = test_user
        yield c


# ─── Auth Flow Tests ─────────────────────────────────────────


class TestAuthFlow:
    """Test complete auth lifecycle: register → login → refresh → me."""

    @pytest.mark.asyncio
    async def test_register_new_user(self, test_user):
        """POST /register creates user and returns tokens."""
        from app.main import create_app
        from app.db.session import get_db

        app = create_app()
        mock_db = make_mock_db([
            # First execute: check email uniqueness → not found
            MockResult([]),
        ])
        # Mock flush to set user.id
        user_obj_holder = []
        original_add = mock_db.add

        def capture_add(obj):
            user_obj_holder.append(obj)
            obj.id = uuid.uuid4()

        mock_db.add = capture_add

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/auth/register", json={
                "email": "new@example.com",
                "password": "Secure123",
                "display_name": "New User",
            })

        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, test_user):
        """POST /register with existing email returns 409."""
        from app.main import create_app
        from app.db.session import get_db

        app = create_app()
        mock_db = make_mock_db([
            MockResult([test_user]),  # email already exists
        ])

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/auth/register", json={
                "email": "test@example.com",
                "password": "Secure123",
            })

        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_success(self, test_user):
        """POST /login with valid credentials returns tokens."""
        from app.main import create_app
        from app.db.session import get_db

        # Create user with known password
        user = _make_user(email="login@test.com")
        user.hashed_password = hash_password("mypassword")

        app = create_app()
        mock_db = make_mock_db([
            MockResult([user]),
        ])

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/auth/login", json={
                "email": "login@test.com",
                "password": "mypassword",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, test_user):
        """POST /login with wrong password returns 401."""
        from app.main import create_app
        from app.db.session import get_db

        user = _make_user()
        user.hashed_password = hash_password("correct")

        app = create_app()
        mock_db = make_mock_db([MockResult([user])])

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/auth/login", json={
                "email": "test@example.com",
                "password": "wrong",
            })

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self):
        """POST /login with unknown email returns 401."""
        from app.main import create_app
        from app.db.session import get_db

        app = create_app()
        mock_db = make_mock_db([MockResult([])])

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/auth/login", json={
                "email": "nobody@test.com",
                "password": "whatever",
            })

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token(self):
        """POST /refresh with valid refresh token returns new tokens."""
        from app.main import create_app
        from app.core.security import create_refresh_token

        app = create_app()
        refresh = create_refresh_token({"sub": str(uuid.uuid4())})

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/auth/refresh", json={
                "refresh_token": refresh,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self):
        """POST /refresh with invalid token returns 401."""
        from app.main import create_app

        app = create_app()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/auth/refresh", json={
                "refresh_token": "invalid-token",
            })

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_with_access_token_fails(self):
        """POST /refresh with an access token (not refresh) returns 401."""
        from app.main import create_app

        app = create_app()
        access = create_access_token({"sub": str(uuid.uuid4())})

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/auth/refresh", json={
                "refresh_token": access,
            })

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_endpoint(self, client, test_user):
        """GET /me returns current user profile."""
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == test_user.email
        assert data["id"] == str(test_user.id)

    @pytest.mark.asyncio
    async def test_me_without_auth(self):
        """GET /me without token returns 403."""
        from app.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/v1/auth/me")

        assert resp.status_code == 401


# ─── Strategy CRUD Tests ─────────────────────────────────────


class TestStrategyCRUD:
    """Test full strategy lifecycle: create → list → get → update → activate → deactivate → delete."""

    @pytest.mark.asyncio
    async def test_create_strategy(self, client, test_user):
        """POST /strategies creates a new strategy."""
        # Mock db.add to set id and timestamps
        def mock_add(obj):
            obj.id = uuid.uuid4()
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = datetime.now(timezone.utc)
            obj.composite_score = None
            obj.validation_results = None
            obj.status = "draft"
            obj.is_auto_trading = False

        client._mock_db.add = mock_add

        resp = await client.post("/api/v1/strategies", json={
            "name": "RSI Strategy",
            "stock_code": "005930",
            "stock_name": "Samsung",
            "strategy_type": "indicator_based",
            "indicators": [{"name": "RSI", "params": {"period": 14}}],
            "parameters": {"rsi_oversold": 30},
        })

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "RSI Strategy"
        assert data["stock_code"] == "005930"
        assert data["status"] == "draft"
        assert data["is_auto_trading"] is False

    @pytest.mark.asyncio
    async def test_list_strategies(self, client, test_user):
        """GET /strategies returns user's strategies."""
        strategies = [
            _make_strategy(test_user.id, name="Strategy A"),
            _make_strategy(test_user.id, name="Strategy B"),
        ]
        client._mock_db.execute = AsyncMock(return_value=MockResult(strategies))

        resp = await client.get("/api/v1/strategies")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_get_strategy(self, client, test_user):
        """GET /strategies/{id} returns specific strategy."""
        strategy = _make_strategy(test_user.id)
        client._mock_db.execute = AsyncMock(return_value=MockResult([strategy]))

        resp = await client.get(f"/api/v1/strategies/{strategy.id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "RSI Momentum"
        assert data["stock_code"] == "005930"

    @pytest.mark.asyncio
    async def test_get_strategy_not_found(self, client):
        """GET /strategies/{id} with invalid id returns 404."""
        client._mock_db.execute = AsyncMock(return_value=MockResult([]))

        resp = await client.get(f"/api/v1/strategies/{uuid.uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_strategy(self, client, test_user):
        """PUT /strategies/{id} updates strategy fields."""
        strategy = _make_strategy(test_user.id)
        client._mock_db.execute = AsyncMock(return_value=MockResult([strategy]))

        resp = await client.put(f"/api/v1/strategies/{strategy.id}", json={
            "name": "Updated RSI",
            "parameters": {"rsi_oversold": 25},
        })

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_strategy(self, client, test_user):
        """DELETE /strategies/{id} removes strategy."""
        strategy = _make_strategy(test_user.id)
        client._mock_db.execute = AsyncMock(return_value=MockResult([strategy]))

        resp = await client.delete(f"/api/v1/strategies/{strategy.id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_strategy_not_found(self, client):
        """DELETE /strategies/{id} with invalid id returns 404."""
        client._mock_db.execute = AsyncMock(return_value=MockResult([]))

        resp = await client.delete(f"/api/v1/strategies/{uuid.uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_search_strategies(self, client):
        """POST /strategies/search starts async search job."""
        resp = await client.post("/api/v1/strategies/search", json={
            "stock_code": "005930",
            "date_range_start": "2024-01-01",
            "date_range_end": "2024-12-31",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "running"

    @pytest.mark.asyncio
    async def test_activate_strategy(self, client, test_user):
        """POST /strategies/{id}/activate sets auto-trading on."""
        strategy = _make_strategy(test_user.id)
        client._mock_db.execute = AsyncMock(return_value=MockResult([strategy]))

        resp = await client.post(f"/api/v1/strategies/{strategy.id}/activate")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_deactivate_strategy(self, client, test_user):
        """POST /strategies/{id}/deactivate sets auto-trading off."""
        strategy = _make_strategy(test_user.id)
        client._mock_db.execute = AsyncMock(return_value=MockResult([strategy]))

        resp = await client.post(f"/api/v1/strategies/{strategy.id}/deactivate")
        assert resp.status_code == 200


# ─── Agent Session Tests ─────────────────────────────────────


class TestAgentSessionLifecycle:
    """Test agent session: start → status → sessions → approve → reject."""

    @pytest.mark.asyncio
    @patch("app.tasks.agent_tasks.run_agent_session")
    async def test_start_agent_session(self, mock_celery, client, test_user):
        """POST /agents/start creates session and fires Celery task."""
        # No existing active session
        client._mock_db.execute = AsyncMock(return_value=MockResult([]))

        def mock_add(obj):
            obj.id = uuid.uuid4()
            obj.started_at = datetime.now(timezone.utc)
            obj.status = "active"
            obj.session_type = "full_cycle"
            obj.market_regime = None
            obj.iteration_count = 0

        client._mock_db.add = mock_add

        resp = await client.post("/api/v1/agents/start", json={
            "session_type": "full_cycle",
            "stock_codes": ["005930"],
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert data["session_type"] == "full_cycle"
        mock_celery.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_session_duplicate_rejected(self, client, test_user):
        """POST /agents/start with existing active session returns 409."""
        existing = _make_session(test_user.id)
        client._mock_db.execute = AsyncMock(return_value=MockResult([existing]))

        resp = await client.post("/api/v1/agents/start", json={
            "session_type": "full_cycle",
        })

        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_agent_status_active(self, client, test_user):
        """GET /agents/status returns active session details."""
        session = _make_session(test_user.id)
        actions = [MagicMock(agent_name="market_analyst", action_type="analyze", created_at=datetime.now(timezone.utc))]

        client._mock_db.execute = AsyncMock(side_effect=[
            MockResult([session]),  # find active session
            MockResult(actions),    # recent actions
        ])

        resp = await client.get("/api/v1/agents/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert data["market_regime"] == "bull"

    @pytest.mark.asyncio
    async def test_get_agent_status_none(self, client):
        """GET /agents/status with no active session returns null."""
        client._mock_db.execute = AsyncMock(return_value=MockResult([]))

        resp = await client.get("/api/v1/agents/status")
        assert resp.status_code == 200
        assert resp.json() is None

    @pytest.mark.asyncio
    async def test_list_sessions(self, client, test_user):
        """GET /agents/sessions returns session history."""
        sessions = [
            _make_session(test_user.id, status="completed"),
            _make_session(test_user.id, status="active"),
        ]
        client._mock_db.execute = AsyncMock(return_value=MockResult(sessions))

        resp = await client.get("/api/v1/agents/sessions")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_stop_session(self, client, test_user):
        """POST /agents/stop changes session status to stopped."""
        session = _make_session(test_user.id)
        client._mock_db.execute = AsyncMock(return_value=MockResult([session]))

        resp = await client.post("/api/v1/agents/stop", json={
            "session_id": str(session.id),
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_stop_session_not_found(self, client):
        """POST /agents/stop with invalid session returns 404."""
        client._mock_db.execute = AsyncMock(return_value=MockResult([]))

        resp = await client.post("/api/v1/agents/stop", json={
            "session_id": str(uuid.uuid4()),
        })
        assert resp.status_code == 404

    @pytest.mark.asyncio
    @patch("app.tasks.agent_tasks.resume_agent_session")
    async def test_approve_trades(self, mock_resume, client, test_user):
        """POST /agents/sessions/{id}/approve approves pending trades."""
        session = _make_session(test_user.id, status="pending_approval")
        client._mock_db.execute = AsyncMock(return_value=MockResult([session]))
        client._mock_db.add = MagicMock()

        resp = await client.post(f"/api/v1/agents/sessions/{session.id}/approve")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert "Resuming execution" in data["message"]
        mock_resume.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_approve_wrong_status(self, client, test_user):
        """POST /approve on non-pending session returns 400."""
        session = _make_session(test_user.id, status="active")
        client._mock_db.execute = AsyncMock(return_value=MockResult([session]))

        resp = await client.post(f"/api/v1/agents/sessions/{session.id}/approve")
        assert resp.status_code == 400
        assert "not pending" in resp.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.tasks.agent_tasks.resume_agent_session")
    async def test_reject_trades(self, mock_resume, client, test_user):
        """POST /agents/sessions/{id}/reject rejects pending trades."""
        session = _make_session(test_user.id, status="pending_approval")
        client._mock_db.execute = AsyncMock(return_value=MockResult([session]))
        client._mock_db.add = MagicMock()

        resp = await client.post(f"/api/v1/agents/sessions/{session.id}/reject")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        mock_resume.delay.assert_called_once()


# ─── Trading & Orders Tests ──────────────────────────────────


class TestTradingOrders:
    """Test order placement, listing, and cancellation."""

    @pytest.mark.asyncio
    @patch("app.api.v1.trading.ws_manager")
    @patch("app.api.v1.trading.get_kis_client")
    async def test_place_order_success(self, mock_kis_factory, mock_ws, client, test_user):
        """POST /trading/orders places order via KIS and returns result."""
        mock_kis = AsyncMock()
        mock_kis.place_order.return_value = {"success": True, "kis_order_id": "K001"}
        mock_kis_factory.return_value = mock_kis
        mock_ws.send_to_user = AsyncMock()

        def mock_add(obj):
            obj.id = uuid.uuid4()
            obj.status = "pending"
            obj.filled_quantity = 0
            obj.avg_fill_price = None
            obj.submitted_at = None
            obj.filled_at = None
            obj.created_at = datetime.now(timezone.utc)
            obj.kis_order_id = None
            obj.stock_name = "Samsung"

        client._mock_db.add = mock_add

        resp = await client.post("/api/v1/trading/orders", json={
            "stock_code": "005930",
            "stock_name": "Samsung",
            "side": "buy",
            "order_type": "market",
            "quantity": 10,
        })

        assert resp.status_code == 201
        data = resp.json()
        assert data["stock_code"] == "005930"
        assert data["side"] == "buy"
        assert data["quantity"] == 10

    @pytest.mark.asyncio
    @patch("app.api.v1.trading.ws_manager")
    @patch("app.api.v1.trading.get_kis_client")
    async def test_place_order_kis_failure(self, mock_kis_factory, mock_ws, client, test_user):
        """POST /trading/orders handles KIS API failure gracefully."""
        mock_kis_factory.side_effect = ValueError("No KIS credentials")
        mock_ws.send_to_user = AsyncMock()

        def mock_add(obj):
            obj.id = uuid.uuid4()
            obj.status = "pending"
            obj.filled_quantity = 0
            obj.avg_fill_price = None
            obj.submitted_at = None
            obj.filled_at = None
            obj.created_at = datetime.now(timezone.utc)
            obj.kis_order_id = None
            obj.stock_name = None

        client._mock_db.add = mock_add

        resp = await client.post("/api/v1/trading/orders", json={
            "stock_code": "005930",
            "side": "buy",
            "order_type": "market",
            "quantity": 5,
        })

        # Still creates order in DB but with "failed" status
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_list_orders(self, client, test_user):
        """GET /trading/orders returns order list."""
        orders = [
            _make_order(test_user.id, status="submitted"),
            _make_order(test_user.id, status="filled"),
        ]
        client._mock_db.execute = AsyncMock(return_value=MockResult(orders))

        resp = await client.get("/api/v1/trading/orders")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_list_orders_with_status_filter(self, client, test_user):
        """GET /trading/orders?status=submitted filters orders."""
        orders = [_make_order(test_user.id, status="submitted")]
        client._mock_db.execute = AsyncMock(return_value=MockResult(orders))

        resp = await client.get("/api/v1/trading/orders?status=submitted")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    @pytest.mark.asyncio
    @patch("app.api.v1.trading.ws_manager")
    @patch("app.api.v1.trading.get_kis_client")
    async def test_cancel_order(self, mock_kis_factory, mock_ws, client, test_user):
        """DELETE /trading/orders/{id} cancels order."""
        order = _make_order(test_user.id, status="submitted")
        client._mock_db.execute = AsyncMock(return_value=MockResult([order]))
        mock_kis = AsyncMock()
        mock_kis.cancel_order.return_value = {"success": True}
        mock_kis_factory.return_value = mock_kis
        mock_ws.send_to_user = AsyncMock()

        resp = await client.delete(f"/api/v1/trading/orders/{order.id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_cancel_order_not_found(self, client):
        """DELETE /trading/orders/{id} returns 404 for missing order."""
        client._mock_db.execute = AsyncMock(return_value=MockResult([]))

        resp = await client.delete(f"/api/v1/trading/orders/{uuid.uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_filled_order_rejected(self, client, test_user):
        """DELETE /trading/orders/{id} rejects cancel for filled order."""
        order = _make_order(test_user.id, status="filled")
        client._mock_db.execute = AsyncMock(return_value=MockResult([order]))

        resp = await client.delete(f"/api/v1/trading/orders/{order.id}")
        assert resp.status_code == 400
        assert "Cannot cancel" in resp.json()["detail"]


# ─── Positions & Portfolio Tests ──────────────────────────────


class TestPositionsAndPortfolio:
    """Test position listing and portfolio analytics."""

    @pytest.mark.asyncio
    async def test_list_positions(self, client, test_user):
        """GET /trading/positions returns open positions."""
        positions = [
            _make_position(test_user.id, stock_code="005930"),
            _make_position(test_user.id, stock_code="000660"),
        ]
        client._mock_db.execute = AsyncMock(return_value=MockResult(positions))

        resp = await client.get("/api/v1/trading/positions")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["quantity"] == 100

    @pytest.mark.asyncio
    async def test_list_positions_empty(self, client, test_user):
        """GET /trading/positions with no positions returns empty list."""
        client._mock_db.execute = AsyncMock(return_value=MockResult([]))

        resp = await client.get("/api/v1/trading/positions")

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_portfolio_analytics(self, client, test_user):
        """GET /trading/portfolio/analytics returns aggregated portfolio data."""
        positions = [_make_position(test_user.id)]
        trades_winning = [_make_trade(test_user.id, pnl=50000, pnl_percent=5.0)]
        trades_losing = [_make_trade(test_user.id, pnl=-20000, pnl_percent=-2.0)]

        client._mock_db.execute = AsyncMock(side_effect=[
            MockResult(positions),                           # positions query
            MockResult(trades_winning + trades_losing),      # trades query
        ])

        resp = await client.get("/api/v1/trading/portfolio/analytics")

        assert resp.status_code == 200
        data = resp.json()
        assert "portfolio_value" in data
        assert "allocation" in data
        assert "trade_stats" in data
        assert data["position_count"] == 1
        assert data["trade_stats"]["total_trades"] == 2

    @pytest.mark.asyncio
    async def test_portfolio_analytics_empty(self, client, test_user):
        """GET /trading/portfolio/analytics with no positions/trades."""
        client._mock_db.execute = AsyncMock(side_effect=[
            MockResult([]),  # no positions
            MockResult([]),  # no trades
        ])

        resp = await client.get("/api/v1/trading/portfolio/analytics")

        assert resp.status_code == 200
        data = resp.json()
        assert data["portfolio_value"] == 0
        assert data["position_count"] == 0
        assert data["trade_stats"]["total_trades"] == 0

    @pytest.mark.asyncio
    async def test_list_trades(self, client, test_user):
        """GET /trading/trades returns completed trades."""
        trades = [
            _make_trade(test_user.id, pnl=50000),
            _make_trade(test_user.id, pnl=-20000),
        ]
        client._mock_db.execute = AsyncMock(return_value=MockResult(trades))

        resp = await client.get("/api/v1/trading/trades")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    @patch("app.api.v1.trading.get_kis_client")
    async def test_get_balance(self, mock_kis_factory, client, test_user):
        """GET /trading/balance fetches from KIS."""
        mock_kis = AsyncMock()
        mock_kis.get_balance.return_value = {
            "total_balance": 10000000,
            "available_cash": 5000000,
        }
        mock_kis_factory.return_value = mock_kis

        resp = await client.get("/api/v1/trading/balance")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_balance"] == 10000000

    @pytest.mark.asyncio
    @patch("app.api.v1.trading.get_kis_client")
    async def test_get_balance_no_credentials(self, mock_kis_factory, client):
        """GET /trading/balance without KIS credentials returns 400."""
        mock_kis_factory.side_effect = ValueError("No KIS credentials")

        resp = await client.get("/api/v1/trading/balance")
        assert resp.status_code == 400


# ─── Portfolio Strategy Aggregation Tests ─────────────────────


class TestPortfolioStrategies:
    """Test multi-strategy portfolio analysis endpoints."""

    @pytest.mark.asyncio
    async def test_portfolio_by_strategy(self, client, test_user):
        """GET /trading/portfolio/strategies returns cross-strategy exposure."""
        strat_id = uuid.uuid4()
        positions = [_make_position(test_user.id, strategy_id=strat_id)]
        strategies = [_make_strategy(test_user.id, strategy_id=str(strat_id))]

        client._mock_db.execute = AsyncMock(side_effect=[
            MockResult(positions),   # positions
            MockResult(strategies),  # strategies
        ])

        resp = await client.get("/api/v1/trading/portfolio/strategies")

        assert resp.status_code == 200
        data = resp.json()
        assert "total_exposure" in data
        assert "hhi" in data
        assert "conflicts" in data

    @pytest.mark.asyncio
    async def test_portfolio_correlation_empty(self, client, test_user):
        """GET /trading/portfolio/correlation with no trades returns defaults."""
        client._mock_db.execute = AsyncMock(side_effect=[
            MockResult([]),  # no trades
        ])

        resp = await client.get("/api/v1/trading/portfolio/correlation")

        assert resp.status_code == 200
        data = resp.json()
        assert data["strategy_ids"] == []
        assert data["diversification_ratio"] == 1.0

    @pytest.mark.asyncio
    async def test_portfolio_attribution(self, client, test_user):
        """GET /trading/portfolio/attribution returns P&L breakdown."""
        strat_id = uuid.uuid4()
        trades = [
            _make_trade(test_user.id, pnl=100000, strategy_id=strat_id),
            _make_trade(test_user.id, pnl=-30000, strategy_id=strat_id),
        ]
        strategies = [_make_strategy(test_user.id, strategy_id=str(strat_id))]

        client._mock_db.execute = AsyncMock(side_effect=[
            MockResult(trades),      # trades
            MockResult(strategies),  # strategies
        ])

        resp = await client.get("/api/v1/trading/portfolio/attribution")

        assert resp.status_code == 200
        data = resp.json()
        assert "total_pnl" in data
        assert "by_strategy" in data
        assert "by_stock" in data
        assert data["total_pnl"] == 70000.0


# ─── Health & Metrics Tests ──────────────────────────────────


class TestHealthAndMetrics:
    """Test infrastructure endpoints."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """GET /health returns ok when all checks pass."""
        from app.main import create_app

        app = create_app()

        # Mock DB engine and Redis
        with patch("app.main.engine") as mock_engine, \
             patch("redis.asyncio.from_url") as mock_redis_factory:

            # Mock DB connection
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_engine.connect.return_value = mock_ctx

            # Mock Redis
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_redis.aclose = AsyncMock()
            mock_redis_factory.return_value = mock_redis

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/health")

            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["database"] == "ok"
            assert data["redis"] == "ok"
            assert "circuit_breakers" in data

    @pytest.mark.asyncio
    async def test_health_check_db_down(self):
        """GET /health returns degraded when DB is down."""
        from app.main import create_app

        app = create_app()

        with patch("app.main.engine") as mock_engine, \
             patch("redis.asyncio.from_url") as mock_redis_factory:

            # DB connection fails
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("connection refused"))
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_engine.connect.return_value = mock_ctx

            # Redis OK
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_redis.aclose = AsyncMock()
            mock_redis_factory.return_value = mock_redis

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/health")

            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "degraded"
            assert "error" in data["database"]

    @pytest.mark.asyncio
    async def test_health_check_redis_down(self):
        """GET /health returns degraded when Redis is down."""
        from app.main import create_app

        app = create_app()

        with patch("app.main.engine") as mock_engine, \
             patch("redis.asyncio.from_url") as mock_redis_factory:

            # DB OK
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_engine.connect.return_value = mock_ctx

            # Redis fails
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(side_effect=Exception("Redis unreachable"))
            mock_redis.aclose = AsyncMock()
            mock_redis_factory.return_value = mock_redis

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.get("/health")

            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "degraded"
            assert "error" in data["redis"]

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self):
        """GET /metrics returns Prometheus format."""
        from app.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/metrics")

        assert resp.status_code == 200
        body = resp.text
        # Prometheus metrics contain TYPE and HELP lines
        assert "able_" in body or "python_" in body or "process_" in body


# ─── Full User Journey Tests ─────────────────────────────────


class TestFullUserJourney:
    """End-to-end scenarios combining multiple API calls."""

    @pytest.mark.asyncio
    @patch("app.tasks.agent_tasks.run_agent_session")
    async def test_register_create_strategy_start_agent(self, mock_celery, test_user):
        """Full journey: register → create strategy → start agent session."""
        from app.main import create_app
        from app.db.session import get_db
        from app.api.v1.deps import get_current_user

        app = create_app()

        # Phase 1: Register (mock DB for auth)
        register_db = make_mock_db([MockResult([])])  # email not taken
        objects_added = []

        def capture_add(obj):
            obj.id = uuid.uuid4()
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = datetime.now(timezone.utc)
            # Strategy defaults
            if not hasattr(obj, "status") or obj.status is None:
                obj.status = "draft"
            if not hasattr(obj, "is_auto_trading") or obj.is_auto_trading is None:
                obj.is_auto_trading = False
            if not hasattr(obj, "composite_score"):
                obj.composite_score = None
            if not hasattr(obj, "validation_results"):
                obj.validation_results = None
            # AgentSession defaults
            if not hasattr(obj, "started_at") or obj.started_at is None:
                obj.started_at = datetime.now(timezone.utc)
            if not hasattr(obj, "market_regime"):
                obj.market_regime = None
            if not hasattr(obj, "iteration_count"):
                obj.iteration_count = 0
            objects_added.append(obj)

        register_db.add = capture_add

        async def override_db():
            yield register_db

        app.dependency_overrides[get_db] = override_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            # Step 1: Register
            resp = await c.post("/api/v1/auth/register", json={
                "email": "journey@test.com",
                "password": "Secure123",
                "display_name": "Journey Tester",
            })
            assert resp.status_code == 201
            tokens = resp.json()
            access_token = tokens["access_token"]

        # Phase 2: Authenticated operations
        auth_user = test_user

        async def override_user():
            return auth_user

        app.dependency_overrides[get_current_user] = override_user

        # Strategy creation DB
        strategy_db = make_mock_db()
        strategy_db.add = capture_add

        async def override_db2():
            yield strategy_db

        app.dependency_overrides[get_db] = override_db2

        async with AsyncClient(transport=transport, base_url="http://test") as c:
            # Step 2: Create strategy
            resp = await c.post("/api/v1/strategies", json={
                "name": "MACD Cross",
                "stock_code": "005930",
                "strategy_type": "indicator_based",
            })
            assert resp.status_code == 201

        # Phase 3: Start agent
        agent_db = make_mock_db([MockResult([])])  # no active session
        agent_db.add = capture_add

        async def override_db3():
            yield agent_db

        app.dependency_overrides[get_db] = override_db3

        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/agents/start", json={
                "session_type": "full_cycle",
            })
            assert resp.status_code == 200
            assert resp.json()["status"] == "active"
            mock_celery.delay.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.tasks.agent_tasks.resume_agent_session")
    async def test_hitl_approval_flow(self, mock_resume, client, test_user):
        """Agent reaches HITL → user approves → execution resumes."""
        session = _make_session(test_user.id, status="pending_approval")
        client._mock_db.execute = AsyncMock(return_value=MockResult([session]))
        client._mock_db.add = MagicMock()

        # Step 1: Approve
        resp = await client.post(f"/api/v1/agents/sessions/{session.id}/approve")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["message"] == "Trades approved. Resuming execution."

        # Verify Celery was called to resume
        mock_resume.delay.assert_called_once_with(
            user_id=str(test_user.id),
            session_id=str(session.id),
            approval_status="approved",
        )

    @pytest.mark.asyncio
    @patch("app.api.v1.trading.ws_manager")
    @patch("app.api.v1.trading.get_kis_client")
    async def test_place_order_then_cancel(self, mock_kis_factory, mock_ws, client, test_user):
        """Place an order, verify it's created, then cancel it."""
        mock_kis = AsyncMock()
        mock_kis.place_order.return_value = {"success": True, "kis_order_id": "K999"}
        mock_kis.cancel_order.return_value = {"success": True}
        mock_kis_factory.return_value = mock_kis
        mock_ws.send_to_user = AsyncMock()

        order_id = uuid.uuid4()

        def mock_add(obj):
            obj.id = order_id
            obj.status = "pending"
            obj.filled_quantity = 0
            obj.avg_fill_price = None
            obj.submitted_at = None
            obj.filled_at = None
            obj.created_at = datetime.now(timezone.utc)
            obj.kis_order_id = None
            obj.stock_name = "Samsung"

        client._mock_db.add = mock_add

        # Step 1: Place order
        resp = await client.post("/api/v1/trading/orders", json={
            "stock_code": "005930",
            "stock_name": "Samsung",
            "side": "buy",
            "order_type": "market",
            "quantity": 50,
        })
        assert resp.status_code == 201

        # Step 2: Cancel (mock the order lookup)
        cancel_order = _make_order(test_user.id, status="submitted")
        cancel_order.id = order_id
        client._mock_db.execute = AsyncMock(return_value=MockResult([cancel_order]))

        resp = await client.delete(f"/api/v1/trading/orders/{order_id}")
        assert resp.status_code == 204


# ─── Error & Edge Case Tests ─────────────────────────────────


class TestErrorHandling:
    """Test error responses and edge cases across endpoints."""

    @pytest.mark.asyncio
    async def test_invalid_json_body(self):
        """Malformed JSON returns 422."""
        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/auth/register",
                content="not json",
                headers={"Content-Type": "application/json"},
            )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_required_fields(self):
        """Missing required fields returns 422."""
        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/auth/register", json={
                "email": "test@example.com",
                # missing password
            })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_email_format(self):
        """Invalid email format returns 422."""
        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/auth/register", json={
                "email": "not-an-email",
                "password": "Test1234",
            })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_nonexistent_route(self):
        """Accessing nonexistent route returns 404."""
        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/v1/nonexistent")
        assert resp.status_code in (404, 405)

    @pytest.mark.asyncio
    async def test_method_not_allowed(self):
        """Wrong HTTP method returns 405."""
        from app.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.patch("/api/v1/auth/register", json={})
        assert resp.status_code == 405

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self):
        """Expired access token returns 401."""
        from app.main import create_app
        from app.db.session import get_db

        app = create_app()

        # Create an expired token by patching the expiration
        from jose import jwt
        payload = {
            "sub": str(uuid.uuid4()),
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        expired_token = jwt.encode(payload, os.environ["SECRET_KEY"], algorithm="HS256")

        mock_db = make_mock_db()

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {expired_token}"},
            )
        assert resp.status_code == 401
