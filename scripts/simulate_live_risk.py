"""Exercise the complete controller without connecting to Interactive Brokers."""

from __future__ import annotations

import json
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant.live_risk.config import AppConfig, BrokerConfig, RiskConfig, RuntimeConfig
from quant.live_risk.controller import RiskController
from quant.live_risk.fake import FakeBroker
from quant.live_risk.models import Position


def main() -> int:
    positions = (
        Position("DU_TEST", 1, "AAPL", "STK", "USD", Decimal("100")),
        Position("DU_TEST", 2, "MRNA", "STK", "USD", Decimal("900")),
        Position("DU_TEST", 3, "SHORT", "STK", "USD", Decimal("-50")),
    )
    broker = FakeBroker(positions=positions)
    broker.connect()
    with tempfile.TemporaryDirectory(prefix="live-risk-sim-") as directory:
        root = Path(directory)
        runtime = RuntimeConfig(
            fill_check_seconds=0.0001,
            freeze_cancel_interval_seconds=0.0001,
            state_path=root / "state.json",
            status_path=root / "status.json",
            audit_path=root / "audit.jsonl",
            log_path=root / "service.log",
        )
        config = AppConfig(
            broker=BrokerConfig(expected_account="DU_TEST", dry_run=False),
            risk=RiskConfig(confirm_samples=2),
            runtime=runtime,
        )
        controller = RiskController(broker, config)
        observations = []
        for pnl in ("-3100", "-3100", "-4100", "-4100", "-5100", "-5100"):
            broker.set_daily_pnl(pnl)
            snapshot = controller.run_once()
            observations.append(
                {
                    "daily_pnl": str(snapshot.daily_pnl),
                    "level": controller.state.level.name,
                    "positions": {
                        position.symbol: str(position.quantity)
                        for position in broker.snapshot().positions
                    },
                }
            )
        print(
            json.dumps(
                {
                    "observations": observations,
                    "cancel_count": broker.cancel_count,
                    "orders": broker.orders,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
