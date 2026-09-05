"""Deterministic US daily watchlist radar."""

from __future__ import annotations

from datetime import datetime, time, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

import pandas as pd

from quant.contracts import validate_daily_radar_scan
from quant.data import storage
from quant.features import FeatureUnavailable, compute_daily_radar_features
from quant.scanner.config import RadarProfile

FrameLoader = Callable[[str, str], pd.DataFrame | None]
SCORING_VERSION = "us_daily_momentum_volume_v1"


class RadarError(ValueError):
    """Raised when a radar scan cannot produce an auditable artifact."""


def scan_us_daily(
    profile: RadarProfile,
    symbols: Iterable[str],
    *,
    as_of: str | None = None,
    loader: FrameLoader = storage.load_daily,
) -> dict:
    if profile.market != "us":
        raise RadarError("M7-S5 radar only supports market 'us'")
    requested = sorted(
        {str(symbol).upper() for symbol in symbols} - set(profile.exclude_symbols)
    )
    if not requested:
        raise RadarError("radar watchlist is empty after exclusions")

    frames: dict[str, pd.DataFrame] = {}
    for symbol in requested:
        frame = loader("us", symbol)
        if frame is not None and not frame.empty:
            frames[symbol] = frame.copy()
    if not frames:
        raise RadarError(f"no local daily data for radar profile {profile.name}")

    signal_date = _resolve_signal_date(frames, as_of)
    generated_at = _us_close_timestamp(signal_date)
    snapshot = _data_snapshot(requested, frames, signal_date)
    excluded = []
    candidates = []
    feature_count = 0
    base_eligible_count = 0
    unavailable_count = 0

    for symbol in requested:
        frame = frames.get(symbol)
        if frame is None:
            unavailable_count += 1
            excluded.append({"symbol": symbol, "reasons": ["no_data"]})
            continue
        try:
            features = compute_daily_radar_features(
                frame, signal_date, min_history=profile.min_history
            )
        except FeatureUnavailable as exc:
            unavailable_count += 1
            excluded.append({"symbol": symbol, "reasons": [exc.reason]})
            continue
        feature_count += 1
        reasons = []
        if features.close < profile.min_price:
            reasons.append("price_below_minimum")
        if features.average_dollar_volume_20 < profile.min_average_dollar_volume_20:
            reasons.append("liquidity_below_minimum")
        if reasons:
            excluded.append({"symbol": symbol, "reasons": reasons})
            continue
        base_eligible_count += 1
        if features.volume_ratio_20 < profile.min_volume_ratio_20:
            reasons.append("volume_ratio_below_threshold")
        if features.ret_5d < profile.min_ret_5d and not features.breakout_20:
            reasons.append("momentum_or_breakout_not_met")
        if reasons:
            excluded.append({"symbol": symbol, "reasons": reasons})
            continue
        candidates.append(
            {
                "symbol": symbol,
                "score": _score(features.to_dict()),
                "features": _rounded_features(features.to_dict()),
            }
        )

    candidates.sort(key=lambda item: (-item["score"], item["symbol"]))
    total_candidates = len(candidates)
    visible = candidates[: profile.max_results]
    for rank, item in enumerate(visible, start=1):
        item["rank"] = rank
        item["signal_date"] = signal_date
        item["generated_at"] = generated_at
        item["available_at"] = generated_at
        item["signal_id"] = _signal_id(
            profile.name, item["symbol"], signal_date, snapshot["sha256"]
        )
    excluded.sort(key=lambda item: item["symbol"])
    status = "DEGRADED" if unavailable_count else "OK"
    artifact = {
        "schema_version": 1,
        "artifact_type": "daily_radar_scan",
        "market": "us",
        "profile": profile.name,
        "status": status,
        "signal_date": signal_date,
        "generated_at": generated_at,
        "available_at": generated_at,
        "timestamp_basis": "scheduled_us_regular_close_not_fetch_time",
        "scoring_version": SCORING_VERSION,
        "rules": {
            "breakout_basis": "close_above_prior_valid_session_closes",
            "volume_baseline": "prior_20_valid_sessions_excluding_signal_date",
            "score_formula": (
                "40*clip(volume_ratio_20/5,0,1) + 30*clip(ret_5d/0.20,-1,1) + "
                "15*clip(ret_20d/0.40,-1,1) + 5*breakout_20 + 10*breakout_60"
            ),
            "universe_profile": profile.universe_profile,
            "min_history": profile.min_history,
            "min_price": profile.min_price,
            "min_average_dollar_volume_20": profile.min_average_dollar_volume_20,
            "min_volume_ratio_20": profile.min_volume_ratio_20,
            "min_ret_5d": profile.min_ret_5d,
            "max_results": profile.max_results,
        },
        "data_snapshot": snapshot,
        "summary": {
            "requested": len(requested),
            "loaded": len(frames),
            "features_computed": feature_count,
            "base_eligible": base_eligible_count,
            "candidates_total": total_candidates,
            "candidates_returned": len(visible),
            "excluded": len(excluded),
        },
        "candidates": visible,
        "excluded": excluded,
    }
    return validate_daily_radar_scan(artifact)


def write_scan_artifact(artifact: dict, path: str | Path) -> Path:
    validate_daily_radar_scan(artifact)
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(artifact, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(output)
    return output


def _resolve_signal_date(frames: dict[str, pd.DataFrame], as_of: str | None) -> str:
    if as_of:
        try:
            return str(pd.Timestamp(as_of).normalize().date())
        except (TypeError, ValueError):
            raise RadarError(f"invalid as-of date: {as_of}") from None
    latest = []
    for frame in frames.values():
        if "date" in frame.columns:
            dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
            if not dates.empty:
                latest.append(pd.Timestamp(dates.max()).tz_localize(None).normalize())
    if not latest:
        raise RadarError("loaded radar data has no valid dates")
    return str(max(latest).date())


def _us_close_timestamp(signal_date: str) -> str:
    local = datetime.combine(
        pd.Timestamp(signal_date).date(), time(hour=16), ZoneInfo("America/New_York")
    )
    return local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _data_snapshot(
    requested: list[str], frames: dict[str, pd.DataFrame], signal_date: str
) -> dict:
    symbols = {}
    target = pd.Timestamp(signal_date).normalize()
    for symbol in requested:
        frame = frames.get(symbol)
        if frame is None:
            symbols[symbol] = None
            continue
        work = frame.copy()
        if "date" in work.columns:
            dates = pd.to_datetime(work["date"], errors="coerce")
            work = work.loc[dates <= target]
        work = work.reindex(sorted(work.columns), axis=1).reset_index(drop=True)
        encoded = work.to_json(
            orient="split", date_format="iso", double_precision=15, default_handler=str
        )
        symbols[symbol] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    canonical = json.dumps(
        {"signal_date": signal_date, "symbols": symbols}, sort_keys=True, separators=(",", ":")
    )
    return {
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "symbols": symbols,
    }


def _score(features: dict) -> float:
    volume = 40.0 * min(features["volume_ratio_20"] / 5.0, 1.0)
    ret_5d = 30.0 * _clip(features["ret_5d"] / 0.20, -1.0, 1.0)
    ret_20d = 15.0 * _clip(features["ret_20d"] / 0.40, -1.0, 1.0)
    breakout = 5.0 * int(features["breakout_20"]) + 10.0 * int(features["breakout_60"])
    return round(volume + ret_5d + ret_20d + breakout, 6)


def _rounded_features(features: dict) -> dict:
    output = {}
    for key, value in features.items():
        if isinstance(value, float):
            if not math.isfinite(value):
                raise RadarError(f"non-finite radar feature: {key}")
            output[key] = round(value, 8)
        else:
            output[key] = value
    return output


def _signal_id(profile: str, symbol: str, signal_date: str, snapshot_sha256: str) -> str:
    raw = f"{SCORING_VERSION}|{profile}|{symbol}|{signal_date}|{snapshot_sha256}"
    return "radar-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))
