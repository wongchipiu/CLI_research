"""Read-only readiness checks; this module never connects to TWS."""

from __future__ import annotations

import importlib.util
import sys

from .config import AppConfig


def preflight_report(config: AppConfig, *, ibapi_available: bool | None = None) -> dict:
    config.validate()
    available = bool(importlib.util.find_spec("ibapi")) if ibapi_available is None else ibapi_available
    checks = [
        {
            "name": "paper_environment",
            "passed": config.broker.environment == "paper",
            "actual": config.broker.environment,
            "required": "paper",
        },
        {
            "name": "exact_du_account",
            "passed": bool(config.broker.expected_account)
            and config.broker.expected_account.upper().startswith("DU")
            and "REPLACE" not in config.broker.expected_account.upper(),
            "actual": config.broker.expected_account,
            "required": "exact DU paper account",
        },
        {
            "name": "official_ibapi_installed",
            "passed": available,
            "actual": available,
            "required": True,
        },
        {
            "name": "localhost_only",
            "passed": config.broker.host in {"127.0.0.1", "localhost"},
            "actual": config.broker.host,
            "required": "127.0.0.1 or localhost",
        },
        {
            "name": "runtime_paths_absolute",
            "passed": all(
                path.is_absolute()
                for path in (
                    config.runtime.state_path,
                    config.runtime.status_path,
                    config.runtime.audit_path,
                    config.runtime.log_path,
                )
            ),
            "actual": "resolved",
            "required": True,
        },
    ]
    return {
        "schema_version": 1,
        "artifact_type": "live_risk_preflight",
        "ready": all(check["passed"] for check in checks),
        "execution_mode": "DRY_RUN" if config.broker.dry_run else "PAPER_ORDERS",
        "python": sys.executable,
        "checks": checks,
    }
