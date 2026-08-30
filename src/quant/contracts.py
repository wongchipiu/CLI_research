"""Small, explicit JSON contracts used at project boundaries."""

from __future__ import annotations

import json
from pathlib import Path


class ContractError(ValueError):
    """Raised when an artifact does not match its declared version."""


def load_json_object(path: str | Path) -> dict:
    artifact_path = Path(path)
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContractError(f"cannot read artifact: {artifact_path}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON artifact: {artifact_path}") from exc
    if not isinstance(payload, dict):
        raise ContractError(f"artifact root must be an object: {artifact_path}")
    return payload


def validate_data_quality_summary(payload: dict) -> dict:
    _require_envelope(payload, "data_quality_summary", 1)
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ContractError("data_quality_summary.summary must be an object")
    for key in ("symbols", "ok", "warnings", "errors"):
        if type(summary.get(key)) is not int or summary[key] < 0:
            raise ContractError(f"data_quality_summary.summary.{key} must be a nonnegative integer")
    if summary["ok"] + summary["warnings"] + summary["errors"] != summary["symbols"]:
        raise ContractError("data quality counts do not add up to symbols")
    return payload


def validate_strategy_validation(payload: dict) -> dict:
    _require_envelope(payload, "strategy_validation", 2)
    if payload.get("execution_model") != "next_open_v1":
        raise ContractError("strategy_validation requires execution_model next_open_v1")
    if not isinstance(payload.get("params"), dict):
        raise ContractError("strategy_validation.params must be an object")
    if not isinstance(payload.get("research_protocol"), dict):
        raise ContractError("strategy_validation.research_protocol must be an object")
    validation = payload.get("validation")
    if not isinstance(validation, dict):
        raise ContractError("strategy_validation.validation must be an object")
    if validation.get("final_test_status") not in {"completed", "not_run"}:
        raise ContractError("strategy_validation has an invalid final_test_status")
    return payload


def validate_strategy_decision(payload: dict) -> dict:
    _require_envelope(payload, "strategy_validation_decision", 1)
    if payload.get("decision") not in {"BLOCKED", "PAPER_TRADING", "LIVE_READY"}:
        raise ContractError("strategy validation decision is unsupported")
    if not isinstance(payload.get("checks"), list):
        raise ContractError("strategy validation decision checks must be a list")
    return payload


def validate_daily_radar_scan(payload: dict) -> dict:
    _require_envelope(payload, "daily_radar_scan", 1)
    if payload.get("market") != "us":
        raise ContractError("daily_radar_scan market must be us")
    if payload.get("status") not in {"OK", "DEGRADED"}:
        raise ContractError("daily_radar_scan status must be OK or DEGRADED")
    for key in ("profile", "signal_date", "generated_at", "available_at", "scoring_version"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ContractError(f"daily_radar_scan {key} must be a non-empty string")
    snapshot = payload.get("data_snapshot")
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("symbols"), dict):
        raise ContractError("daily_radar_scan data_snapshot must include symbols")
    sha256 = snapshot.get("sha256")
    if not isinstance(sha256, str) or len(sha256) != 64:
        raise ContractError("daily_radar_scan data_snapshot.sha256 must be a SHA-256 hex digest")
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ContractError("daily_radar_scan summary must be an object")
    for key in (
        "requested", "loaded", "features_computed", "base_eligible",
        "candidates_total", "candidates_returned", "excluded",
    ):
        if type(summary.get(key)) is not int or summary[key] < 0:
            raise ContractError(f"daily_radar_scan summary.{key} must be a nonnegative integer")
    candidates = payload.get("candidates")
    excluded = payload.get("excluded")
    if not isinstance(candidates, list) or not isinstance(excluded, list):
        raise ContractError("daily_radar_scan candidates and excluded must be lists")
    if summary["candidates_returned"] != len(candidates) or summary["excluded"] != len(excluded):
        raise ContractError("daily_radar_scan summary counts do not match item lists")
    for rank, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict) or candidate.get("rank") != rank:
            raise ContractError("daily_radar_scan candidate ranks must be consecutive")
        if not isinstance(candidate.get("signal_id"), str) or not candidate["signal_id"].startswith("radar-"):
            raise ContractError("daily_radar_scan candidate signal_id is invalid")
        if not isinstance(candidate.get("features"), dict):
            raise ContractError("daily_radar_scan candidate features must be an object")
    return payload


def validate_daily_radar_tracking(payload: dict) -> dict:
    _require_envelope(payload, "daily_radar_tracking", 1)
    if payload.get("market") != "us":
        raise ContractError("daily_radar_tracking market must be us")
    for key in ("profile", "benchmark", "latest_market_date", "generated_at"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ContractError(f"daily_radar_tracking {key} must be a non-empty string")
    horizons = payload.get("horizons")
    if (
        not isinstance(horizons, list)
        or not horizons
        or any(type(value) is not int or value <= 0 for value in horizons)
        or horizons != sorted(set(horizons))
    ):
        raise ContractError("daily_radar_tracking horizons must be sorted unique positive integers")
    for key in ("buy_fee", "sell_fee"):
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value < 1:
            raise ContractError(f"daily_radar_tracking {key} must be in [0, 1)")
    snapshot = payload.get("tracking_snapshot")
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("frames"), dict):
        raise ContractError("daily_radar_tracking tracking_snapshot must include frames")
    if not isinstance(snapshot.get("sha256"), str) or len(snapshot["sha256"]) != 64:
        raise ContractError("daily_radar_tracking tracking_snapshot.sha256 is invalid")
    signals = payload.get("signals")
    if not isinstance(signals, list):
        raise ContractError("daily_radar_tracking signals must be a list")
    seen = set()
    status_counts = {"MATURED": 0, "PENDING": 0, "MISSING": 0, "DELISTED": 0}
    for signal in signals:
        if not isinstance(signal, dict):
            raise ContractError("daily_radar_tracking signal must be an object")
        signal_id = signal.get("signal_id")
        if not isinstance(signal_id, str) or not signal_id.startswith("radar-") or signal_id in seen:
            raise ContractError("daily_radar_tracking signal_id is invalid or duplicated")
        seen.add(signal_id)
        outcomes = signal.get("outcomes")
        if not isinstance(outcomes, dict) or set(outcomes) != {str(value) for value in horizons}:
            raise ContractError("daily_radar_tracking outcomes do not match horizons")
        for horizon in horizons:
            outcome = outcomes[str(horizon)]
            if not isinstance(outcome, dict) or outcome.get("status") not in status_counts:
                raise ContractError("daily_radar_tracking outcome status is invalid")
            status_counts[outcome["status"]] += 1
            if outcome.get("required_sessions") != horizon:
                raise ContractError("daily_radar_tracking required_sessions does not match horizon")
            if outcome["status"] == "MATURED":
                descriptive = outcome.get("descriptive")
                executable = outcome.get("executable")
                if not isinstance(descriptive, dict) or descriptive.get("status") != "OK":
                    raise ContractError("matured tracking outcome requires descriptive result")
                if not isinstance(executable, dict) or executable.get("status") != "OK":
                    raise ContractError("matured tracking outcome requires executable result")
    summary = payload.get("summary")
    if not isinstance(summary, dict) or summary.get("signals") != len(signals):
        raise ContractError("daily_radar_tracking summary signal count is invalid")
    expected_outcomes = len(signals) * len(horizons)
    if summary.get("outcomes") != expected_outcomes:
        raise ContractError("daily_radar_tracking summary outcome count is invalid")
    for key, status in (
        ("matured", "MATURED"),
        ("pending", "PENDING"),
        ("missing", "MISSING"),
        ("delisted", "DELISTED"),
    ):
        if summary.get(key) != status_counts[status]:
            raise ContractError(f"daily_radar_tracking summary {key} count is invalid")
    return payload


def _require_envelope(payload: dict, artifact_type: str, schema_version: int) -> None:
    if not isinstance(payload, dict):
        raise ContractError(f"{artifact_type} root must be an object")
    if payload.get("artifact_type") != artifact_type or payload.get("schema_version") != schema_version:
        raise ContractError(f"expected {artifact_type} schema_version {schema_version}")
