"""Small dependency-free domain models for the live risk service."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import IntEnum
from typing import Protocol


class RiskLevel(IntEnum):
    NORMAL = 0
    FREEZE = 1
    REDUCE = 2
    LIQUIDATE = 3


@dataclass(frozen=True)
class Position:
    account: str
    contract_id: int
    symbol: str
    sec_type: str
    currency: str
    quantity: Decimal
    exchange: str = "SMART"
    primary_exchange: str = ""

    @property
    def key(self) -> str:
        return str(self.contract_id)


@dataclass(frozen=True)
class AccountSnapshot:
    account: str
    as_of: datetime
    pnl_updated_at: datetime
    net_liquidation: Decimal
    daily_pnl: Decimal
    positions: tuple[Position, ...] = ()
    excess_liquidity: Decimal | None = None
    available_funds: Decimal | None = None


@dataclass
class RuntimeState:
    trade_date: str = ""
    level: RiskLevel = RiskLevel.NORMAL
    start_nav: str | None = None
    pending_level: RiskLevel = RiskLevel.NORMAL
    pending_count: int = 0
    target_positions: dict[str, str] = field(default_factory=dict)
    target_achieved: bool = False
    last_submit_at: str | None = None
    last_cancel_at: str | None = None
    reconcile_attempts: int = 0
    stale_data_latched: bool = False
    last_daily_pnl: str | None = None
    last_loss_fraction: float | None = None
    updated_at: str | None = None

    def reset_for_day(self, trade_date: str, start_nav: Decimal) -> None:
        self.trade_date = trade_date
        self.level = RiskLevel.NORMAL
        self.start_nav = str(start_nav)
        self.pending_level = RiskLevel.NORMAL
        self.pending_count = 0
        self.target_positions = {}
        self.target_achieved = False
        self.last_submit_at = None
        self.last_cancel_at = None
        self.reconcile_attempts = 0
        self.stale_data_latched = False
        self.last_daily_pnl = None
        self.last_loss_fraction = None

    def to_dict(self) -> dict:
        result = asdict(self)
        result["level"] = self.level.name
        result["pending_level"] = self.pending_level.name
        return result

    @classmethod
    def from_dict(cls, payload: dict) -> "RuntimeState":
        values = dict(payload)
        values["level"] = RiskLevel[values.get("level", "NORMAL")]
        values["pending_level"] = RiskLevel[values.get("pending_level", "NORMAL")]
        known = cls.__dataclass_fields__
        return cls(**{key: value for key, value in values.items() if key in known})


@dataclass(frozen=True)
class RiskTransition:
    previous: RiskLevel
    current: RiskLevel
    loss_fraction: float


class Broker(Protocol):
    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def is_connected(self) -> bool: ...

    def snapshot(self) -> AccountSnapshot: ...

    def cancel_all_orders(self) -> None: ...

    def submit_close(
        self,
        position: Position,
        quantity: Decimal,
        order_ref: str,
    ) -> int | str: ...
