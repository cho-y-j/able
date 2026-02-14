"""Paper trading broker that simulates order fills locally.

Uses real market data for pricing but does not submit orders to KIS.
Simulates realistic fills with configurable slippage and latency.
"""

import uuid
import random
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class FillModel(str, Enum):
    IMMEDIATE = "immediate"  # Fill at current price instantly
    REALISTIC = "realistic"  # Add random slippage and partial fills


@dataclass
class PaperOrder:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stock_code: str = ""
    stock_name: str = ""
    side: str = "buy"  # buy or sell
    order_type: str = "market"  # market or limit
    quantity: int = 0
    limit_price: float | None = None
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    status: str = "pending"
    slippage_bps: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    filled_at: str | None = None
    strategy_id: str | None = None


@dataclass
class PaperPosition:
    stock_code: str
    stock_name: str = ""
    quantity: int = 0
    avg_cost_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    strategy_id: str | None = None


@dataclass
class PaperTrade:
    stock_code: str
    side: str
    quantity: int
    entry_price: float
    exit_price: float
    pnl: float
    pnl_percent: float
    entry_at: str
    exit_at: str
    strategy_id: str | None = None


class PaperBroker:
    """Simulated broker for paper trading.

    Maintains in-memory positions, orders, and trade history.
    Uses real market prices for fills with configurable slippage.
    """

    def __init__(
        self,
        initial_cash: float = 100_000_000,  # 1억 KRW
        fill_model: FillModel = FillModel.REALISTIC,
        slippage_bps_range: tuple[float, float] = (0.0, 5.0),
    ):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.fill_model = fill_model
        self.slippage_bps_range = slippage_bps_range

        self.orders: list[PaperOrder] = []
        self.positions: dict[str, PaperPosition] = {}  # keyed by stock_code
        self.trades: list[PaperTrade] = []

    @property
    def portfolio_value(self) -> float:
        """Total portfolio value (cash + positions)."""
        pos_value = sum(
            p.current_price * p.quantity for p in self.positions.values() if p.quantity > 0
        )
        return self.cash + pos_value

    @property
    def total_pnl(self) -> float:
        return self.portfolio_value - self.initial_cash

    @property
    def total_pnl_pct(self) -> float:
        if self.initial_cash == 0:
            return 0
        return (self.total_pnl / self.initial_cash) * 100

    @property
    def unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.positions.values() if p.quantity > 0)

    @property
    def realized_pnl(self) -> float:
        return sum(t.pnl for t in self.trades)

    def place_order(
        self,
        stock_code: str,
        side: str,
        quantity: int,
        current_price: float,
        stock_name: str = "",
        order_type: str = "market",
        limit_price: float | None = None,
        strategy_id: str | None = None,
    ) -> PaperOrder:
        """Place a paper order and fill it immediately."""
        order = PaperOrder(
            stock_code=stock_code,
            stock_name=stock_name,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
            strategy_id=strategy_id,
        )

        # Check limit order conditions
        if order_type == "limit" and limit_price:
            if side == "buy" and current_price > limit_price:
                order.status = "pending"
                self.orders.append(order)
                return order
            elif side == "sell" and current_price < limit_price:
                order.status = "pending"
                self.orders.append(order)
                return order

        # Fill the order
        fill_price = self._calculate_fill_price(current_price, side)

        # Check if we have enough cash for buy
        total_cost = fill_price * quantity
        if side == "buy" and total_cost > self.cash:
            order.status = "rejected"
            self.orders.append(order)
            logger.warning(f"Paper order rejected: insufficient cash ({self.cash:.0f} < {total_cost:.0f})")
            return order

        self._fill_order(order, fill_price)
        self.orders.append(order)
        return order

    def _calculate_fill_price(self, current_price: float, side: str) -> float:
        """Calculate simulated fill price with slippage."""
        if self.fill_model == FillModel.IMMEDIATE:
            return current_price

        # Realistic: add slippage
        slippage_bps = random.uniform(*self.slippage_bps_range)
        slippage_pct = slippage_bps / 10000

        if side == "buy":
            return current_price * (1 + slippage_pct)  # Buy slightly higher
        else:
            return current_price * (1 - slippage_pct)  # Sell slightly lower

    def _fill_order(self, order: PaperOrder, fill_price: float) -> None:
        """Fill an order and update positions/cash."""
        order.filled_quantity = order.quantity
        order.avg_fill_price = fill_price
        order.status = "filled"
        order.filled_at = datetime.now(timezone.utc).isoformat()

        if order.side == "buy":
            self._process_buy(order, fill_price)
        else:
            self._process_sell(order, fill_price)

        # Calculate slippage vs market price
        if order.limit_price:
            expected = order.limit_price
        else:
            expected = fill_price  # For market orders, fill IS the price

        if expected > 0:
            if order.side == "buy":
                order.slippage_bps = ((fill_price - expected) / expected) * 10000
            else:
                order.slippage_bps = ((expected - fill_price) / expected) * 10000

    def _process_buy(self, order: PaperOrder, fill_price: float) -> None:
        """Process a buy order: deduct cash, add/update position."""
        cost = fill_price * order.quantity
        self.cash -= cost

        pos = self.positions.get(order.stock_code)
        if pos and pos.quantity > 0:
            # Average up/down
            total_qty = pos.quantity + order.quantity
            total_cost = pos.avg_cost_price * pos.quantity + fill_price * order.quantity
            pos.avg_cost_price = total_cost / total_qty
            pos.quantity = total_qty
        else:
            self.positions[order.stock_code] = PaperPosition(
                stock_code=order.stock_code,
                stock_name=order.stock_name,
                quantity=order.quantity,
                avg_cost_price=fill_price,
                current_price=fill_price,
                strategy_id=order.strategy_id,
            )

    def _process_sell(self, order: PaperOrder, fill_price: float) -> None:
        """Process a sell order: add cash, reduce/close position, record trade."""
        proceeds = fill_price * order.quantity
        self.cash += proceeds

        pos = self.positions.get(order.stock_code)
        if not pos or pos.quantity <= 0:
            logger.warning(f"Selling without position: {order.stock_code}")
            return

        # Record the trade (round-trip P&L)
        pnl = (fill_price - pos.avg_cost_price) * order.quantity
        pnl_pct = ((fill_price - pos.avg_cost_price) / pos.avg_cost_price) * 100 if pos.avg_cost_price > 0 else 0

        self.trades.append(PaperTrade(
            stock_code=order.stock_code,
            side="sell",
            quantity=order.quantity,
            entry_price=pos.avg_cost_price,
            exit_price=fill_price,
            pnl=pnl,
            pnl_percent=pnl_pct,
            entry_at=order.created_at,
            exit_at=order.filled_at or datetime.now(timezone.utc).isoformat(),
            strategy_id=pos.strategy_id,
        ))

        pos.quantity -= order.quantity
        pos.realized_pnl += pnl

    def update_prices(self, prices: dict[str, float]) -> None:
        """Update current prices for all positions."""
        for code, price in prices.items():
            pos = self.positions.get(code)
            if pos and pos.quantity > 0:
                pos.current_price = price
                pos.unrealized_pnl = (price - pos.avg_cost_price) * pos.quantity

    def try_fill_pending(self, prices: dict[str, float]) -> list[PaperOrder]:
        """Try to fill any pending limit orders at current prices."""
        filled = []
        for order in self.orders:
            if order.status != "pending" or not order.limit_price:
                continue

            price = prices.get(order.stock_code, 0)
            if price <= 0:
                continue

            should_fill = False
            if order.side == "buy" and price <= order.limit_price:
                should_fill = True
            elif order.side == "sell" and price >= order.limit_price:
                should_fill = True

            if should_fill:
                fill_price = self._calculate_fill_price(price, order.side)
                if order.side == "buy":
                    total_cost = fill_price * order.quantity
                    if total_cost > self.cash:
                        order.status = "rejected"
                        continue
                self._fill_order(order, fill_price)
                filled.append(order)

        return filled

    def get_stats(self) -> dict:
        """Get comprehensive paper trading statistics."""
        winning = [t for t in self.trades if t.pnl > 0]
        losing = [t for t in self.trades if t.pnl <= 0]
        total_trades = len(self.trades)

        win_rate = len(winning) / total_trades * 100 if total_trades > 0 else 0
        avg_win = sum(t.pnl for t in winning) / len(winning) if winning else 0
        avg_loss = sum(t.pnl for t in losing) / len(losing) if losing else 0
        profit_factor = abs(sum(t.pnl for t in winning)) / abs(sum(t.pnl for t in losing)) if losing and sum(t.pnl for t in losing) != 0 else 0

        max_drawdown = 0.0
        peak = self.initial_cash
        # Approximate drawdown from trade sequence
        equity = self.initial_cash
        for t in self.trades:
            equity += t.pnl
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100 if peak > 0 else 0
            if dd > max_drawdown:
                max_drawdown = dd

        return {
            "initial_cash": self.initial_cash,
            "cash": round(self.cash, 0),
            "portfolio_value": round(self.portfolio_value, 0),
            "total_pnl": round(self.total_pnl, 0),
            "total_pnl_pct": round(self.total_pnl_pct, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 0),
            "realized_pnl": round(self.realized_pnl, 0),
            "total_trades": total_trades,
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": round(win_rate, 1),
            "avg_win": round(avg_win, 0),
            "avg_loss": round(avg_loss, 0),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
            "open_positions": sum(1 for p in self.positions.values() if p.quantity > 0),
        }
