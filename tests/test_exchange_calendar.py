from datetime import date

import pytest

from quant.exchange_calendar import calendar_id, coverage, is_trading_date, session_close


def test_pinned_market_calendar_holidays_and_early_close():
    assert calendar_id("us") == "exchange_calendars:4.13.2:XNYS"
    assert calendar_id("cn") == "exchange_calendars:4.13.2:XSHG+XSHE"
    assert not is_trading_date("us", date(2026, 7, 3))
    assert is_trading_date("us", date(2026, 7, 6))
    assert session_close("us", date(2026, 11, 27)).hour == 18  # 13:00 New York / 18:00 UTC
    assert not is_trading_date("cn", date(2026, 2, 23))
    assert is_trading_date("cn", date(2026, 2, 24))


def test_calendar_exposes_and_enforces_coverage():
    first, last = coverage("cn")
    assert first <= date(2026, 1, 1) <= last
    with pytest.raises(ValueError, match="outside the pinned"):
        is_trading_date("cn", date(2030, 1, 2))


def test_calendar_rejects_provider_version_drift(monkeypatch):
    monkeypatch.setattr("quant.exchange_calendar.version", lambda _: "4.13.1")
    with pytest.raises(RuntimeError, match="version mismatch"):
        calendar_id("us")
