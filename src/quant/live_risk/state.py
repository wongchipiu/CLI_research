"""Atomic runtime state, health status, and append-only audit output."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from .models import AccountSnapshot, RuntimeState


def _atomic_json_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


class StateStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> RuntimeState:
        if not self.path.exists():
            return RuntimeState()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return RuntimeState.from_dict(payload)

    def save(self, state: RuntimeState) -> None:
        state.updated_at = datetime.now(UTC).isoformat()
        _atomic_json_write(self.path, state.to_dict())


class StatusWriter:
    def __init__(self, path: Path):
        self.path = path

    def write(
        self,
        snapshot: AccountSnapshot,
        state: RuntimeState,
        *,
        healthy: bool,
        message: str,
    ) -> None:
        payload = {
            "schema_version": 1,
            "artifact_type": "live_risk_status",
            "updated_at": datetime.now(UTC).isoformat(),
            "account": snapshot.account,
            "as_of": snapshot.as_of.isoformat(),
            "pnl_updated_at": snapshot.pnl_updated_at.isoformat(),
            "net_liquidation": str(snapshot.net_liquidation),
            "daily_pnl": str(snapshot.daily_pnl),
            "position_count": len(snapshot.positions),
            "healthy": healthy,
            "message": message,
            "state": state.to_dict(),
        }
        _atomic_json_write(self.path, payload)

    def write_error(self, state: RuntimeState, message: str, *, account: str = "") -> None:
        """Publish service failure even when no broker snapshot is available."""
        payload = {
            "schema_version": 1,
            "artifact_type": "live_risk_status",
            "updated_at": datetime.now(UTC).isoformat(),
            "account": account,
            "as_of": None,
            "pnl_updated_at": None,
            "net_liquidation": None,
            "daily_pnl": None,
            "position_count": None,
            "healthy": False,
            "message": message,
            "state": state.to_dict(),
        }
        _atomic_json_write(self.path, payload)


class AuditWriter:
    def __init__(self, path: Path):
        self.path = path
        self._lock = Lock()

    def append(self, event: str, **details) -> None:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            **details,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
