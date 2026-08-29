from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
import plistlib
import sys
import types

import pytest

from quant.live_risk.config import AppConfig, BrokerConfig, RiskConfig, RuntimeConfig, load_config
from quant.live_risk.controller import RiskController
from quant.live_risk.fake import FakeBroker
from quant.live_risk.models import Position, RiskLevel
from quant.live_risk.launchd import render_launchd_plist
from quant.live_risk.preflight import preflight_report
from quant.live_risk.tws import TwsBroker


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


def test_service_failure_is_published_without_a_broker_snapshot(tmp_path, monkeypatch):
    from quant.live_risk import main as service

    class FailingBroker:
        def __init__(self, broker_config):
            self.config = broker_config

        def is_connected(self):
            return False

        def connect(self):
            raise ConnectionError("TWS unavailable")

        def disconnect(self):
            return None

    monkeypatch.setattr(service, "TwsBroker", FailingBroker)
    result = service.run(config(tmp_path, dry_run=True), once=True)
    payload = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))

    assert result == 1
    assert payload["schema_version"] == 1
    assert payload["artifact_type"] == "live_risk_status"
    assert payload["healthy"] is False
    assert payload["account"] == "DU_TEST"
    assert "TWS unavailable" in payload["message"]


def test_launchd_plist_keeps_night_guard_alive_without_installing_it(tmp_path):
    root = Path(__file__).resolve().parents[1]
    paper_config = tmp_path / "live_risk.paper.yaml"
    paper_config.write_text("broker: {}\n", encoding="utf-8")
    payload = plistlib.loads(
        render_launchd_plist(root, paper_config, python_path=sys.executable)
    )

    assert payload["RunAtLoad"] is True
    assert payload["KeepAlive"] is True
    assert payload["WorkingDirectory"] == str(root)
    assert payload["ProgramArguments"][:3] == ["/usr/bin/caffeinate", "-im", sys.executable]
    assert str(root / "scripts" / "run_live_risk.py") in payload["ProgramArguments"]
    assert "launchctl" not in " ".join(payload["ProgramArguments"])


def test_tws_broker_submits_only_monotonic_close_orders(monkeypatch):
    installed = _install_fake_ibapi(monkeypatch)
    broker = TwsBroker(BrokerConfig(expected_account="DU_TEST", dry_run=False))
    broker.connect()
    long_position = broker.snapshot().positions[0]

    first_id = broker.submit_close(long_position, Decimal("4"), "risk-test-long")
    first_order = installed["client"].placed_orders[-1][2]
    assert first_id == 10
    assert first_order.account == "DU_TEST"
    assert first_order.action == "SELL"
    assert first_order.orderType == "MKT"
    assert first_order.totalQuantity == Decimal("4")
    assert first_order.tif == "DAY"
    assert first_order.outsideRth is False
    assert first_order.transmit is True

    broker._app.orderStatus(50, "Submitted", 0, 4, 0, 0, 0, 0, 71, "", 0)
    short_position = stock("SHORT", 2, "-5")
    second_id = broker.submit_close(short_position, Decimal("5"), "risk-test-short")
    assert second_id == 51
    assert installed["client"].placed_orders[-1][2].action == "BUY"

    with pytest.raises(ValueError, match="cannot exceed"):
        broker.submit_close(long_position, Decimal("11"), "risk-too-large")
    with pytest.raises(ValueError, match="risk- order_ref"):
        broker.submit_close(long_position, Decimal("1"), "manual-order")

    broker._app.error(-1, 1101, "data lost")
    assert broker.is_connected() is False
    broker._app.error(-1, 1102, "data maintained")
    assert broker.is_connected() is True
    broker._app.connectionClosed()
    assert broker.is_connected() is False
    broker.disconnect()


def test_preflight_is_read_only_and_requires_paper_dependencies(tmp_path):
    app_config = config(tmp_path, dry_run=True)
    missing = preflight_report(app_config, ibapi_available=False)
    ready = preflight_report(app_config, ibapi_available=True)

    assert missing["artifact_type"] == "live_risk_preflight"
    assert missing["ready"] is False
    assert {check["name"] for check in missing["checks"] if not check["passed"]} == {
        "official_ibapi_installed"
    }
    assert ready["ready"] is True
    assert ready["execution_mode"] == "DRY_RUN"


def test_relative_config_resolves_runtime_paths_from_project_root(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    path = config_dir / "paper.yaml"
    path.write_text(
        "broker:\n  expected_account: DU_TEST\n"
        "runtime:\n  state_path: var/live_risk/state.json\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    loaded = load_config("config/paper.yaml")

    assert loaded.runtime.state_path == tmp_path / "var" / "live_risk" / "state.json"
    assert loaded.runtime.state_path.is_absolute()


def _install_fake_ibapi(monkeypatch):
    package = types.ModuleType("ibapi")
    client_module = types.ModuleType("ibapi.client")
    wrapper_module = types.ModuleType("ibapi.wrapper")
    contract_module = types.ModuleType("ibapi.contract")
    order_module = types.ModuleType("ibapi.order")
    installed = {}

    class EWrapper:
        pass

    class EClient:
        def __init__(self, wrapper):
            self.wrapper = wrapper
            self.connected = False
            self.placed_orders = []
            self.global_cancel_count = 0
            installed["client"] = self

        def connect(self, host, port, clientId):
            self.connected = True
            self.wrapper.nextValidId(10)
            self.wrapper.managedAccounts("DU_TEST")

        def run(self):
            return None

        def isConnected(self):
            return self.connected

        def disconnect(self):
            self.connected = False

        def reqAccountSummary(self, req_id, group, tags):
            self.wrapper.accountSummary(req_id, "DU_TEST", "NetLiquidation", "100000", "USD")
            self.wrapper.accountSummaryEnd(req_id)

        def reqPnL(self, req_id, account, model_code):
            self.wrapper.pnl(req_id, -100.0, -100.0, 0.0)

        def reqPositions(self):
            contract = types.SimpleNamespace(
                conId=1,
                symbol="AAPL",
                secType="STK",
                currency="USD",
                exchange="SMART",
                primaryExchange="NASDAQ",
            )
            self.wrapper.position("DU_TEST", contract, Decimal("10"), 100.0)
            self.wrapper.positionEnd()

        def cancelPnL(self, request_id):
            return None

        def cancelAccountSummary(self, request_id):
            return None

        def cancelPositions(self):
            return None

        def reqGlobalCancel(self):
            self.global_cancel_count += 1

        def placeOrder(self, order_id, contract, order):
            self.placed_orders.append((order_id, contract, order))

    class Contract:
        pass

    class Order:
        pass

    client_module.EClient = EClient
    wrapper_module.EWrapper = EWrapper
    contract_module.Contract = Contract
    order_module.Order = Order
    for name, module in {
        "ibapi": package,
        "ibapi.client": client_module,
        "ibapi.wrapper": wrapper_module,
        "ibapi.contract": contract_module,
        "ibapi.order": order_module,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    return installed
