"""Versioned configuration for daily radar profiles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml


class RadarConfigError(ValueError):
    """Raised when the radar configuration is missing or invalid."""


@dataclass(frozen=True)
class RadarProfile:
    name: str
    market: str
    universe_profile: str
    exclude_symbols: tuple[str, ...]
    min_history: int
    min_price: float
    min_average_dollar_volume_20: float
    min_volume_ratio_20: float
    min_ret_5d: float
    max_results: int


@dataclass(frozen=True)
class TrackingConfig:
    benchmark: str
    horizons: tuple[int, ...]
    buy_fee: float
    sell_fee: float
    delistings: tuple[tuple[str, str], ...] = ()


def load_radar_profile(path: str | Path, name: str | None = None) -> RadarProfile:
    root = _load_root(path)
    profiles = root.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise RadarConfigError("radar config profiles must be a non-empty object")
    active = name or root.get("default_profile")
    if active not in profiles or not isinstance(profiles[active], dict):
        raise RadarConfigError(f"unknown radar profile {active!r}; available: {sorted(profiles)}")
    payload = profiles[active]

    profile = RadarProfile(
        name=str(active),
        market=_string(payload, "market"),
        universe_profile=_string(payload, "universe_profile"),
        exclude_symbols=tuple(
            sorted({str(symbol).upper() for symbol in payload.get("exclude_symbols", [])})
        ),
        min_history=_positive_int(payload, "min_history"),
        min_price=_nonnegative_number(payload, "min_price"),
        min_average_dollar_volume_20=_nonnegative_number(
            payload, "min_average_dollar_volume_20"
        ),
        min_volume_ratio_20=_nonnegative_number(payload, "min_volume_ratio_20"),
        min_ret_5d=_number(payload, "min_ret_5d"),
        max_results=_positive_int(payload, "max_results"),
    )
    if profile.market != "us":
        raise RadarConfigError("M7-S5 only supports market 'us'")
    if profile.min_history < 61:
        raise RadarConfigError("radar min_history must be at least 61")
    return profile


def load_tracking_config(path: str | Path) -> TrackingConfig:
    root = _load_root(path)
    payload = root.get("tracking")
    if not isinstance(payload, dict):
        raise RadarConfigError("radar tracking config must be an object")
    benchmark = _string(payload, "benchmark").upper()
    horizons = payload.get("horizons")
    if not isinstance(horizons, list) or not horizons:
        raise RadarConfigError("radar tracking horizons must be a non-empty list")
    if any(type(value) is not int or value <= 0 for value in horizons):
        raise RadarConfigError("radar tracking horizons must contain positive integers")
    normalized_horizons = tuple(sorted(set(horizons)))
    if len(normalized_horizons) != len(horizons):
        raise RadarConfigError("radar tracking horizons must not contain duplicates")
    buy_fee = _nonnegative_number(payload, "buy_fee")
    sell_fee = _nonnegative_number(payload, "sell_fee")
    if buy_fee >= 1 or sell_fee >= 1:
        raise RadarConfigError("radar tracking fees must be less than 1")
    delistings = payload.get("delistings", {})
    if not isinstance(delistings, dict):
        raise RadarConfigError("radar tracking delistings must be an object")
    normalized_delistings = []
    for symbol, final_date in delistings.items():
        try:
            parsed = str(pd.Timestamp(final_date).normalize().date())
        except (TypeError, ValueError):
            raise RadarConfigError(f"invalid delisting date for {symbol}: {final_date}") from None
        normalized_delistings.append((str(symbol).upper(), parsed))
    return TrackingConfig(
        benchmark,
        normalized_horizons,
        buy_fee,
        sell_fee,
        tuple(sorted(normalized_delistings)),
    )


def _load_root(path: str | Path) -> dict:
    config_path = Path(path)
    try:
        root = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RadarConfigError(f"cannot read radar config: {config_path}") from exc
    except yaml.YAMLError as exc:
        raise RadarConfigError(f"invalid radar YAML: {config_path}") from exc
    if not isinstance(root, dict):
        raise RadarConfigError("radar config root must be an object")
    if root.get("schema_version") != 1 or root.get("artifact_type") != "daily_radar_config":
        raise RadarConfigError("radar config requires daily_radar_config schema_version 1")
    return root


def _string(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise RadarConfigError(f"radar profile {key} must be a non-empty string")
    return value


def _number(payload: dict, key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RadarConfigError(f"radar profile {key} must be a number")
    return float(value)


def _nonnegative_number(payload: dict, key: str) -> float:
    value = _number(payload, key)
    if value < 0:
        raise RadarConfigError(f"radar profile {key} must be nonnegative")
    return value


def _positive_int(payload: dict, key: str) -> int:
    value = payload.get(key)
    if type(value) is not int or value <= 0:
        raise RadarConfigError(f"radar profile {key} must be a positive integer")
    return value
