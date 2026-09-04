"""Pure risk-threshold state machine; no broker calls live here."""

from __future__ import annotations

from decimal import Decimal
from zoneinfo import ZoneInfo

from .config import RiskConfig
from .models import AccountSnapshot, RiskLevel, RiskTransition, RuntimeState


class RiskEngine:
    def __init__(self, config: RiskConfig, timezone: str):
        self.config = config
        self.timezone = ZoneInfo(timezone)

    def observe(
        self,
        snapshot: AccountSnapshot,
        state: RuntimeState,
    ) -> RiskTransition | None:
        trade_date = snapshot.as_of.astimezone(self.timezone).date().isoformat()
        if state.trade_date != trade_date:
            start_nav = snapshot.net_liquidation - snapshot.daily_pnl
            if start_nav <= 0:
                raise ValueError("cannot infer a positive start-of-day NAV")
            state.reset_for_day(trade_date, start_nav)

        if state.start_nav is None:
            raise ValueError("runtime state has no start-of-day NAV")
        start_nav = Decimal(state.start_nav)
        loss_fraction = float(snapshot.daily_pnl / start_nav)
        state.last_daily_pnl = str(snapshot.daily_pnl)
        state.last_loss_fraction = loss_fraction

        candidate = self._candidate(loss_fraction)
        if candidate <= state.level:
            state.pending_level = state.level
            state.pending_count = 0
            return None

        if candidate == state.pending_level:
            state.pending_count += 1
        else:
            state.pending_level = candidate
            state.pending_count = 1

        if state.pending_count < self.config.confirm_samples:
            return None

        previous = state.level
        state.level = candidate
        state.pending_level = candidate
        state.pending_count = 0
        state.target_achieved = False
        state.reconcile_attempts = 0
        state.last_submit_at = None
        return RiskTransition(previous, candidate, loss_fraction)

    def _candidate(self, pnl_fraction: float) -> RiskLevel:
        if pnl_fraction <= -self.config.liquidate_loss:
            return RiskLevel.LIQUIDATE
        if pnl_fraction <= -self.config.reduce_loss:
            return RiskLevel.REDUCE
        if pnl_fraction <= -self.config.freeze_loss:
            return RiskLevel.FREEZE
        return RiskLevel.NORMAL
