from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from quant.live_risk.config import AppConfig, BrokerConfig, RiskConfig, RuntimeConfig
from quant.live_risk.controller import RiskController
from quant.live_risk.fake import FakeBroker
from quant.live_risk.models import Position, RiskLevel


def stock(symbol: str, contract_id: int, quantity: str) -> Position:
    return Position(
        account="DU_TEST",
        contract_id=contract_id,
        symbol=symbol,
        sec_type="STK",
        currency="USD",
        quantity=Decimal(quantity),
    )


def config(tmp_path, *, dry_run=False, confirm_samples=2) -> AppConfig:
    return AppConfig(
        broker=BrokerConfig(expected_account="DU_TEST", dry_run=dry_run),
        risk=RiskConfig(confirm_samples=confirm_samples),
        runtime=RuntimeConfig(
            fill_check_seconds=0.000001,
            freeze_cancel_interval_seconds=0.000001,
            manual_retry_seconds=0.000001,
            state_path=tmp_path / "state.json",
            status_path=tmp_path / "status.json",
            audit_path=tmp_path / "audit.jsonl",
            log_path=tmp_path / "service.log",
        ),
    )


def observe(controller: RiskController, broker: FakeBroker, pnl: str, count: int = 1):
    for _ in range(count):
        broker.set_daily_pnl(pnl)
        controller.run_once()


def test_three_stage_controls_freeze_reduce_then_liquidate(tmp_path):
    broker = FakeBroker(
        positions=(stock("AAPL", 1, "100"), stock("MRNA", 2, "900"), stock("SHORT", 3, "-50"))
    )
    broker.connect()
    controller = RiskController(broker, config(tmp_path))

    observe(controller, broker, "-3100", 2)
    assert controller.state.level == RiskLevel.FREEZE
    assert broker.orders == []
    assert broker.cancel_count >= 1

    observe(controller, broker, "-4100", 2)
    assert controller.state.level == RiskLevel.REDUCE
    quantities = {position.symbol: position.quantity for position in broker.snapshot().positions}
    assert quantities == {
        "AAPL": Decimal("50.0"),
        "MRNA": Decimal("450.0"),
        "SHORT": Decimal("-25.0"),
    }

    observe(controller, broker, "-5100", 2)
    assert controller.state.level == RiskLevel.LIQUIDATE
    assert all(position.quantity == 0 for position in broker.snapshot().positions)
    assert {order["side"] for order in broker.orders} == {"BUY", "SELL"}


def test_level_is_monotonic_and_restart_does_not_repeat_reduction(tmp_path):
    broker = FakeBroker(positions=(stock("AAPL", 1, "100"),))
    broker.connect()
    app_config = config(tmp_path)
    controller = RiskController(broker, app_config)
    observe(controller, broker, "-4100", 2)
    assert controller.state.level == RiskLevel.REDUCE
    assert broker.snapshot().positions[0].quantity == Decimal("50.0")
    order_count = len(broker.orders)

    restarted = RiskController(broker, app_config)
    observe(restarted, broker, "-1000", 1)
    assert restarted.state.level == RiskLevel.REDUCE
    assert len(broker.orders) == order_count


def test_liquidation_reconciles_partial_fills_until_flat(tmp_path):
    broker = FakeBroker(
        positions=(stock("AAPL", 1, "100"),),
        partial_fill_ratio=Decimal("0.5"),
    )
    broker.connect()
    controller = RiskController(broker, config(tmp_path, confirm_samples=1))
    observe(controller, broker, "-5100")
    assert broker.snapshot().positions[0].quantity == Decimal("50.0")

    for _ in range(10):
        controller.state.last_submit_at = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        controller.run_once()
    assert broker.snapshot().positions[0].quantity < Decimal("0.1")
    assert len(broker.orders) > 1


def test_new_position_after_liquidation_is_closed(tmp_path):
    broker = FakeBroker(positions=(stock("AAPL", 1, "10"),))
    broker.connect()
    controller = RiskController(broker, config(tmp_path, confirm_samples=1))
    observe(controller, broker, "-5100")
    assert broker.snapshot().positions[0].quantity == 0

    broker.positions["2"] = stock("MRNA", 2, "20")
    controller.state.last_submit_at = None
    controller.run_once()
    assert broker.positions["2"].quantity == 0


def test_stale_pnl_cancels_orders_but_does_not_guess_liquidation(tmp_path):
    broker = FakeBroker(positions=(stock("AAPL", 1, "100"),))
    broker.connect()
    broker.set_daily_pnl("-9000")
    broker.pnl_updated_at = datetime.now(UTC) - timedelta(minutes=1)
    controller = RiskController(broker, config(tmp_path, confirm_samples=1))
    controller.run_once()
    assert controller.state.level == RiskLevel.NORMAL
    assert broker.cancel_count == 1
    assert broker.orders == []


def test_dry_run_never_mutates_broker(tmp_path):
    broker = FakeBroker(positions=(stock("AAPL", 1, "100"),))
    broker.connect()
    controller = RiskController(broker, config(tmp_path, dry_run=True, confirm_samples=1))
    observe(controller, broker, "-5100")
    assert controller.state.level == RiskLevel.LIQUIDATE
    assert broker.cancel_count == 0
    assert broker.orders == []
    assert broker.snapshot().positions[0].quantity == 100


def test_execution_requires_exact_paper_account_and_live_ack(monkeypatch):
    with pytest.raises(ValueError, match="DU paper account"):
        BrokerConfig(
            expected_account="U_LIVE",
            environment="paper",
            dry_run=False,
        ).validate()

    with pytest.raises(ValueError, match="allow_live_trading"):
        BrokerConfig(
            expected_account="U_LIVE",
            environment="live",
            dry_run=False,
        ).validate()

    monkeypatch.setenv("IBKR_LIVE_TRADING_ACK", "ALLOW:WRONG")
    with pytest.raises(ValueError, match="IBKR_LIVE_TRADING_ACK"):
        BrokerConfig(
            expected_account="U_LIVE",
            environment="live",
            dry_run=False,
            allow_live_trading=True,
        ).validate()


def test_start_nav_is_inferred_from_net_liq_and_daily_pnl(tmp_path):
    broker = FakeBroker(start_nav=Decimal("100000"))
    broker.connect()
    controller = RiskController(broker, config(tmp_path, confirm_samples=1))
    observe(controller, broker, "-3000")
    assert controller.state.start_nav == "100000"
    assert controller.state.last_loss_fraction == pytest.approx(-0.03)
