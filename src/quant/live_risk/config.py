"""YAML configuration and non-bypassable account safety validation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class BrokerConfig:
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 71
    expected_account: str = ""
    environment: str = "paper"
    dry_run: bool = True
    allow_live_trading: bool = False
    connect_timeout_seconds: float = 15.0
    order_type: str = "MKT"
    time_in_force: str = "DAY"
    outside_rth: bool = False

    @property
    def execution_enabled(self) -> bool:
        return not self.dry_run

    def validate(self) -> None:
        if self.environment not in {"paper", "live"}:
            raise ValueError("broker.environment must be paper or live")
        if self.order_type != "MKT":
            raise ValueError("phase one only supports MKT close orders")
        if self.execution_enabled and not self.expected_account:
            raise ValueError("expected_account is required before enabling orders")
        if self.environment == "paper" and self.execution_enabled:
            if not self.expected_account.upper().startswith("DU"):
                raise ValueError("paper execution requires an exact DU paper account")
        if self.environment == "live" and self.execution_enabled:
            if not self.allow_live_trading:
                raise ValueError("live environment requires allow_live_trading=true")
            expected_ack = f"ALLOW:{self.expected_account}"
            if os.environ.get("IBKR_LIVE_TRADING_ACK") != expected_ack:
                raise ValueError(
                    "live environment requires IBKR_LIVE_TRADING_ACK=ALLOW:<exact-account>"
                )


@dataclass(frozen=True)
class RiskConfig:
    freeze_loss: float = 0.03
    reduce_loss: float = 0.04
    liquidate_loss: float = 0.05
    reduce_fraction: float = 0.50
    confirm_samples: int = 2
    managed_security_types: tuple[str, ...] = ("STK",)

    def validate(self) -> None:
        if not 0 < self.freeze_loss < self.reduce_loss < self.liquidate_loss < 1:
            raise ValueError("loss thresholds must satisfy 0 < freeze < reduce < liquidate < 1")
        if not 0 < self.reduce_fraction < 1:
            raise ValueError("reduce_fraction must be in (0, 1)")
        if self.confirm_samples < 1:
            raise ValueError("confirm_samples must be positive")
        if not self.managed_security_types:
            raise ValueError("managed_security_types cannot be empty")


@dataclass(frozen=True)
class RuntimeConfig:
    timezone: str = "America/New_York"
    poll_seconds: float = 1.0
    reconnect_seconds: float = 5.0
    max_pnl_age_seconds: float = 10.0
    cancel_on_stale_data: bool = True
    freeze_cancel_interval_seconds: float = 5.0
    fill_check_seconds: float = 8.0
    max_fast_reconcile_attempts: int = 3
    manual_retry_seconds: float = 60.0
    state_path: Path = Path("var/live_risk/state.json")
    status_path: Path = Path("var/live_risk/status.json")
    audit_path: Path = Path("var/live_risk/audit.jsonl")
    log_path: Path = Path("var/live_risk/service.log")
    webhook_env_var: str = "LIVE_RISK_WEBHOOK_URL"

    def validate(self) -> None:
        if self.poll_seconds <= 0 or self.reconnect_seconds <= 0:
            raise ValueError("poll and reconnect intervals must be positive")
        if self.max_pnl_age_seconds <= 0:
            raise ValueError("max_pnl_age_seconds must be positive")
        if self.fill_check_seconds <= 0 or self.manual_retry_seconds <= 0:
            raise ValueError("reconciliation intervals must be positive")
        if self.max_fast_reconcile_attempts < 1:
            raise ValueError("max_fast_reconcile_attempts must be positive")


@dataclass(frozen=True)
class AppConfig:
    broker: BrokerConfig
    risk: RiskConfig
    runtime: RuntimeConfig

    def validate(self) -> None:
        self.broker.validate()
        self.risk.validate()
        self.runtime.validate()


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    base = config_path.parent.parent if config_path.parent.name == "config" else config_path.parent

    broker = BrokerConfig(**payload.get("broker", {}))
    risk_values = dict(payload.get("risk", {}))
    if "managed_security_types" in risk_values:
        risk_values["managed_security_types"] = tuple(risk_values["managed_security_types"])
    risk = RiskConfig(**risk_values)

    runtime_values = dict(payload.get("runtime", {}))
    for key in ("state_path", "status_path", "audit_path", "log_path"):
        if key in runtime_values:
            value = Path(runtime_values[key])
            runtime_values[key] = value if value.is_absolute() else base / value
    runtime = RuntimeConfig(**runtime_values)
    config = AppConfig(broker=broker, risk=risk, runtime=runtime)
    config.validate()
    return config
