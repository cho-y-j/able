"""Comprehensive tests for strategy search service and API endpoints.

Tests cover:
- Strategy search service (get_job_status, _update_job, _build_param_grid)
- Strategy detail API endpoint (GET /strategies/{id}/detail)
- Search job polling endpoint (GET /strategies/search-jobs/{job_id})
- Search kickoff endpoint (POST /strategies/search)
"""

import os
import uuid
from datetime import datetime, date, timezone
from unittest.mock import patch, AsyncMock, MagicMock

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
from app.models.backtest import Backtest


# ─── Mock DB Helpers ──────────────────────────────────────────


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


# ─── Factory Helpers ──────────────────────────────────────────


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
    s.status = "validated"
    s.is_auto_trading = False
    s.created_at = datetime.now(timezone.utc)
    s.updated_at = datetime.now(timezone.utc)
    s.description = None
    return s


def _make_backtest(strategy_id, user_id, backtest_id=None):
    """Create a mock Backtest instance with realistic metrics."""
    bt = MagicMock(spec=Backtest)
    bt.id = uuid.UUID(backtest_id) if backtest_id else uuid.uuid4()
    bt.strategy_id = strategy_id
    bt.user_id = user_id
    bt.status = "completed"
    bt.parameters = {"rsi_oversold": 30, "rsi_overbought": 70}
    bt.date_range_start = date(2024, 1, 1)
    bt.date_range_end = date(2024, 12, 31)
    bt.total_return = 25.3
    bt.annual_return = 18.7
    bt.sharpe_ratio = 1.45
    bt.sortino_ratio = 2.1
    bt.max_drawdown = -8.5
    bt.win_rate = 0.62
    bt.profit_factor = 1.85
    bt.total_trades = 42
    bt.calmar_ratio = 2.2
    bt.wfa_score = 78.0
    bt.mc_score = 82.5
    bt.oos_score = 71.0
    bt.equity_curve = [{"date": "2024-01-02", "value": 10000}, {"date": "2024-12-31", "value": 12530}]
    bt.trade_log = [{"entry": "2024-01-15", "exit": "2024-02-01", "pnl": 500}]
    bt.completed_at = datetime.now(timezone.utc)
    bt.created_at = datetime.now(timezone.utc)
    return bt


# ─── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def test_user():
    return _make_user()


@pytest.fixture
def auth_token(test_user):
    return create_access_token({"sub": str(test_user.id)})


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
        c._mock_db = mock_db
        c._test_user = test_user
        yield c


# ─── Strategy Search Service Tests ───────────────────────────


class TestGetJobStatus:
    """Test get_job_status() returns correct values for known and unknown jobs."""

    def test_returns_none_for_unknown_job(self):
        """get_job_status() returns None when job_id does not exist."""
        from app.services.strategy_search import get_job_status, _search_jobs

        # Ensure the job store doesn't have our ID
        unknown_id = str(uuid.uuid4())
        _search_jobs.pop(unknown_id, None)

        result = get_job_status(unknown_id)
        assert result is None

    def test_returns_status_after_creation(self):
        """get_job_status() returns correct status dict after job is created."""
        from app.services.strategy_search import get_job_status, _search_jobs

        job_id = str(uuid.uuid4())
        _search_jobs[job_id] = {
            "status": "running",
            "progress": 0,
            "step": "initializing",
            "result": None,
            "error": None,
        }

        result = get_job_status(job_id)
        assert result is not None
        assert result["status"] == "running"
        assert result["progress"] == 0
        assert result["step"] == "initializing"
        assert result["result"] is None
        assert result["error"] is None

        # Cleanup
        del _search_jobs[job_id]

    def test_returns_completed_job_with_result(self):
        """get_job_status() returns result payload when job is complete."""
        from app.services.strategy_search import get_job_status, _search_jobs

        job_id = str(uuid.uuid4())
        expected_result = {
            "strategies_found": 3,
            "stock_code": "005930",
        }
        _search_jobs[job_id] = {
            "status": "complete",
            "progress": 100,
            "step": "done",
            "result": expected_result,
            "error": None,
        }

        result = get_job_status(job_id)
        assert result["status"] == "complete"
        assert result["progress"] == 100
        assert result["result"]["strategies_found"] == 3

        # Cleanup
        del _search_jobs[job_id]

    def test_returns_error_job(self):
        """get_job_status() returns error details when job fails."""
        from app.services.strategy_search import get_job_status, _search_jobs

        job_id = str(uuid.uuid4())
        _search_jobs[job_id] = {
            "status": "error",
            "progress": 5,
            "step": "fetching_data",
            "result": None,
            "error": "데이터 부족: 10일",
        }

        result = get_job_status(job_id)
        assert result["status"] == "error"
        assert "데이터 부족" in result["error"]

        # Cleanup
        del _search_jobs[job_id]


class TestUpdateJob:
    """Test _update_job() correctly updates existing jobs and ignores missing ones."""

    def test_updates_existing_job(self):
        """_update_job() modifies fields of an existing job."""
        from app.services.strategy_search import _update_job, _search_jobs

        job_id = str(uuid.uuid4())
        _search_jobs[job_id] = {
            "status": "running",
            "progress": 0,
            "step": "initializing",
            "result": None,
            "error": None,
        }

        _update_job(job_id, step="fetching_data", progress=5)

        assert _search_jobs[job_id]["step"] == "fetching_data"
        assert _search_jobs[job_id]["progress"] == 5
        assert _search_jobs[job_id]["status"] == "running"  # unchanged

        # Cleanup
        del _search_jobs[job_id]

    def test_updates_multiple_fields(self):
        """_update_job() can update status, progress, step, and result at once."""
        from app.services.strategy_search import _update_job, _search_jobs

        job_id = str(uuid.uuid4())
        _search_jobs[job_id] = {
            "status": "running",
            "progress": 65,
            "step": "validating",
            "result": None,
            "error": None,
        }

        result_data = {"strategies_found": 5, "stock_code": "000660"}
        _update_job(job_id, status="complete", progress=100, step="done", result=result_data)

        assert _search_jobs[job_id]["status"] == "complete"
        assert _search_jobs[job_id]["progress"] == 100
        assert _search_jobs[job_id]["step"] == "done"
        assert _search_jobs[job_id]["result"]["strategies_found"] == 5

        # Cleanup
        del _search_jobs[job_id]

    def test_ignores_unknown_job(self):
        """_update_job() does nothing for non-existent job_id (no error)."""
        from app.services.strategy_search import _update_job, _search_jobs

        unknown_id = str(uuid.uuid4())
        _search_jobs.pop(unknown_id, None)

        # Should not raise
        _update_job(unknown_id, status="complete", progress=100)

        assert unknown_id not in _search_jobs


class TestBuildParamGrid:
    """Test _build_param_grid() produces correct grid for int, float, and categorical types."""

    def test_int_type_creates_range(self):
        """Integer param type generates discrete steps from low to high."""
        from app.services.strategy_search import _build_param_grid

        param_space = {
            "period": {"type": "int", "low": 5, "high": 25},
        }
        grid = _build_param_grid(param_space)

        assert "period" in grid
        values = grid["period"]
        assert isinstance(values, list)
        assert all(isinstance(v, int) for v in values)
        assert values[0] == 5
        assert values[-1] <= 25
        # Step = max(1, (25-5)//4) = 5, so range(5, 26, 5) = [5, 10, 15, 20, 25]
        assert values == [5, 10, 15, 20, 25]

    def test_int_type_small_range(self):
        """Integer param with small range still generates valid grid."""
        from app.services.strategy_search import _build_param_grid

        param_space = {
            "lookback": {"type": "int", "low": 1, "high": 3},
        }
        grid = _build_param_grid(param_space)

        values = grid["lookback"]
        assert len(values) >= 1
        assert values[0] == 1
        # Step = max(1, (3-1)//4) = 1, so range(1, 4, 1) = [1, 2, 3]
        assert values == [1, 2, 3]

    def test_float_type_creates_five_points(self):
        """Float param type generates exactly 5 evenly spaced points."""
        from app.services.strategy_search import _build_param_grid

        param_space = {
            "threshold": {"type": "float", "low": 0.0, "high": 1.0},
        }
        grid = _build_param_grid(param_space)

        assert "threshold" in grid
        values = grid["threshold"]
        assert len(values) == 5
        assert values[0] == 0.0
        assert values[-1] == 1.0
        # Verify evenly spaced: [0.0, 0.25, 0.5, 0.75, 1.0]
        assert values == [0.0, 0.25, 0.5, 0.75, 1.0]

    def test_float_type_rounding(self):
        """Float param values are rounded to 2 decimal places."""
        from app.services.strategy_search import _build_param_grid

        param_space = {
            "multiplier": {"type": "float", "low": 1.0, "high": 3.0},
        }
        grid = _build_param_grid(param_space)

        values = grid["multiplier"]
        for v in values:
            assert v == round(v, 2), f"Value {v} not rounded to 2 decimals"

    def test_categorical_type_uses_choices(self):
        """Categorical param type returns the choices list directly."""
        from app.services.strategy_search import _build_param_grid

        param_space = {
            "signal_type": {"type": "categorical", "choices": ["ema", "sma", "wma"]},
        }
        grid = _build_param_grid(param_space)

        assert grid["signal_type"] == ["ema", "sma", "wma"]

    def test_categorical_type_empty_choices(self):
        """Categorical param with no choices key returns empty list."""
        from app.services.strategy_search import _build_param_grid

        param_space = {
            "mode": {"type": "categorical"},
        }
        grid = _build_param_grid(param_space)

        assert grid["mode"] == []

    def test_mixed_param_types(self):
        """Grid handles a mix of int, float, and categorical params."""
        from app.services.strategy_search import _build_param_grid

        param_space = {
            "period": {"type": "int", "low": 10, "high": 50},
            "threshold": {"type": "float", "low": 0.5, "high": 2.5},
            "method": {"type": "categorical", "choices": ["fast", "slow"]},
        }
        grid = _build_param_grid(param_space)

        assert len(grid) == 3
        assert all(isinstance(v, list) for v in grid.values())
        assert grid["method"] == ["fast", "slow"]
        assert all(isinstance(v, int) for v in grid["period"])
        assert all(isinstance(v, float) for v in grid["threshold"])

    def test_empty_param_space(self):
        """Empty param_space returns empty grid."""
        from app.services.strategy_search import _build_param_grid

        grid = _build_param_grid({})
        assert grid == {}


# ─── Strategy Detail API Tests ───────────────────────────────


class TestStrategyDetailEndpoint:
    """Test GET /strategies/{id}/detail returns full strategy with backtest data."""

    @pytest.mark.asyncio
    async def test_returns_strategy_with_backtest(self, client, test_user):
        """Detail endpoint returns strategy fields plus backtest metrics."""
        strategy = _make_strategy(test_user.id)
        backtest = _make_backtest(strategy.id, test_user.id)

        client._mock_db.execute = AsyncMock(side_effect=[
            MockResult([strategy]),   # strategy query
            MockResult([backtest]),   # backtest query
        ])

        resp = await client.get(f"/api/v1/strategies/{strategy.id}/detail")

        assert resp.status_code == 200
        data = resp.json()

        # Strategy fields
        assert data["id"] == str(strategy.id)
        assert data["name"] == "RSI Momentum"
        assert data["stock_code"] == "005930"
        assert data["stock_name"] == "Samsung Electronics"
        assert data["strategy_type"] == "indicator_based"
        assert data["indicators"] == [{"name": "RSI", "params": {"period": 14}}]
        assert data["parameters"] == {"rsi_oversold": 30, "rsi_overbought": 70}
        assert data["entry_rules"] == {"type": "rsi_crossover"}
        assert data["exit_rules"] == {"type": "rsi_exit"}
        assert data["risk_params"] == {"stop_loss_pct": 3}
        assert data["composite_score"] == 72.5
        assert data["validation_results"] == {"grade": "B+"}
        assert data["status"] == "validated"
        assert data["is_auto_trading"] is False
        assert "created_at" in data

        # Backtest data
        bt_data = data["backtest"]
        assert bt_data is not None
        assert bt_data["id"] == str(backtest.id)
        assert bt_data["date_range_start"] == "2024-01-01"
        assert bt_data["date_range_end"] == "2024-12-31"

        # Metrics
        metrics = bt_data["metrics"]
        assert metrics["total_return"] == 25.3
        assert metrics["annual_return"] == 18.7
        assert metrics["sharpe_ratio"] == 1.45
        assert metrics["sortino_ratio"] == 2.1
        assert metrics["max_drawdown"] == -8.5
        assert metrics["win_rate"] == 0.62
        assert metrics["profit_factor"] == 1.85
        assert metrics["total_trades"] == 42
        assert metrics["calmar_ratio"] == 2.2

        # Validation
        validation = bt_data["validation"]
        assert validation["wfa_score"] == 78.0
        assert validation["mc_score"] == 82.5
        assert validation["oos_score"] == 71.0

        # Raw data
        assert bt_data["equity_curve"] is not None
        assert len(bt_data["equity_curve"]) == 2
        assert bt_data["trade_log"] is not None

    @pytest.mark.asyncio
    async def test_returns_strategy_without_backtest(self, client, test_user):
        """Detail endpoint returns backtest=null when no completed backtest exists."""
        strategy = _make_strategy(test_user.id)

        client._mock_db.execute = AsyncMock(side_effect=[
            MockResult([strategy]),   # strategy query
            MockResult([]),           # no backtest found
        ])

        resp = await client.get(f"/api/v1/strategies/{strategy.id}/detail")

        assert resp.status_code == 200
        data = resp.json()

        assert data["id"] == str(strategy.id)
        assert data["name"] == "RSI Momentum"
        assert data["backtest"] is None

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_strategy(self, client, test_user):
        """Detail endpoint returns 404 when strategy does not exist."""
        client._mock_db.execute = AsyncMock(return_value=MockResult([]))

        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/v1/strategies/{fake_id}/detail")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Strategy not found"

    @pytest.mark.asyncio
    async def test_detail_respects_user_ownership(self, client, test_user):
        """Detail endpoint returns 404 if strategy belongs to a different user."""
        # The mock DB returns empty (simulating no match for user_id filter)
        client._mock_db.execute = AsyncMock(return_value=MockResult([]))

        other_user_strategy_id = uuid.uuid4()
        resp = await client.get(f"/api/v1/strategies/{other_user_strategy_id}/detail")

        assert resp.status_code == 404


# ─── Search Job Polling Tests ─────────────────────────────────


class TestSearchJobPolling:
    """Test GET /strategies/search-jobs/{job_id} for job status polling."""

    @pytest.mark.asyncio
    @patch("app.services.strategy_search.get_job_status")
    async def test_returns_404_for_unknown_job(self, mock_get_status, client):
        """Polling endpoint returns 404 when job_id is unknown."""
        mock_get_status.return_value = None

        fake_job_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/strategies/search-jobs/{fake_job_id}")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Job not found"
        mock_get_status.assert_called_once_with(fake_job_id)

    @pytest.mark.asyncio
    @patch("app.services.strategy_search.get_job_status")
    async def test_returns_running_job_status(self, mock_get_status, client):
        """Polling endpoint returns correct progress for running job."""
        job_id = str(uuid.uuid4())
        mock_get_status.return_value = {
            "status": "running",
            "progress": 45,
            "step": "optimizing:rsi",
            "result": None,
            "error": None,
        }

        resp = await client.get(f"/api/v1/strategies/search-jobs/{job_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == job_id
        assert data["status"] == "running"
        assert data["progress"] == 45
        assert data["step"] == "optimizing:rsi"
        assert data["result"] is None
        assert data["error"] is None

    @pytest.mark.asyncio
    @patch("app.services.strategy_search.get_job_status")
    async def test_returns_complete_job_with_result(self, mock_get_status, client):
        """Polling endpoint returns result payload when job completes."""
        job_id = str(uuid.uuid4())
        strategies_result = {
            "strategies_found": 3,
            "strategies": [
                {"id": str(uuid.uuid4()), "name": "RSI_005930", "score": 85.0},
            ],
            "stock_code": "005930",
            "data_rows": 500,
            "method": "grid",
        }
        mock_get_status.return_value = {
            "status": "complete",
            "progress": 100,
            "step": "done",
            "result": strategies_result,
            "error": None,
        }

        resp = await client.get(f"/api/v1/strategies/search-jobs/{job_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "complete"
        assert data["progress"] == 100
        assert data["result"]["strategies_found"] == 3
        assert len(data["result"]["strategies"]) == 1

    @pytest.mark.asyncio
    @patch("app.services.strategy_search.get_job_status")
    async def test_returns_error_job_status(self, mock_get_status, client):
        """Polling endpoint returns error details when job fails."""
        job_id = str(uuid.uuid4())
        mock_get_status.return_value = {
            "status": "error",
            "progress": 5,
            "step": "fetching_data",
            "result": None,
            "error": "데이터 부족: 10일",
        }

        resp = await client.get(f"/api/v1/strategies/search-jobs/{job_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "데이터 부족" in data["error"]


# ─── Search Kickoff Tests ─────────────────────────────────────


class TestSearchKickoff:
    """Test POST /strategies/search starts a strategy search job."""

    @pytest.mark.asyncio
    async def test_returns_job_id_and_running_status(self, client):
        """Search endpoint returns job_id and status='running'."""
        resp = await client.post("/api/v1/strategies/search", json={
            "stock_code": "005930",
            "date_range_start": "2024-01-01",
            "date_range_end": "2024-12-31",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "running"
        assert "message" in data
        # Verify job_id is a valid UUID
        uuid.UUID(data["job_id"])

    @pytest.mark.asyncio
    async def test_response_matches_schema(self, client):
        """Search response matches StrategySearchResponse schema fields."""
        from app.schemas.strategy import StrategySearchResponse

        resp = await client.post("/api/v1/strategies/search", json={
            "stock_code": "000660",
            "date_range_start": "2024-06-01",
            "date_range_end": "2024-12-31",
            "optimization_method": "bayesian",
            "data_source": "yahoo",
        })

        assert resp.status_code == 200
        data = resp.json()

        # Validate all StrategySearchResponse fields are present
        parsed = StrategySearchResponse(**data)
        assert parsed.job_id == data["job_id"]
        assert parsed.status == "running"
        assert isinstance(parsed.message, str)
        assert len(parsed.message) > 0

    @pytest.mark.asyncio
    async def test_search_with_default_params(self, client):
        """Search with only required fields uses defaults for optional params."""
        resp = await client.post("/api/v1/strategies/search", json={
            "stock_code": "005930",
            "date_range_start": "2024-01-01",
            "date_range_end": "2024-12-31",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        # Message should contain the stock code
        assert "005930" in data["message"]

    @pytest.mark.asyncio
    async def test_search_with_genetic_method(self, client):
        """Search accepts genetic optimization method."""
        resp = await client.post("/api/v1/strategies/search", json={
            "stock_code": "005930",
            "date_range_start": "2024-01-01",
            "date_range_end": "2024-12-31",
            "optimization_method": "genetic",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"

    @pytest.mark.asyncio
    async def test_search_missing_required_fields(self, client):
        """Search without required fields returns 422."""
        resp = await client.post("/api/v1/strategies/search", json={
            "stock_code": "005930",
            # Missing date_range_start and date_range_end
        })

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_multiple_search_jobs_get_unique_ids(self, client):
        """Each search request generates a unique job_id."""
        resp1 = await client.post("/api/v1/strategies/search", json={
            "stock_code": "005930",
            "date_range_start": "2024-01-01",
            "date_range_end": "2024-12-31",
        })
        resp2 = await client.post("/api/v1/strategies/search", json={
            "stock_code": "000660",
            "date_range_start": "2024-01-01",
            "date_range_end": "2024-12-31",
        })

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        job_id_1 = resp1.json()["job_id"]
        job_id_2 = resp2.json()["job_id"]
        assert job_id_1 != job_id_2
