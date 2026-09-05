"""Thin synchronous facade over the official event-driven IBKR TWS API."""

from __future__ import annotations

import math
import threading
from datetime import UTC, datetime
from decimal import Decimal

from .config import BrokerConfig
from .models import AccountSnapshot, Position


class TwsBroker:
    """Read account/P&L continuously and submit close-only stock orders."""

    ACCOUNT_SUMMARY_REQUEST = 9101
    PNL_REQUEST = 9102

    def __init__(self, config: BrokerConfig):
        self.config = config
        self.config.validate()
        self._app = None
        self._thread: threading.Thread | None = None
        self._next_order_id: int | None = None
        self._order_id_lock = threading.Lock()
        self._data_lock = threading.Lock()
        self._error_lock = threading.Lock()
        self._orders_lock = threading.Lock()
        self._connected_event = threading.Event()
        self._accounts_event = threading.Event()
        self._summary_event = threading.Event()
        self._pnl_event = threading.Event()
        self._positions_event = threading.Event()
        self._managed_accounts: tuple[str, ...] = ()
        self._account = ""
        self._account_values: dict[str, Decimal] = {}
        self._daily_pnl: Decimal | None = None
        self._pnl_updated_at: datetime | None = None
        self._positions: dict[str, Position] = {}
        self._server_connected = False
        self.errors: list[tuple[int, int, str]] = []
        self.order_statuses: dict[int, dict] = {}
        self.open_orders: dict[int, dict] = {}

    def connect(self) -> None:
        if self.is_connected():
            return
        self._reset_connection_state()
        app = self._build_app()
        self._app = app
        app.connect(self.config.host, self.config.port, clientId=self.config.client_id)
        self._thread = threading.Thread(target=app.run, name="ibkr-tws-api", daemon=True)
        self._thread.start()
        timeout = self.config.connect_timeout_seconds
        if not self._connected_event.wait(timeout):
            self.disconnect()
            raise TimeoutError("TWS API did not provide nextValidId")
        if not self._accounts_event.wait(timeout):
            self.disconnect()
            raise TimeoutError("TWS API did not provide managed accounts")

        self._account = self._resolve_account()
        app.reqAccountSummary(
            self.ACCOUNT_SUMMARY_REQUEST,
            "All",
            "NetLiquidation,ExcessLiquidity,AvailableFunds",
        )
        app.reqPnL(self.PNL_REQUEST, self._account, "")
        app.reqPositions()
        if not self._summary_event.wait(timeout):
            self.disconnect()
            raise TimeoutError("TWS API account summary timed out")
        if not self._positions_event.wait(timeout):
            self.disconnect()
            raise TimeoutError("TWS API positions timed out")
        if not self._pnl_event.wait(timeout):
            self.disconnect()
            raise TimeoutError(
                "TWS API Daily P&L timed out; enable 'Prepare portfolio P&L data when downloading positions'"
            )

    def disconnect(self) -> None:
        app = self._app
        if app is not None:
            try:
                app.cancelPnL(self.PNL_REQUEST)
                app.cancelAccountSummary(self.ACCOUNT_SUMMARY_REQUEST)
                app.cancelPositions()
            except Exception:
                pass
            try:
                app.disconnect()
            except Exception:
                pass
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self._server_connected = False
        self._app = None
        self._thread = None

    def is_connected(self) -> bool:
        app = self._app
        return bool(app is not None and app.isConnected() and self._server_connected)

    def snapshot(self) -> AccountSnapshot:
        if not self.is_connected():
            raise RuntimeError("TWS API is disconnected")
        with self._data_lock:
            net_liquidation = self._account_values.get("NetLiquidation")
            if net_liquidation is None or self._daily_pnl is None or self._pnl_updated_at is None:
                raise RuntimeError("TWS account data is incomplete")
            return AccountSnapshot(
                account=self._account,
                as_of=datetime.now(UTC),
                pnl_updated_at=self._pnl_updated_at,
                net_liquidation=net_liquidation,
                daily_pnl=self._daily_pnl,
                positions=tuple(self._positions.values()),
                excess_liquidity=self._account_values.get("ExcessLiquidity"),
                available_funds=self._account_values.get("AvailableFunds"),
            )

    def cancel_all_orders(self) -> None:
        self._require_connection()
        from ibapi.order_cancel import OrderCancel

        self._app.reqGlobalCancel(OrderCancel())

    def pop_errors(self) -> list[tuple[int, int, str]]:
        with self._error_lock:
            result = list(self.errors)
            self.errors.clear()
        return result

    def submit_close(
        self,
        position: Position,
        quantity: Decimal,
        order_ref: str,
    ) -> int:
        self._require_connection()
        if quantity <= 0:
            raise ValueError("close quantity must be positive")
        if position.account != self._account:
            raise RuntimeError("position account does not match connected account")
        if position.sec_type != "STK":
            raise ValueError("phase one only submits close orders for stocks")
        if quantity > abs(position.quantity):
            raise ValueError("close quantity cannot exceed the current position")
        if not order_ref.startswith("risk-"):
            raise ValueError("close-only broker requires a risk- order_ref")

        from ibapi.contract import Contract
        from ibapi.order import Order

        contract = Contract()
        contract.conId = position.contract_id
        contract.symbol = position.symbol
        contract.secType = position.sec_type
        contract.currency = position.currency
        contract.exchange = position.exchange or "SMART"
        if position.primary_exchange:
            contract.primaryExchange = position.primary_exchange

        order = Order()
        order.account = self._account
        order.action = "SELL" if position.quantity > 0 else "BUY"
        order.orderType = self.config.order_type
        order.totalQuantity = quantity
        order.tif = self.config.time_in_force
        order.outsideRth = self.config.outside_rth
        order.orderRef = order_ref
        order.transmit = True

        order_id = self._take_order_id()
        self._app.placeOrder(order_id, contract, order)
        return order_id

    def _require_connection(self) -> None:
        if not self.is_connected():
            raise RuntimeError("TWS API is disconnected")

    def _reset_connection_state(self) -> None:
        self._connected_event.clear()
        self._accounts_event.clear()
        self._summary_event.clear()
        self._pnl_event.clear()
        self._positions_event.clear()
        self._managed_accounts = ()
        self._account = ""
        self._next_order_id = None
        self._server_connected = False
        with self._orders_lock:
            self.order_statuses = {}
            self.open_orders = {}
        with self._data_lock:
            self._account_values = {}
            self._daily_pnl = None
            self._pnl_updated_at = None
            self._positions = {}

    def _resolve_account(self) -> str:
        expected = self.config.expected_account
        if expected:
            if expected not in self._managed_accounts:
                raise RuntimeError(
                    f"expected account {expected!r} not in TWS accounts {self._managed_accounts!r}"
                )
            return expected
        if len(self._managed_accounts) != 1:
            raise RuntimeError("expected_account is required when TWS exposes multiple accounts")
        return self._managed_accounts[0]

    def _take_order_id(self) -> int:
        with self._order_id_lock:
            if self._next_order_id is None:
                raise RuntimeError("TWS has not supplied an order id")
            value = self._next_order_id
            self._next_order_id += 1
            return value

    def _build_app(self):
        try:
            from ibapi.client import EClient
            from ibapi.wrapper import EWrapper
        except ImportError as exc:
            raise RuntimeError(
                "official IBKR TWS API package 'ibapi' is not installed; install it from the IBKR TWS API download"
            ) from exc

        owner = self

        class App(EWrapper, EClient):
            def __init__(self):
                EClient.__init__(self, self)

            def nextValidId(self, orderId):
                owner._advance_order_id(int(orderId))
                owner._server_connected = True
                owner._connected_event.set()

            def managedAccounts(self, accountsList):
                accounts = tuple(item.strip() for item in accountsList.split(",") if item.strip())
                owner._managed_accounts = accounts
                owner._accounts_event.set()

            def accountSummary(self, reqId, account, tag, value, currency):
                selected = owner.config.expected_account or (
                    owner._managed_accounts[0] if len(owner._managed_accounts) == 1 else ""
                )
                if selected and account != selected:
                    return
                try:
                    parsed = Decimal(value)
                except Exception:
                    return
                with owner._data_lock:
                    owner._account_values[tag] = parsed

            def accountSummaryEnd(self, reqId):
                if reqId == owner.ACCOUNT_SUMMARY_REQUEST:
                    owner._summary_event.set()

            def pnl(self, reqId, dailyPnL, unrealizedPnL, realizedPnL):
                if reqId != owner.PNL_REQUEST or not math.isfinite(dailyPnL):
                    return
                with owner._data_lock:
                    owner._daily_pnl = Decimal(str(dailyPnL))
                    owner._pnl_updated_at = datetime.now(UTC)
                owner._pnl_event.set()

            def position(self, account, contract, pos, avgCost):
                if owner._account and account != owner._account:
                    return
                position = Position(
                    account=account,
                    contract_id=int(contract.conId),
                    symbol=contract.symbol,
                    sec_type=contract.secType,
                    currency=contract.currency,
                    quantity=Decimal(str(pos)),
                    exchange=contract.exchange or "SMART",
                    primary_exchange=getattr(contract, "primaryExchange", "") or "",
                )
                with owner._data_lock:
                    if position.quantity == 0:
                        owner._positions.pop(position.key, None)
                    else:
                        owner._positions[position.key] = position

            def positionEnd(self):
                owner._positions_event.set()

            def openOrder(self, orderId, contract, order, orderState):
                order_id = int(orderId)
                owner._advance_order_id(order_id + 1)
                with owner._orders_lock:
                    owner.open_orders[order_id] = {
                        "contract_id": int(getattr(contract, "conId", 0)),
                        "symbol": str(getattr(contract, "symbol", "")),
                        "action": str(getattr(order, "action", "")),
                        "quantity": str(getattr(order, "totalQuantity", "")),
                        "order_type": str(getattr(order, "orderType", "")),
                        "order_ref": str(getattr(order, "orderRef", "")),
                        "status": str(getattr(orderState, "status", "")),
                    }

            def orderStatus(
                self,
                orderId,
                status,
                filled,
                remaining,
                avgFillPrice,
                permId,
                parentId,
                lastFillPrice,
                clientId,
                whyHeld,
                mktCapPrice,
            ):
                order_id = int(orderId)
                owner._advance_order_id(order_id + 1)
                with owner._orders_lock:
                    owner.order_statuses[order_id] = {
                        "status": status,
                        "filled": str(filled),
                        "remaining": str(remaining),
                        "avg_fill_price": avgFillPrice,
                        "updated_at": datetime.now(UTC).isoformat(),
                    }
                    if str(status) in {"Cancelled", "ApiCancelled", "Filled", "Inactive"}:
                        owner.open_orders.pop(order_id, None)

            def connectionClosed(self):
                owner._server_connected = False

            def error(self, reqId, *args):
                # TWS API 10.50 added errorTime before errorCode. Accept both
                # callback layouts so the broker also remains compatible with
                # older TWS API clients.
                if len(args) == 4:
                    _error_time, errorCode, errorString, _advanced_reject = args
                elif len(args) in {2, 3}:
                    errorCode, errorString = args[:2]
                else:
                    raise TypeError(f"unexpected TWS error callback arguments: {args!r}")
                with owner._error_lock:
                    owner.errors.append((int(reqId), int(errorCode), str(errorString)))
                if errorCode in {1100, 1101, 1300}:
                    # 1101 means subscriptions were lost; force the service loop to
                    # reconnect and recreate every account/P&L/position subscription.
                    owner._server_connected = False
                elif errorCode == 1102:
                    owner._server_connected = True

        return App()

    def _advance_order_id(self, candidate: int) -> None:
        with self._order_id_lock:
            if self._next_order_id is None or candidate > self._next_order_id:
                self._next_order_id = candidate
