"""Command-line service loop for the IBKR risk controller."""

from __future__ import annotations

import argparse
import logging
import time
from logging.handlers import RotatingFileHandler

from .config import AppConfig, load_config
from .controller import RiskController
from .notify import WebhookNotifier
from .state import AuditWriter
from .tws import TwsBroker


def _configure_logging(config: AppConfig) -> logging.Logger:
    path = config.runtime.log_path
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("quant.live_risk")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        file_handler = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=5)
        file_handler.setFormatter(formatter)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
    return logger


def run(config: AppConfig, *, once: bool = False) -> int:
    logger = _configure_logging(config)
    audit = AuditWriter(config.runtime.audit_path)
    notifier = WebhookNotifier(config.runtime.webhook_env_var)
    broker = TwsBroker(config.broker)
    controller = RiskController(broker, config, audit=audit, notifier=notifier)
    logger.info(
        "starting IBKR risk service environment=%s dry_run=%s account=%s",
        config.broker.environment,
        config.broker.dry_run,
        config.broker.expected_account or "auto-detect",
    )
    audit.append(
        "SERVICE_STARTED",
        environment=config.broker.environment,
        dry_run=config.broker.dry_run,
        expected_account=config.broker.expected_account,
    )
    last_status_log = 0.0
    last_level = None
    try:
        while True:
            try:
                if not broker.is_connected():
                    broker.disconnect()
                    broker.connect()
                    logger.info("connected to TWS/IB Gateway")
                    audit.append("BROKER_CONNECTED")
                snapshot = controller.run_once()
                for request_id, code, message in broker.pop_errors():
                    audit.append(
                        "BROKER_MESSAGE",
                        request_id=request_id,
                        code=code,
                        message=message,
                    )
                    if code not in {1102, 2104, 2106, 2107, 2108, 2158}:
                        logger.warning("IBKR message code=%s request=%s: %s", code, request_id, message)
                        notifier.send(
                            "BROKER_MESSAGE",
                            {
                                "account": snapshot.account,
                                "request_id": request_id,
                                "code": code,
                                "message": message,
                            },
                        )
                now = time.monotonic()
                if (
                    once
                    or controller.state.level != last_level
                    or now - last_status_log >= 60
                ):
                    logger.info(
                        "level=%s daily_pnl=%s net_liq=%s positions=%s",
                        controller.state.level.name,
                        snapshot.daily_pnl,
                        snapshot.net_liquidation,
                        len(snapshot.positions),
                    )
                    last_status_log = now
                    last_level = controller.state.level
                if once:
                    return 0
                time.sleep(config.runtime.poll_seconds)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                logger.exception("risk loop failed: %s", exc)
                audit.append("RISK_LOOP_ERROR", error=repr(exc))
                broker.disconnect()
                if once:
                    return 1
                time.sleep(config.runtime.reconnect_seconds)
    except KeyboardInterrupt:
        logger.info("stopping on user request")
        return 0
    finally:
        broker.disconnect()
        audit.append("SERVICE_STOPPED")


def main() -> int:
    parser = argparse.ArgumentParser(description="Paper-first IBKR account risk kill switch")
    parser.add_argument("--config", required=True, help="Path to live-risk YAML configuration")
    parser.add_argument("--once", action="store_true", help="Read and evaluate one snapshot")
    args = parser.parse_args()
    return run(load_config(args.config), once=args.once)


if __name__ == "__main__":
    raise SystemExit(main())
