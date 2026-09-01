"""Build an idempotent next-open paper target from approved v2 evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant.backtest.risk_overlay import RiskOverlayConfig, apply_risk_overlay
from quant.backtest.study import data_fingerprint
from quant.data.research import load_market_bars
from quant.exchange_calendar import calendar_id, is_trading_date, session_close
from quant.strategies import get_strategy
from quant.workspace import WorkspaceConfig


STRATEGY_PACKAGE_FIELDS = (
    "strategy",
    "market",
    "params",
    "risk_overlay",
    "execution_model",
    "universe",
    "membership_sha256",
    "source_sha256",
    "data_snapshot_sha256",
)

PAPER_SIGNAL_IDENTITY_FIELDS = (
    "schema_version",
    "artifact_type",
    "signal_date",
    "generated_at",
    "available_at",
    "expires_at",
    "execution_model",
    "calendar_id",
    "strategy",
    "market",
    "universe",
    "evidence_sha256",
    "strategy_package_sha256",
    "signal_data_sha256",
    "target_weights",
)


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def select_fields(payload: dict, fields: tuple[str, ...], label: str) -> dict:
    missing = set(fields) - payload.keys()
    if missing:
        raise ValueError(f"{label} is missing fields: {sorted(missing)}")
    return {field: payload[field] for field in fields}


def main(now: datetime | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("metrics_path", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--workspace", type=Path, help="versioned workspace YAML; paths are cwd-independent")
    args = parser.parse_args()
    if args.workspace:
        workspace = WorkspaceConfig.load(args.workspace)
        workspace.apply()
        args.metrics_path = workspace.resolve_project_path(args.metrics_path)
        if args.output:
            args.output = workspace.resolve_project_path(args.output)

    raw = args.metrics_path.read_bytes()
    payload = json.loads(raw)
    required = {
        "strategy", "market", "params", "universe", "risk_overlay", "validation",
        "research_protocol", "membership_sha256", "source_sha256", "data_snapshot_sha256",
    }
    missing = required - payload.keys()
    if missing:
        parser.error(f"metrics artifact lacks paper-signal evidence: {sorted(missing)}")
    if (payload.get("schema_version") != 2 or payload.get("artifact_type") != "strategy_validation"
            or payload.get("execution_model") != "next_open_v1"):
        parser.error("paper signals require schema-v2 strategy validation with next_open_v1 execution")
    if payload["validation"].get("final_test_status") != "completed":
        parser.error("independent final-test evidence is not completed")
    if not payload["validation"].get("walk_forward", {}).get("passed", False):
        parser.error("walk-forward evidence is not approved")
    if not payload["validation"].get("parameter_robustness", {}).get("passed", False):
        parser.error("parameter robustness evidence is not approved")
    if payload.get("universe_point_in_time") is not True:
        parser.error("paper signals require point-in-time universe evidence")

    bars = load_market_bars(
        payload["market"], payload["universe"], payload.get("membership_file")
    )
    universe = bars.universe
    if payload.get("membership_sha256") != universe.get("membership_sha256"):
        parser.error("point-in-time membership hash changed since validation")
    decision = get_strategy(payload["strategy"])(bars.signal_close, **payload["params"])
    overlay = RiskOverlayConfig(**payload["risk_overlay"])
    target = apply_risk_overlay(bars.signal_close, decision, overlay).where(bars.eligible, 0.0).iloc[-1]
    prices = bars.close.iloc[-1]
    if any(not math.isfinite(float(weight)) for weight in target):
        parser.error("strategy produced non-finite target weights")
    active = target[target > 1e-10]
    current_time = now or datetime.now(timezone.utc)
    signal_date = bars.close.index[-1].date()
    if not is_trading_date(payload["market"], signal_date):
        parser.error("latest local signal date is not a session in the pinned exchange calendar")
    available_at = session_close(payload["market"], signal_date)
    expires_at = available_at + timedelta(days=7)
    if current_time > expires_at:
        parser.error("latest local signal is already stale; update and quality-check market data first")
    missing_reference_prices = [
        symbol for symbol in active.index
        if symbol not in prices or not math.isfinite(float(prices[symbol])) or float(prices[symbol]) <= 0
    ]
    if missing_reference_prices:
        parser.error(f"active targets lack valid reference closes: {sorted(missing_reference_prices)}")
    try:
        strategy_package_hash = canonical_sha256(
            select_fields(payload, STRATEGY_PACKAGE_FIELDS, "strategy package")
        )
    except (TypeError, ValueError) as exc:
        parser.error(f"strategy package is not canonical JSON: {exc}")
    evidence_hash = hashlib.sha256(raw).hexdigest()
    signal_data_hash = data_fingerprint(bars)
    target_weights = {symbol: round(float(weight), 10) for symbol, weight in active.items()}
    signal = {
        "schema_version": 4,
        "artifact_type": "paper_target_signal",
        "generated_at": available_at.isoformat(),
        "created_at": current_time.isoformat(),
        "available_at": available_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "execution_model": "next_open_v1",
        "calendar_id": calendar_id(payload["market"]),
        "signal_date": signal_date.isoformat(),
        "strategy": payload["strategy"],
        "market": payload["market"],
        "universe": universe["profile"],
        "evidence_path": str(args.metrics_path.resolve()),
        "evidence_sha256": evidence_hash,
        "strategy_package_sha256": strategy_package_hash,
        "signal_data_sha256": signal_data_hash,
        "target_weights": target_weights,
        "reference_close_prices": {
            symbol: round(float(price), 8)
            for symbol, price in prices.dropna().items()
        },
        "cash_weight": round(1.0 - float(active.sum()), 10),
        "execution_prices_required": True,
    }
    signal["signal_id"] = canonical_sha256(
        select_fields(signal, PAPER_SIGNAL_IDENTITY_FIELDS, "paper signal identity")
    )
    encoded = json.dumps(signal, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
