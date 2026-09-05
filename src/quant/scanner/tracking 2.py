"""Persist radar signals and mature point-in-time forward outcomes."""

from __future__ import annotations

from datetime import datetime, time, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

import pandas as pd

from quant.contracts import validate_daily_radar_scan, validate_daily_radar_tracking
from quant.data import storage
from quant.scanner.config import TrackingConfig

FrameLoader = Callable[[str, str], pd.DataFrame | None]


class TrackingError(ValueError):
    """Raised when signals cannot be tracked without inventing market data."""


def track_daily_radar(
    scans: Iterable[dict],
    config: TrackingConfig,
    *,
    existing: dict | None = None,
    loader: FrameLoader = storage.load_daily,
) -> dict:
    scan_list = [validate_daily_radar_scan(scan) for scan in scans]
    if not scan_list:
        raise TrackingError("no daily_radar_scan artifacts supplied")
    profiles = {scan["profile"] for scan in scan_list}
    if len(profiles) != 1:
        raise TrackingError("tracking input must contain exactly one radar profile")
    profile = next(iter(profiles))

    registered: dict[str, dict] = {}
    if existing is not None:
        validate_daily_radar_tracking(existing)
        if existing["profile"] != profile:
            raise TrackingError("existing tracking profile does not match scan profile")
        for signal in existing["signals"]:
            registered[signal["signal_id"]] = _immutable_signal(signal)

    for scan in scan_list:
        for candidate in scan["candidates"]:
            signal = {
                "signal_id": candidate["signal_id"],
                "profile": scan["profile"],
                "symbol": candidate["symbol"],
                "signal_date": candidate["signal_date"],
                "registered_at": candidate["generated_at"],
                "available_at": candidate["available_at"],
                "scoring_version": scan["scoring_version"],
                "source_snapshot_sha256": scan["data_snapshot"]["sha256"],
                "score": candidate["score"],
                "features": candidate["features"],
            }
            current = registered.get(signal["signal_id"])
            if current is not None and current != signal:
                raise TrackingError(f"conflicting payload for signal_id {signal['signal_id']}")
            registered[signal["signal_id"]] = signal

    benchmark_frame = loader("us", config.benchmark)
    benchmark = _normalize_bars(benchmark_frame, config.benchmark)
    if benchmark.empty:
        raise TrackingError(f"no local benchmark data for {config.benchmark}")
    sessions = pd.DatetimeIndex(benchmark.index).sort_values().unique()
    latest_market_date = str(pd.Timestamp(sessions[-1]).date())

    symbol_frames: dict[str, pd.DataFrame] = {}
    for symbol in sorted({signal["symbol"] for signal in registered.values()}):
        frame = loader("us", symbol)
        symbol_frames[symbol] = _normalize_bars(frame, symbol)

    signals = []
    for signal in sorted(
        registered.values(), key=lambda item: (item["signal_date"], item["symbol"], item["signal_id"])
    ):
        tracked = dict(signal)
        tracked["outcomes"] = _track_signal(
            signal,
            symbol_frames[signal["symbol"]],
            benchmark,
            sessions,
            config,
        )
        signals.append(tracked)

    summary = _summarize(signals, config.horizons)
    artifact = {
        "schema_version": 1,
        "artifact_type": "daily_radar_tracking",
        "market": "us",
        "profile": profile,
        "benchmark": config.benchmark,
        "horizons": list(config.horizons),
        "buy_fee": config.buy_fee,
        "sell_fee": config.sell_fee,
        "delistings": dict(config.delistings),
        "latest_market_date": latest_market_date,
        "generated_at": _us_close_timestamp(latest_market_date),
        "timestamp_basis": "latest_loaded_benchmark_regular_close_not_fetch_time",
        "tracking_snapshot": _tracking_snapshot(
            latest_market_date, benchmark, symbol_frames
        ),
        "summary": summary,
        "signals": signals,
    }
    return validate_daily_radar_tracking(artifact)


def write_tracking_artifact(artifact: dict, path: str | Path) -> Path:
    validate_daily_radar_tracking(artifact)
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(artifact, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(output)
    return output


def _immutable_signal(signal: dict) -> dict:
    return {
        key: signal[key]
        for key in (
            "signal_id",
            "profile",
            "symbol",
            "signal_date",
            "registered_at",
            "available_at",
            "scoring_version",
            "source_snapshot_sha256",
            "score",
            "features",
        )
    }


def _track_signal(
    signal: dict,
    symbol: pd.DataFrame,
    benchmark: pd.DataFrame,
    sessions: pd.DatetimeIndex,
    config: TrackingConfig,
) -> dict:
    signal_date = pd.Timestamp(signal["signal_date"]).normalize()
    future = sessions[sessions > signal_date]
    outcomes = {}
    for horizon in config.horizons:
        key = str(horizon)
        if len(future) < horizon:
            outcomes[key] = {
                "status": "PENDING",
                "required_sessions": horizon,
                "observed_sessions": len(future),
                "target_session": None,
                "descriptive": None,
                "executable": None,
            }
            continue
        entry_date = pd.Timestamp(future[0])
        target_date = pd.Timestamp(future[horizon - 1])
        delisting_date = dict(config.delistings).get(signal["symbol"])
        if delisting_date and target_date > pd.Timestamp(delisting_date):
            outcomes[key] = {
                "status": "DELISTED",
                "required_sessions": horizon,
                "observed_sessions": horizon,
                "target_session": str(target_date.date()),
                "final_trading_date": delisting_date,
                "descriptive": None,
                "executable": None,
            }
            continue
        descriptive = _descriptive_outcome(signal, symbol, benchmark, signal_date, target_date)
        executable = _executable_outcome(
            symbol, benchmark, entry_date, target_date, config
        )
        status = (
            "MATURED"
            if descriptive.get("status") == "OK" and executable.get("status") == "OK"
            else "MISSING"
        )
        outcomes[key] = {
            "status": status,
            "required_sessions": horizon,
            "observed_sessions": horizon,
            "target_session": str(target_date.date()),
            "descriptive": descriptive,
            "executable": executable,
        }
    return outcomes


def _descriptive_outcome(
    signal: dict,
    symbol: pd.DataFrame,
    benchmark: pd.DataFrame,
    signal_date: pd.Timestamp,
    target_date: pd.Timestamp,
) -> dict:
    reference_close = _positive_number(signal.get("features", {}).get("close"))
    symbol_exit = _bar_value(symbol, target_date, "close")
    benchmark_start = _bar_value(benchmark, signal_date, "close")
    benchmark_exit = _bar_value(benchmark, target_date, "close")
    missing = []
    if reference_close is None:
        missing.append("missing_signal_reference_close")
    if symbol_exit is None:
        missing.append("missing_symbol_exit_close")
    if benchmark_start is None:
        missing.append("missing_benchmark_signal_close")
    if benchmark_exit is None:
        missing.append("missing_benchmark_exit_close")
    if missing:
        return {"status": "MISSING", "reasons": missing}
    symbol_return = symbol_exit / reference_close - 1.0
    benchmark_return = benchmark_exit / benchmark_start - 1.0
    return {
        "status": "OK",
        "basis": "signal_close_to_future_close",
        "signal_close": reference_close,
        "exit_close": symbol_exit,
        "return": _round(symbol_return),
        "benchmark_return": _round(benchmark_return),
        "excess_return": _round(symbol_return - benchmark_return),
    }


def _executable_outcome(
    symbol: pd.DataFrame,
    benchmark: pd.DataFrame,
    entry_date: pd.Timestamp,
    target_date: pd.Timestamp,
    config: TrackingConfig,
) -> dict:
    symbol_entry = _bar_value(symbol, entry_date, "open")
    symbol_exit = _bar_value(symbol, target_date, "close")
    benchmark_entry = _bar_value(benchmark, entry_date, "open")
    benchmark_exit = _bar_value(benchmark, target_date, "close")
    missing = []
    if symbol_entry is None:
        missing.append("missing_symbol_entry_open")
    if symbol_exit is None:
        missing.append("missing_symbol_exit_close")
    if benchmark_entry is None:
        missing.append("missing_benchmark_entry_open")
    if benchmark_exit is None:
        missing.append("missing_benchmark_exit_close")
    if missing:
        return {"status": "MISSING", "reasons": missing}
    gross_return = symbol_exit / symbol_entry - 1.0
    net_return = symbol_exit * (1.0 - config.sell_fee) / (
        symbol_entry * (1.0 + config.buy_fee)
    ) - 1.0
    benchmark_net_return = benchmark_exit * (1.0 - config.sell_fee) / (
        benchmark_entry * (1.0 + config.buy_fee)
    ) - 1.0
    return {
        "status": "OK",
        "basis": "next_session_open_to_future_close_after_fees",
        "entry_session": str(entry_date.date()),
        "entry_open": symbol_entry,
        "exit_close": symbol_exit,
        "gross_return": _round(gross_return),
        "net_return": _round(net_return),
        "benchmark_net_return": _round(benchmark_net_return),
        "excess_net_return": _round(net_return - benchmark_net_return),
    }


def _normalize_bars(frame: pd.DataFrame | None, symbol: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["open", "close"])
    missing = {"date", "open", "close"} - set(frame.columns)
    if missing:
        raise TrackingError(f"{symbol} daily data missing columns: {sorted(missing)}")
    work = frame[["date", "open", "close"]].copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.dropna(subset=["date"]).sort_values("date")
    work["date"] = work["date"].map(
        lambda value: pd.Timestamp(value).tz_localize(None).normalize()
    )
    work["open"] = pd.to_numeric(work["open"], errors="coerce")
    work["close"] = pd.to_numeric(work["close"], errors="coerce")
    return work.drop_duplicates(subset="date", keep="last").set_index("date")


def _bar_value(frame: pd.DataFrame, date: pd.Timestamp, column: str) -> float | None:
    if date not in frame.index:
        return None
    value = frame.at[date, column]
    return _positive_number(value)


def _positive_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _summarize(signals: list[dict], horizons: tuple[int, ...]) -> dict:
    by_horizon = {}
    totals = {"MATURED": 0, "PENDING": 0, "MISSING": 0, "DELISTED": 0}
    for horizon in horizons:
        counts = {"matured": 0, "pending": 0, "missing": 0, "delisted": 0}
        for signal in signals:
            status = signal["outcomes"][str(horizon)]["status"]
            counts[status.lower()] += 1
            totals[status] += 1
        by_horizon[str(horizon)] = counts
    return {
        "signals": len(signals),
        "outcomes": sum(totals.values()),
        "matured": totals["MATURED"],
        "pending": totals["PENDING"],
        "missing": totals["MISSING"],
        "delisted": totals["DELISTED"],
        "by_horizon": by_horizon,
    }


def _tracking_snapshot(
    latest_market_date: str,
    benchmark: pd.DataFrame,
    symbols: dict[str, pd.DataFrame],
) -> dict:
    hashes = {"benchmark": _frame_hash(benchmark)}
    hashes.update({symbol: _frame_hash(frame) for symbol, frame in sorted(symbols.items())})
    raw = json.dumps(
        {"latest_market_date": latest_market_date, "frames": hashes},
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "frames": hashes,
    }


def _frame_hash(frame: pd.DataFrame) -> str:
    encoded = frame.reset_index().to_json(
        orient="split", date_format="iso", double_precision=15, default_handler=str
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _us_close_timestamp(market_date: str) -> str:
    local = datetime.combine(
        pd.Timestamp(market_date).date(), time(hour=16), ZoneInfo("America/New_York")
    )
    return local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _round(value: float) -> float:
    if not math.isfinite(value):
        raise TrackingError("non-finite tracking result")
    return round(value, 8)
