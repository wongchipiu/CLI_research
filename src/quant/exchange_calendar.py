"""Pinned exchange-calendar boundary used by executable paper signals."""

from __future__ import annotations

from datetime import date, datetime
from importlib.metadata import version

import exchange_calendars as xcals
from exchange_calendars.errors import DateOutOfBounds


EXPECTED_PROVIDER_VERSION = "4.13.2"
PROVIDER = "exchange_calendars"
MARKET_CALENDARS = {
    "us": ("XNYS", "XNYS"),
    "cn": ("XSHG", "XSHG+XSHE"),
}


def calendar_id(market: str) -> str:
    provider_name, contract_name = _calendar_names(market)
    _verify_provider_version()
    return f"{PROVIDER}:{EXPECTED_PROVIDER_VERSION}:{contract_name}"


def is_trading_date(market: str, value: date) -> bool:
    calendar = _calendar(market)
    try:
        return bool(calendar.is_session(value.isoformat()))
    except DateOutOfBounds as exc:
        raise ValueError(f"date is outside the pinned {market} calendar coverage: {value}") from exc


def session_close(market: str, value: date) -> datetime:
    calendar = _calendar(market)
    try:
        close = calendar.session_close(value.isoformat())
    except DateOutOfBounds as exc:
        raise ValueError(f"date is outside the pinned {market} calendar coverage: {value}") from exc
    return close.to_pydatetime()


def coverage(market: str) -> tuple[date, date]:
    calendar = _calendar(market)
    return calendar.first_session.date(), calendar.last_session.date()


def _calendar(market: str):
    provider_name, _ = _calendar_names(market)
    _verify_provider_version()
    return xcals.get_calendar(provider_name)


def _calendar_names(market: str) -> tuple[str, str]:
    try:
        return MARKET_CALENDARS[market]
    except KeyError as exc:
        raise ValueError(f"unsupported exchange calendar market: {market}") from exc


def _verify_provider_version() -> None:
    installed = version("exchange-calendars")
    if installed != EXPECTED_PROVIDER_VERSION:
        raise RuntimeError(
            f"exchange calendar version mismatch: expected {EXPECTED_PROVIDER_VERSION}, got {installed}"
        )
