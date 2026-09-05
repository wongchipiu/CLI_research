"""Broker orchestration for freeze, half-reduction, and full liquidation."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from .config import AppConfig
from .engine import RiskEngine
from .models import AccountSnapshot, Broker, Position, RiskLevel, RuntimeState
from .notify import WebhookNotifier
from .state import AuditWriter, StateStore, StatusWriter


class RiskController:
    def __init__(
        self,
        broker: Broker,
        config: AppConfig,
        *,
        state_store: StateStore | None = None,
        audit: AuditWriter | None = None,
        status: StatusWriter | None = None,
        notifier: WebhookNotifier | None = None,
    ):
        config.validate()
        self.broker = broker
        self.config = config
        self.engine = RiskEngine(config.risk, config.runtime.timezone)
        self.state_store = state_store or StateStore(config.runtime.state_path)
        self.audit = audit or AuditWriter(config.runtime.audit_path)
        self.status = status or StatusWriter(config.runtime.status_path)
        self.notifier = notifier or WebhookNotifier(config.runtime.webhook_env_var)
        self.state = self.state_store.load()

    def run_once(self) -> AccountSnapshot:
        snapshot = self.broker.snapshot()
        self._validate_account(snapshot)
        age = (datetime.now(UTC) - snapshot.pnl_updated_at).total_seconds()
        if age > self.config.runtime.max_pnl_age_seconds:
            self._handle_stale_data(snapshot, age)
            return snapshot

        if self.state.stale_data_latched:
            self.audit.append("PNL_DATA_RECOVERED", age_seconds=age)
            self.state.stale_data_latched = False

        transition = self.engine.observe(snapshot, self.state)
        if transition is not None:
            self.audit.append(
                "RISK_LEVEL_CHANGED",
                previous=transition.previous.name,
                current=transition.current.name,
                loss_fraction=transition.loss_fraction,
                daily_pnl=str(snapshot.daily_pnl),
                start_nav=self.state.start_nav,
            )
            self.notifier.send(
                "RISK_LEVEL_CHANGED",
                {
                    "account": snapshot.account,
                    "level": transition.current.name,
                    "loss_fraction": transition.loss_fraction,
                },
            )
            self._prepare_transition(snapshot, transition.current)

        self._maintain_controls(snapshot)
        self.state_store.save(self.state)
        self.status.write(snapshot, self.state, healthy=True, message="ok")
        return snapshot

    def _validate_account(self, snapshot: AccountSnapshot) -> None:
        expected = self.config.broker.expected_account
        if expected and snapshot.account != expected:
            raise RuntimeError(
                f"connected account {snapshot.account!r} does not match expected_account"
            )
        if self.config.broker.execution_enabled:
            if self.config.broker.environment == "paper" and not snapshot.account.upper().startswith("DU"):
                raise RuntimeError("refusing paper-mode orders for a non-DU account")

    def _handle_stale_data(self, snapshot: AccountSnapshot, age: float) -> None:
        if not self.state.stale_data_latched:
            self.audit.append("STALE_PNL_DATA", age_seconds=age)
            self.notifier.send(
                "STALE_PNL_DATA",
                {"account": snapshot.account, "age_seconds": age},
            )
            self.state.stale_data_latched = True
        if self.config.runtime.cancel_on_stale_data:
            self._cancel_if_due("stale_data")
        self.state_store.save(self.state)
        self.status.write(
            snapshot,
            self.state,
            healthy=False,
            message=f"PnL data is stale by {age:.1f}s",
        )

    def _prepare_transition(self, snapshot: AccountSnapshot, level: RiskLevel) -> None:
        managed = self._managed_positions(snapshot)
        if level == RiskLevel.REDUCE:
            keep_fraction = Decimal("1") - Decimal(str(self.config.risk.reduce_fraction))
            self.state.target_positions = {
                position.key: str(position.quantity * keep_fraction)
                for position in managed
            }
        elif level == RiskLevel.LIQUIDATE:
            self.state.target_positions = {position.key: "0" for position in managed}
        self.state.target_achieved = False
        self.state.reconcile_attempts = 0
        self.state.last_submit_at = None
        self.state_store.save(self.state)
        self._cancel_if_due(f"enter_{level.name.lower()}", force=True)

    def _maintain_controls(self, snapshot: AccountSnapshot) -> None:
        if self.state.level == RiskLevel.NORMAL:
            return
        if self.state.level == RiskLevel.FREEZE:
            self._cancel_if_due("freeze")
            return
        self._reconcile_targets(snapshot)

    def _reconcile_targets(self, snapshot: AccountSnapshot) -> None:
        positions = {position.key: position for position in self._managed_positions(snapshot)}
        for key in positions:
            if key not in self.state.target_positions:
                # Any position opened after the risk latch is unauthorized new risk.
                self.state.target_positions[key] = "0"

        orders: list[tuple[Position, Decimal]] = []
        for key, position in positions.items():
            target = Decimal(self.state.target_positions.get(key, "0"))
            quantity = self._close_quantity(position.quantity, target)
            if quantity > 0:
                orders.append((position, quantity))

        if not orders:
            if not self.state.target_achieved:
                self.audit.append(
                    "TARGET_POSITIONS_ACHIEVED",
                    level=self.state.level.name,
                    targets=self.state.target_positions,
                )
            self.state.target_achieved = True
            self._cancel_if_due("latched_target_achieved")
            return

        self.state.target_achieved = False
        if not self._reconcile_due():
            return

        self._cancel_if_due("reconcile", force=True)
        attempt = self.state.reconcile_attempts + 1
        submitted = []
        for position, quantity in orders:
            order_ref = (
                f"risk-{self.state.trade_date}-{self.state.level.name[:3]}-"
                f"{position.contract_id}-{attempt}"
            )
            if self.config.broker.execution_enabled:
                order_id = self.broker.submit_close(position, quantity, order_ref)
            else:
                order_id = "DRY_RUN"
            submitted.append(
                {
                    "order_id": str(order_id),
                    "symbol": position.symbol,
                    "contract_id": position.contract_id,
                    "quantity": str(quantity),
                    "current": str(position.quantity),
                    "target": self.state.target_positions[position.key],
                    "order_ref": order_ref,
                }
            )
        self.state.reconcile_attempts = attempt
        self.state.last_submit_at = datetime.now(UTC).isoformat()
        self.audit.append(
            "CLOSE_ORDERS_SUBMITTED" if self.config.broker.execution_enabled else "CLOSE_ORDERS_PLANNED",
            level=self.state.level.name,
            attempt=attempt,
            orders=submitted,
        )
        if attempt == self.config.runtime.max_fast_reconcile_attempts:
            self.notifier.send(
                "RECONCILIATION_SLOW",
                {"account": snapshot.account, "level": self.state.level.name},
            )

    @staticmethod
    def _close_quantity(current: Decimal, target: Decimal) -> Decimal:
        if current == 0:
            return Decimal("0")
        if target == 0:
            return abs(current)
        if (current > 0) != (target > 0):
            return abs(current)
        if abs(current) > abs(target):
            return abs(current) - abs(target)
        return Decimal("0")

    def _managed_positions(self, snapshot: AccountSnapshot) -> tuple[Position, ...]:
        allowed = set(self.config.risk.managed_security_types)
        return tuple(
            position
            for position in snapshot.positions
            if position.sec_type in allowed and position.quantity != 0
        )

    def _reconcile_due(self) -> bool:
        if self.state.last_submit_at is None:
            return True
        elapsed = (
            datetime.now(UTC) - datetime.fromisoformat(self.state.last_submit_at)
        ).total_seconds()
        if self.state.reconcile_attempts < self.config.runtime.max_fast_reconcile_attempts:
            return elapsed >= self.config.runtime.fill_check_seconds
        return elapsed >= self.config.runtime.manual_retry_seconds

    def _cancel_if_due(self, reason: str, *, force: bool = False) -> None:
        if not force and self.state.last_cancel_at is not None:
            elapsed = (
                datetime.now(UTC) - datetime.fromisoformat(self.state.last_cancel_at)
            ).total_seconds()
            if elapsed < self.config.runtime.freeze_cancel_interval_seconds:
                return
        if self.config.broker.execution_enabled:
            self.broker.cancel_all_orders()
        self.state.last_cancel_at = datetime.now(UTC).isoformat()
        self.audit.append(
            "ALL_ORDERS_CANCELLED" if self.config.broker.execution_enabled else "ALL_ORDERS_CANCEL_PLANNED",
            reason=reason,
        )
