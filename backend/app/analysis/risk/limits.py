"""Portfolio-level risk limit enforcement."""


class RiskLimits:
    """Enforces portfolio-level risk constraints."""

    def __init__(
        self,
        total_capital: float,
        max_daily_loss_pct: float = 0.03,
        max_total_exposure_pct: float = 0.80,
        max_single_position_pct: float = 0.10,
        max_correlated_exposure_pct: float = 0.30,
    ):
        self.total_capital = total_capital
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_total_exposure_pct = max_total_exposure_pct
        self.max_single_position_pct = max_single_position_pct
        self.max_correlated_exposure_pct = max_correlated_exposure_pct

    @property
    def max_daily_loss(self) -> float:
        return self.total_capital * self.max_daily_loss_pct

    @property
    def max_total_exposure(self) -> float:
        return self.total_capital * self.max_total_exposure_pct

    @property
    def max_single_position(self) -> float:
        return self.total_capital * self.max_single_position_pct

    def check_order(
        self,
        order_value: float,
        current_exposure: float,
        daily_pnl: float,
        stock_code: str | None = None,
        existing_position_value: float = 0,
    ) -> dict:
        """Check if an order passes all risk limits.

        Returns:
            {"approved": bool, "reason": str, "max_allowed_value": float}
        """
        reasons = []
        max_allowed = order_value

        # 1. Daily loss limit check
        if daily_pnl < 0 and abs(daily_pnl) >= self.max_daily_loss:
            return {
                "approved": False,
                "reason": f"Daily loss limit breached: {abs(daily_pnl):,.0f} >= {self.max_daily_loss:,.0f}",
                "max_allowed_value": 0,
            }

        # 2. Total exposure check
        new_exposure = current_exposure + order_value
        if new_exposure > self.max_total_exposure:
            remaining = max(0, self.max_total_exposure - current_exposure)
            max_allowed = min(max_allowed, remaining)
            if remaining <= 0:
                return {
                    "approved": False,
                    "reason": f"Max exposure limit: {current_exposure:,.0f}/{self.max_total_exposure:,.0f}",
                    "max_allowed_value": 0,
                }
            reasons.append(f"Exposure capped: {new_exposure:,.0f} -> {current_exposure + remaining:,.0f}")

        # 3. Single position limit
        total_position = existing_position_value + order_value
        if total_position > self.max_single_position:
            remaining = max(0, self.max_single_position - existing_position_value)
            max_allowed = min(max_allowed, remaining)
            if remaining <= 0:
                return {
                    "approved": False,
                    "reason": f"Single position limit: {existing_position_value:,.0f}/{self.max_single_position:,.0f}",
                    "max_allowed_value": 0,
                }
            reasons.append(f"Position capped: {total_position:,.0f} -> {existing_position_value + remaining:,.0f}")

        # 4. Remaining daily loss budget
        daily_loss_remaining = self.max_daily_loss - abs(min(0, daily_pnl))
        if order_value * 0.03 > daily_loss_remaining:
            # 3% worst-case loss would breach daily limit
            safe_value = daily_loss_remaining / 0.03
            max_allowed = min(max_allowed, safe_value)
            reasons.append(f"Daily loss budget constrained: max {safe_value:,.0f}")

        return {
            "approved": True,
            "reason": "; ".join(reasons) if reasons else "All checks passed",
            "max_allowed_value": round(max_allowed, 0),
        }

    def daily_loss_check(self, realized_pnl: float, unrealized_pnl: float) -> dict:
        """Check if daily loss limit is breached.

        Returns:
            {"breached": bool, "total_pnl": float, "limit": float, "action": str}
        """
        total_pnl = realized_pnl + unrealized_pnl
        pnl_pct = total_pnl / self.total_capital if self.total_capital > 0 else 0
        breached = total_pnl < 0 and abs(total_pnl) >= self.max_daily_loss

        if breached:
            action = "HALT_TRADING"
        elif total_pnl < 0 and abs(total_pnl) >= self.max_daily_loss * 0.8:
            action = "WARNING"
        else:
            action = "NORMAL"

        return {
            "breached": breached,
            "total_pnl": round(total_pnl, 0),
            "pnl_pct": round(pnl_pct * 100, 2),
            "limit": round(self.max_daily_loss, 0),
            "action": action,
        }

    def drawdown_recovery_mode(
        self,
        current_drawdown: float,
        max_allowed: float = 0.15,
    ) -> dict:
        """Determine if we should enter drawdown recovery mode.

        Args:
            current_drawdown: Current drawdown as positive fraction (e.g., 0.10 = 10%)
            max_allowed: Maximum drawdown before full halt

        Returns:
            {"recovery_mode": bool, "position_scale": float, "action": str}
        """
        if current_drawdown >= max_allowed:
            return {
                "recovery_mode": True,
                "position_scale": 0.0,
                "action": "HALT_TRADING",
                "message": f"Max drawdown {current_drawdown:.1%} >= {max_allowed:.1%}. Trading halted.",
            }
        elif current_drawdown >= max_allowed * 0.7:
            scale = 0.3
            return {
                "recovery_mode": True,
                "position_scale": scale,
                "action": "REDUCE_SIZE",
                "message": f"Drawdown {current_drawdown:.1%}: reducing positions to {scale:.0%}",
            }
        elif current_drawdown >= max_allowed * 0.5:
            scale = 0.6
            return {
                "recovery_mode": True,
                "position_scale": scale,
                "action": "REDUCE_SIZE",
                "message": f"Drawdown {current_drawdown:.1%}: reducing positions to {scale:.0%}",
            }
        else:
            return {
                "recovery_mode": False,
                "position_scale": 1.0,
                "action": "NORMAL",
                "message": "Within acceptable drawdown limits",
            }
