"""Rebuild the latest target weights from an approved research artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant.backtest.risk_overlay import RiskOverlayConfig, apply_risk_overlay
from quant.data.research import load_market_close
from quant.strategies import get_strategy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("metrics_path", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    raw = args.metrics_path.read_bytes()
    payload = json.loads(raw)
    if payload.get("schema_version") == 2:
        parser.error("v2 next-open evidence requires a new paper execution adapter; this close-price signal bridge is legacy-only (pending S3)")
    required = {"strategy", "market", "params", "universe", "risk_overlay", "validation"}
    missing = required - payload.keys()
    if missing:
        parser.error(f"metrics artifact lacks paper-signal evidence: {sorted(missing)}")
    if not payload["validation"].get("walk_forward", {}).get("passed", False):
        parser.error("walk-forward evidence is not approved")
    if not payload["validation"].get("parameter_robustness", {}).get("passed", False):
        parser.error("parameter robustness evidence is not approved")

    close, _, _, universe = load_market_close(
        payload["market"], payload["universe"], payload.get("membership_file")
    )
    if payload.get("membership_sha256") != universe.get("membership_sha256"):
        parser.error("point-in-time membership hash changed since validation")
    decision = get_strategy(payload["strategy"])(close, **payload["params"])
    overlay = RiskOverlayConfig(**payload["risk_overlay"])
    target = apply_risk_overlay(close, decision, overlay).iloc[-1]
    prices = close.iloc[-1]
    active = target[target > 1e-10]
    signal = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "signal_date": str(close.index[-1].date()),
        "strategy": payload["strategy"],
        "market": payload["market"],
        "universe": universe["profile"],
        "evidence_path": str(args.metrics_path.resolve()),
        "evidence_sha256": hashlib.sha256(raw).hexdigest(),
        "target_weights": {symbol: round(float(weight), 10) for symbol, weight in active.items()},
        "prices": {
            symbol: round(float(price), 8)
            for symbol, price in prices.dropna().items()
        },
        "cash_weight": round(1.0 - float(active.sum()), 10),
    }
    encoded = json.dumps(signal, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
