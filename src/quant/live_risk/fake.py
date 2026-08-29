"""In-memory broker for deterministic simulations and tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from .models import AccountSnapshot, Position


class FakeBroker:
    def __init__(
        self,
        *,
        account: str = "DU_TEST",
        start_nav: Decimal = Decimal("100000"),
        positions: tuple[Position, ...] = (),
        partial_fill_ratio: Decimal = Decimal("1"),
    ):
        self.account = account
        self.start_nav = start_nav
        self.daily_pnl = Decimal("0")
        self.positions = {position.key: position for position in positions}
        self.partial_fill_ratio = partial_fill_ratio
        self.cancel_count = 0
        self.orders: list[dict] = []
        self.connected = False
        self.pnl_updated_at = datetime.now(UTC)

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    def set_daily_pnl(self, value: Decimal | str | float) -> None:
        self.daily_pnl = Decimal(str(value))
        self.pnl_updated_at = datetime.now(UTC)

    def snapshot(self) -> AccountSnapshot:
        if not self.connected:
            raise RuntimeError("fake broker is disconnected")
        now = datetime.now(UTC)
        return AccountSnapshot(
            account=self.account,
            as_of=now,
            pnl_updated_at=self.pnl_updated_at,
            net_liquidation=self.start_nav + self.daily_pnl,
            daily_pnl=self.daily_pnl,
            positions=tuple(self.positions.values()),
        )

    def cancel_all_orders(self) -> None:
        self.cancel_count += 1

    def submit_close(
        self,
        position: Position,
        quantity: Decimal,
        order_ref: str,
    ) -> int:
        current = self.positions[position.key]
        fill = min(abs(current.quantity), quantity * self.partial_fill_ratio)
        if current.quantity > 0:
            updated_quantity = current.quantity - fill
            side = "SELL"
        else:
            updated_quantity = current.quantity + fill
            side = "BUY"
        self.positions[position.key] = Position(
            account=current.account,
            contract_id=current.contract_id,
            symbol=current.symbol,
            sec_type=current.sec_type,
            currency=current.currency,
            quantity=updated_quantity,
            exchange=current.exchange,
            primary_exchange=current.primary_exchange,
        )
        order_id = len(self.orders) + 1
        self.orders.append(
            {
                "order_id": order_id,
                "contract_id": position.contract_id,
                "symbol": position.symbol,
                "side": side,
                "quantity": str(quantity),
                "filled": str(fill),
                "order_ref": order_ref,
            }
        )
        return order_id
