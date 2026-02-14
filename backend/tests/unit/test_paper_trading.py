"""Tests for paper trading simulation engine and API."""

import pytest
from app.simulation.paper_broker import PaperBroker, FillModel, PaperOrder, PaperPosition, PaperTrade
from app.simulation.paper_portfolio import PaperPortfolio, PaperSession


# ── PaperBroker Tests ──


class TestPaperBrokerBasics:
    def test_initial_state(self):
        broker = PaperBroker(initial_cash=50_000_000)
        assert broker.cash == 50_000_000
        assert broker.portfolio_value == 50_000_000
        assert broker.total_pnl == 0
        assert broker.total_pnl_pct == 0
        assert len(broker.orders) == 0
        assert len(broker.positions) == 0
        assert len(broker.trades) == 0

    def test_portfolio_value_includes_positions(self):
        broker = PaperBroker(initial_cash=10_000_000, fill_model=FillModel.IMMEDIATE)
        broker.place_order("005930", "buy", 100, current_price=70000)
        assert broker.cash == 10_000_000 - 70000 * 100
        assert broker.portfolio_value == 10_000_000  # cash + pos value

    def test_zero_initial_cash(self):
        broker = PaperBroker(initial_cash=0)
        assert broker.total_pnl_pct == 0


class TestPaperBrokerBuy:
    def test_buy_market_immediate(self):
        broker = PaperBroker(initial_cash=100_000_000, fill_model=FillModel.IMMEDIATE)
        order = broker.place_order("005930", "buy", 10, current_price=70000, stock_name="삼성전자")

        assert order.status == "filled"
        assert order.filled_quantity == 10
        assert order.avg_fill_price == 70000
        assert broker.cash == 100_000_000 - 700_000
        assert "005930" in broker.positions
        assert broker.positions["005930"].quantity == 10
        assert broker.positions["005930"].avg_cost_price == 70000

    def test_buy_insufficient_cash(self):
        broker = PaperBroker(initial_cash=500_000, fill_model=FillModel.IMMEDIATE)
        order = broker.place_order("005930", "buy", 100, current_price=70000)
        assert order.status == "rejected"
        assert broker.cash == 500_000  # unchanged

    def test_buy_averaging_up(self):
        broker = PaperBroker(initial_cash=100_000_000, fill_model=FillModel.IMMEDIATE)
        broker.place_order("005930", "buy", 10, current_price=70000)
        broker.place_order("005930", "buy", 10, current_price=80000)

        pos = broker.positions["005930"]
        assert pos.quantity == 20
        assert pos.avg_cost_price == 75000  # (70k*10 + 80k*10) / 20

    def test_buy_realistic_slippage(self):
        broker = PaperBroker(
            initial_cash=100_000_000,
            fill_model=FillModel.REALISTIC,
            slippage_bps_range=(10.0, 10.0),  # Fixed 10 bps
        )
        order = broker.place_order("005930", "buy", 10, current_price=100000)
        assert order.status == "filled"
        # 10 bps = 0.1%, so fill should be ~100100
        assert order.avg_fill_price == pytest.approx(100100, rel=1e-6)


class TestPaperBrokerSell:
    def test_sell_records_trade(self):
        broker = PaperBroker(initial_cash=100_000_000, fill_model=FillModel.IMMEDIATE)
        broker.place_order("005930", "buy", 10, current_price=70000)
        order = broker.place_order("005930", "sell", 10, current_price=75000)

        assert order.status == "filled"
        assert len(broker.trades) == 1

        trade = broker.trades[0]
        assert trade.stock_code == "005930"
        assert trade.entry_price == 70000
        assert trade.exit_price == 75000
        assert trade.pnl == 50000  # (75k - 70k) * 10
        assert trade.pnl_percent == pytest.approx(7.14, rel=0.1)

    def test_sell_partial(self):
        broker = PaperBroker(initial_cash=100_000_000, fill_model=FillModel.IMMEDIATE)
        broker.place_order("005930", "buy", 10, current_price=70000)
        broker.place_order("005930", "sell", 5, current_price=75000)

        assert broker.positions["005930"].quantity == 5
        assert broker.cash == 100_000_000 - 700_000 + 375_000

    def test_sell_without_position(self):
        broker = PaperBroker(initial_cash=100_000_000, fill_model=FillModel.IMMEDIATE)
        order = broker.place_order("005930", "sell", 10, current_price=70000)
        # Should fill but warn (short selling)
        assert order.status == "filled"

    def test_sell_realistic_slippage(self):
        broker = PaperBroker(
            initial_cash=100_000_000,
            fill_model=FillModel.REALISTIC,
            slippage_bps_range=(10.0, 10.0),
        )
        broker.place_order("005930", "buy", 10, current_price=100000)
        order = broker.place_order("005930", "sell", 10, current_price=100000)
        # Sell slippage: price * (1 - 0.001) = 99900
        assert order.avg_fill_price == pytest.approx(99900, rel=1e-6)


class TestPaperBrokerLimitOrders:
    def test_limit_buy_below_market(self):
        broker = PaperBroker(initial_cash=100_000_000, fill_model=FillModel.IMMEDIATE)
        order = broker.place_order(
            "005930", "buy", 10, current_price=70000,
            order_type="limit", limit_price=65000,
        )
        assert order.status == "pending"  # Price too high

    def test_limit_buy_at_or_below_limit(self):
        broker = PaperBroker(initial_cash=100_000_000, fill_model=FillModel.IMMEDIATE)
        order = broker.place_order(
            "005930", "buy", 10, current_price=60000,
            order_type="limit", limit_price=65000,
        )
        assert order.status == "filled"

    def test_limit_sell_above_market(self):
        broker = PaperBroker(initial_cash=100_000_000, fill_model=FillModel.IMMEDIATE)
        broker.place_order("005930", "buy", 10, current_price=70000)
        order = broker.place_order(
            "005930", "sell", 10, current_price=70000,
            order_type="limit", limit_price=75000,
        )
        assert order.status == "pending"  # Price too low

    def test_try_fill_pending(self):
        broker = PaperBroker(initial_cash=100_000_000, fill_model=FillModel.IMMEDIATE)
        broker.place_order(
            "005930", "buy", 10, current_price=70000,
            order_type="limit", limit_price=65000,
        )
        assert broker.orders[0].status == "pending"

        filled = broker.try_fill_pending({"005930": 64000})
        assert len(filled) == 1
        assert filled[0].status == "filled"
        assert broker.positions["005930"].quantity == 10


class TestPaperBrokerPriceUpdates:
    def test_update_prices(self):
        broker = PaperBroker(initial_cash=100_000_000, fill_model=FillModel.IMMEDIATE)
        broker.place_order("005930", "buy", 10, current_price=70000)

        broker.update_prices({"005930": 75000})
        pos = broker.positions["005930"]
        assert pos.current_price == 75000
        assert pos.unrealized_pnl == 50000  # (75k - 70k) * 10

    def test_update_prices_negative_pnl(self):
        broker = PaperBroker(initial_cash=100_000_000, fill_model=FillModel.IMMEDIATE)
        broker.place_order("005930", "buy", 10, current_price=70000)

        broker.update_prices({"005930": 65000})
        pos = broker.positions["005930"]
        assert pos.unrealized_pnl == -50000

    def test_update_prices_unknown_stock(self):
        broker = PaperBroker(initial_cash=100_000_000, fill_model=FillModel.IMMEDIATE)
        # Should not raise
        broker.update_prices({"999999": 50000})


class TestPaperBrokerStats:
    def test_stats_no_trades(self):
        broker = PaperBroker(initial_cash=100_000_000)
        stats = broker.get_stats()
        assert stats["total_trades"] == 0
        assert stats["win_rate"] == 0
        assert stats["profit_factor"] == 0
        assert stats["max_drawdown_pct"] == 0

    def test_stats_with_trades(self):
        broker = PaperBroker(initial_cash=100_000_000, fill_model=FillModel.IMMEDIATE)
        # Winning trade
        broker.place_order("005930", "buy", 10, current_price=70000)
        broker.place_order("005930", "sell", 10, current_price=80000)
        # Losing trade
        broker.place_order("000660", "buy", 10, current_price=150000)
        broker.place_order("000660", "sell", 10, current_price=140000)

        stats = broker.get_stats()
        assert stats["total_trades"] == 2
        assert stats["winning_trades"] == 1
        assert stats["losing_trades"] == 1
        assert stats["win_rate"] == 50.0
        assert stats["avg_win"] == 100000  # (80k-70k)*10
        assert stats["avg_loss"] == -100000  # (140k-150k)*10
        assert stats["profit_factor"] == 1.0

    def test_stats_max_drawdown(self):
        broker = PaperBroker(initial_cash=10_000_000, fill_model=FillModel.IMMEDIATE)
        # Win then lose big
        broker.place_order("A", "buy", 100, current_price=10000, stock_name="A")
        broker.place_order("A", "sell", 100, current_price=12000)  # +200k
        broker.place_order("B", "buy", 100, current_price=10000, stock_name="B")
        broker.place_order("B", "sell", 100, current_price=7000)  # -300k

        stats = broker.get_stats()
        assert stats["max_drawdown_pct"] > 0


# ── PaperPortfolio / PaperSession Tests ──


class TestPaperPortfolio:
    def setup_method(self):
        PaperPortfolio.reset()

    def test_create_session(self):
        session = PaperPortfolio.create_session(
            user_id="user1", name="Test", initial_cash=50_000_000
        )
        assert session.user_id == "user1"
        assert session.name == "Test"
        assert session.status == "active"
        assert session.initial_cash == 50_000_000
        assert PaperPortfolio.get_session(session.id) is session

    def test_list_sessions(self):
        PaperPortfolio.create_session(user_id="user1", name="Session A")
        PaperPortfolio.create_session(user_id="user1", name="Session B")
        PaperPortfolio.create_session(user_id="user2", name="Session C")

        u1_sessions = PaperPortfolio.list_sessions("user1")
        assert len(u1_sessions) == 2
        u2_sessions = PaperPortfolio.list_sessions("user2")
        assert len(u2_sessions) == 1

    def test_get_broker(self):
        session = PaperPortfolio.create_session(user_id="user1")
        broker = PaperPortfolio.get_broker(session.id)
        assert broker is not None
        assert broker.initial_cash == 100_000_000

    def test_stop_session(self):
        session = PaperPortfolio.create_session(user_id="user1")
        stopped = PaperPortfolio.stop_session(session.id)
        assert stopped.status == "completed"
        assert stopped.ended_at is not None

    def test_stop_nonexistent_session(self):
        result = PaperPortfolio.stop_session("nonexistent")
        assert result is None

    def test_session_summary_empty(self):
        session = PaperPortfolio.create_session(user_id="user1")
        summary = PaperPortfolio.get_session_summary(session.id)
        assert summary is not None
        assert summary["stats"]["total_trades"] == 0
        assert summary["positions"] == []
        assert summary["orders"] == []
        assert summary["trades"] == []
        assert len(summary["equity_curve"]) == 1

    def test_session_summary_with_trades(self):
        session = PaperPortfolio.create_session(
            user_id="user1", fill_model="immediate"
        )
        broker = PaperPortfolio.get_broker(session.id)
        broker.place_order("005930", "buy", 10, current_price=70000, stock_name="삼성전자")
        broker.place_order("005930", "sell", 5, current_price=75000)

        summary = PaperPortfolio.get_session_summary(session.id)
        assert len(summary["positions"]) == 1
        assert summary["positions"][0]["stock_code"] == "005930"
        assert summary["positions"][0]["quantity"] == 5
        assert len(summary["orders"]) == 2
        assert len(summary["trades"]) == 1
        assert summary["trades"][0]["pnl"] == 25000  # (75k-70k)*5

    def test_session_summary_equity_curve(self):
        session = PaperPortfolio.create_session(
            user_id="user1", initial_cash=10_000_000, fill_model="immediate"
        )
        broker = PaperPortfolio.get_broker(session.id)
        broker.place_order("A", "buy", 100, current_price=10000, stock_name="A")
        broker.place_order("A", "sell", 100, current_price=11000)

        summary = PaperPortfolio.get_session_summary(session.id)
        curve = summary["equity_curve"]
        assert len(curve) == 2
        assert curve[0]["value"] == 10_000_000
        assert curve[1]["value"] == 10_100_000  # +100k pnl

    def test_reset(self):
        PaperPortfolio.create_session(user_id="user1")
        PaperPortfolio.reset()
        assert PaperPortfolio.list_sessions("user1") == []

    def test_fill_model_realistic(self):
        session = PaperPortfolio.create_session(
            user_id="user1", fill_model="realistic"
        )
        broker = PaperPortfolio.get_broker(session.id)
        assert broker.fill_model == FillModel.REALISTIC

    def test_fill_model_immediate(self):
        session = PaperPortfolio.create_session(
            user_id="user1", fill_model="immediate"
        )
        broker = PaperPortfolio.get_broker(session.id)
        assert broker.fill_model == FillModel.IMMEDIATE


# ── Paper Trading API Tests ──


@pytest.mark.asyncio
class TestPaperAPI:
    """Test paper trading API endpoints via httpx."""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        PaperPortfolio.reset()
        yield
        PaperPortfolio.reset()

    @pytest.fixture
    async def client(self):
        import uuid
        from httpx import AsyncClient, ASGITransport
        from app.main import create_app
        from app.api.v1.deps import get_current_user

        app = create_app()

        class FakeUser:
            id = uuid.UUID("11111111-1111-1111-1111-111111111111")
            email = "test@test.com"

        async def override_user():
            return FakeUser()

        app.dependency_overrides[get_current_user] = override_user
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    async def test_create_session(self, client):
        res = await client.post("/api/v1/paper/sessions", json={
            "name": "Test Paper", "initial_cash": 50000000, "fill_model": "immediate"
        })
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "Test Paper"
        assert data["status"] == "active"
        assert data["initial_cash"] == 50000000

    async def test_list_sessions(self, client):
        await client.post("/api/v1/paper/sessions", json={"name": "S1"})
        await client.post("/api/v1/paper/sessions", json={"name": "S2"})
        res = await client.get("/api/v1/paper/sessions")
        assert res.status_code == 200
        assert len(res.json()) == 2

    async def test_get_session_summary(self, client):
        create = await client.post("/api/v1/paper/sessions", json={"name": "Test"})
        sid = create.json()["id"]
        res = await client.get(f"/api/v1/paper/sessions/{sid}")
        assert res.status_code == 200
        data = res.json()
        assert "stats" in data
        assert "positions" in data
        assert "orders" in data

    async def test_get_session_not_found(self, client):
        res = await client.get("/api/v1/paper/sessions/nonexistent")
        assert res.status_code == 404

    async def test_stop_session(self, client):
        create = await client.post("/api/v1/paper/sessions", json={"name": "Test"})
        sid = create.json()["id"]
        res = await client.post(f"/api/v1/paper/sessions/{sid}/stop")
        assert res.status_code == 200
        assert res.json()["status"] == "completed"

    async def test_stop_already_stopped(self, client):
        create = await client.post("/api/v1/paper/sessions", json={"name": "Test"})
        sid = create.json()["id"]
        await client.post(f"/api/v1/paper/sessions/{sid}/stop")
        res = await client.post(f"/api/v1/paper/sessions/{sid}/stop")
        assert res.status_code == 400

    async def test_place_order_buy(self, client):
        create = await client.post("/api/v1/paper/sessions", json={
            "name": "Test", "fill_model": "immediate"
        })
        sid = create.json()["id"]
        res = await client.post(f"/api/v1/paper/sessions/{sid}/order", json={
            "stock_code": "005930", "stock_name": "삼성전자",
            "side": "buy", "quantity": 10, "current_price": 70000,
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "filled"
        assert data["filled_quantity"] == 10
        assert data["avg_fill_price"] == 70000

    async def test_place_order_sell(self, client):
        create = await client.post("/api/v1/paper/sessions", json={
            "name": "Test", "fill_model": "immediate"
        })
        sid = create.json()["id"]
        await client.post(f"/api/v1/paper/sessions/{sid}/order", json={
            "stock_code": "005930", "side": "buy", "quantity": 10, "current_price": 70000,
        })
        res = await client.post(f"/api/v1/paper/sessions/{sid}/order", json={
            "stock_code": "005930", "side": "sell", "quantity": 10, "current_price": 75000,
        })
        assert res.status_code == 200
        assert res.json()["status"] == "filled"

    async def test_place_order_invalid_side(self, client):
        create = await client.post("/api/v1/paper/sessions", json={"name": "Test"})
        sid = create.json()["id"]
        res = await client.post(f"/api/v1/paper/sessions/{sid}/order", json={
            "stock_code": "005930", "side": "invalid", "quantity": 10, "current_price": 70000,
        })
        assert res.status_code == 400

    async def test_place_order_on_stopped_session(self, client):
        create = await client.post("/api/v1/paper/sessions", json={"name": "Test"})
        sid = create.json()["id"]
        await client.post(f"/api/v1/paper/sessions/{sid}/stop")
        res = await client.post(f"/api/v1/paper/sessions/{sid}/order", json={
            "stock_code": "005930", "side": "buy", "quantity": 10, "current_price": 70000,
        })
        assert res.status_code == 400

    async def test_update_prices(self, client):
        create = await client.post("/api/v1/paper/sessions", json={
            "name": "Test", "fill_model": "immediate"
        })
        sid = create.json()["id"]
        await client.post(f"/api/v1/paper/sessions/{sid}/order", json={
            "stock_code": "005930", "side": "buy", "quantity": 10, "current_price": 70000,
        })
        res = await client.post(f"/api/v1/paper/sessions/{sid}/prices", json={
            "prices": {"005930": 75000}
        })
        assert res.status_code == 200
        assert res.json()["prices_updated"] == 1

    async def test_full_round_trip(self, client):
        """Full session: create → buy → update prices → sell → check summary."""
        create = await client.post("/api/v1/paper/sessions", json={
            "name": "Full Test", "initial_cash": 10000000, "fill_model": "immediate"
        })
        sid = create.json()["id"]

        # Buy
        await client.post(f"/api/v1/paper/sessions/{sid}/order", json={
            "stock_code": "005930", "stock_name": "삼성전자",
            "side": "buy", "quantity": 100, "current_price": 70000,
        })

        # Update prices
        await client.post(f"/api/v1/paper/sessions/{sid}/prices", json={
            "prices": {"005930": 75000}
        })

        # Sell
        await client.post(f"/api/v1/paper/sessions/{sid}/order", json={
            "stock_code": "005930", "side": "sell", "quantity": 100, "current_price": 75000,
        })

        # Check summary
        res = await client.get(f"/api/v1/paper/sessions/{sid}")
        data = res.json()
        assert data["stats"]["total_trades"] == 1
        assert data["stats"]["realized_pnl"] == 500000  # (75k-70k)*100
        assert data["stats"]["win_rate"] == 100.0
        assert len(data["trades"]) == 1

    async def test_invalid_fill_model(self, client):
        res = await client.post("/api/v1/paper/sessions", json={
            "name": "Test", "fill_model": "invalid"
        })
        assert res.status_code == 400
