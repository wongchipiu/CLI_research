"""Build an idempotent next-open paper target from approved v2 evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant.backtest.risk_overlay import RiskOverlayConfig, apply_risk_overlay
from quant.backtest.study import data_fingerprint
from quant.data.research import load_market_bars
from quant.strategies import get_strategy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("metrics_path", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    raw = args.metrics_path.read_bytes()
    payload = json.loads(raw)
    required = {"strategy", "market", "params", "universe", "risk_overlay", "validation", "research_protocol"}
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
    active = target[target > 1e-10]
    now = datetime.now(timezone.utc)
    signal_date = bars.close.index[-1].date()
    market_timezone, close_time = (
        (ZoneInfo("America/New_York"), time(16, 0))
        if payload["market"] == "us"
        else (ZoneInfo("Asia/Shanghai"), time(15, 0))
    )
    available_at = datetime.combine(signal_date, close_time, tzinfo=market_timezone)
    expires_at = available_at + timedelta(days=7)
    if now > expires_at:
        parser.error("latest local signal is already stale; update and quality-check market data first")
    target_weights = {symbol: round(float(weight), 10) for symbol, weight in active.items()}
    signal_identity = {
        "evidence_sha256": hashlib.sha256(raw).hexdigest(),
        "signal_date": signal_date.isoformat(),
        "signal_data_sha256": data_fingerprint(bars),
        "target_weights": target_weights,
        "execution_model": "next_open_v1",
    }
    signal_id = hashlib.sha256(
        json.dumps(signal_identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    signal = {
        "schema_version": 2,
        "artifact_type": "paper_target_signal",
        "signal_id": signal_id,
        "generated_at": now.isoformat(),
        "available_at": available_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "execution_model": "next_open_v1",
        "signal_date": signal_date.isoformat(),
        "strategy": payload["strategy"],
        "market": payload["market"],
        "universe": universe["profile"],
        "evidence_path": str(args.metrics_path.resolve()),
        "evidence_sha256": hashlib.sha256(raw).hexdigest(),
        "signal_data_sha256": signal_identity["signal_data_sha256"],
        "target_weights": target_weights,
        "reference_close_prices": {
            symbol: round(float(price), 8)
            for symbol, price in prices.dropna().items()
        },
        "cash_weight": round(1.0 - float(active.sum()), 10),
        "execution_prices_required": True,
    }
    encoded = json.dumps(signal, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
