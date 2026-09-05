"""Small, explicit JSON contracts used at project boundaries."""

from __future__ import annotations

import json
from datetime import datetime
import hashlib
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
    if payload.get("decision") not in {"BLOCKED", "PAPER_TRADING"}:
        raise ContractError("strategy validation decision is unsupported")
    if not isinstance(payload.get("checks"), list):
        raise ContractError("strategy validation decision checks must be a list")
    return payload


def validate_sec_evidence(payload: dict, *, as_of: datetime | None = None) -> dict:
    """Validate the provider-neutral SEC Evidence v1 contract."""
    _require_envelope(payload, "sec_evidence", 1)
    required = ("evidence_id", "accession", "issuer_cik", "form_type", "filed_at", "period_end", "source_url", "content_sha256", "content", "retrieved_at")
    for key in required:
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ContractError(f"sec_evidence {key} must be a non-empty string")
    if payload["evidence_id"] != f"{payload['issuer_cik']}:{payload['accession']}":
        raise ContractError("sec_evidence evidence_id does not match issuer and accession")
    if not payload["issuer_cik"].isdigit():
        raise ContractError("sec_evidence issuer_cik must contain only digits")
    digest = payload["content_sha256"]
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ContractError("sec_evidence content_sha256 must be a lowercase SHA-256 digest")
    if hashlib.sha256(payload["content"].encode("utf-8")).hexdigest() != digest:
        raise ContractError("sec_evidence content_sha256 does not match content")
    if not payload["source_url"].startswith("https://"):
        raise ContractError("sec_evidence source_url must use https")
    try:
        filed_at = datetime.fromisoformat(payload["filed_at"].replace("Z", "+00:00"))
        retrieved_at = datetime.fromisoformat(payload["retrieved_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("sec_evidence timestamps must be ISO-8601") from exc
    if filed_at.tzinfo is None or retrieved_at.tzinfo is None:
        raise ContractError("sec_evidence timestamps must include a UTC offset")
    if retrieved_at < filed_at:
        raise ContractError("sec_evidence retrieved_at cannot precede filed_at")
    if as_of is not None:
        if as_of.tzinfo is None:
            raise ContractError("sec_evidence as_of must include a UTC offset")
        if filed_at > as_of:
            raise ContractError("sec_evidence is not available at the requested as_of")
    return payload


def validate_sec_evidence_v2(payload: dict, *, as_of: datetime | None = None, mode: str | None = None) -> dict:
    """Validate the shared SEC v2 point-in-time document contract."""
    _require_envelope(payload, "sec_evidence", 2)
    required = (
        "document_version_id", "evidence_id", "accession", "issuer_cik", "form_type",
        "accepted_at", "first_received_at", "validated_at", "available_at", "period_end",
        "source_url", "raw_bytes_sha256", "normalized_text_sha256", "content", "parser_version",
        "availability_mode",
    )
    for key in required:
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ContractError(f"sec_evidence v2 {key} must be a non-empty string")
    if payload["evidence_id"] != f"{payload['issuer_cik']}:{payload['accession']}:{payload['document_version_id']}" or not payload["issuer_cik"].isdigit():
        raise ContractError("sec_evidence v2 document identity is invalid")
    for key in ("raw_bytes_sha256", "normalized_text_sha256"):
        value = payload[key]
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ContractError(f"sec_evidence v2 {key} is not a SHA-256 digest")
    if hashlib.sha256(payload["content"].encode("utf-8")).hexdigest() != payload["normalized_text_sha256"]:
        raise ContractError("sec_evidence v2 normalized content hash does not match")
    if payload["availability_mode"] not in {"observed", "historical_reconstructed"}:
        raise ContractError("sec_evidence v2 availability_mode is invalid")
    timestamps = {}
    try:
        for key in ("accepted_at", "first_received_at", "validated_at", "available_at"):
            timestamps[key] = datetime.fromisoformat(payload[key].replace("Z", "+00:00"))
        if payload.get("published_at"):
            timestamps["published_at"] = datetime.fromisoformat(payload["published_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("sec_evidence v2 timestamps must be ISO-8601") from exc
    if any(value.tzinfo is None or value.utcoffset() is None for value in timestamps.values()):
        raise ContractError("sec_evidence v2 timestamps must include a UTC offset")
    if payload["availability_mode"] == "observed" and timestamps["available_at"] < max(
        timestamps["accepted_at"], timestamps["first_received_at"], timestamps["validated_at"]
    ):
        raise ContractError("observed available_at precedes reliable processing")
    if mode is not None and payload["availability_mode"] != mode:
        raise ContractError("SEC evidence mode does not match the requested mode")
    if as_of is not None:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ContractError("sec_evidence v2 as_of must include a UTC offset")
        if timestamps["available_at"] > as_of:
            raise ContractError("sec_evidence v2 is not available at the requested as_of")
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


def validate_daily_radar_job(payload: dict) -> dict:
    _require_envelope(payload, "daily_radar_job", 1)
    if payload.get("market") != "us":
        raise ContractError("daily_radar_job market must be us")
    for key in ("job_id", "profile", "job_date", "started_at", "state_path"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ContractError(f"daily_radar_job {key} must be a non-empty string")
    if type(payload.get("attempt")) is not int or payload["attempt"] <= 0:
        raise ContractError("daily_radar_job attempt must be a positive integer")
    if payload.get("status") not in {"RUNNING", "FAILED", "COMPLETED", "COMPLETED_WITH_WARNINGS"}:
        raise ContractError("daily_radar_job status is invalid")
    stages = payload.get("stages")
    expected = {"update", "quality", "scan", "track", "report"}
    if not isinstance(stages, dict) or set(stages) != expected:
        raise ContractError("daily_radar_job stages are incomplete")
    for name, stage in stages.items():
        if not isinstance(stage, dict) or stage.get("status") not in {
            "PENDING", "RUNNING", "SKIPPED", "COMPLETED", "FAILED"
        }:
            raise ContractError(f"daily_radar_job stage {name} status is invalid")
        if not isinstance(stage.get("artifacts"), list) or not isinstance(stage.get("warnings"), list):
            raise ContractError(f"daily_radar_job stage {name} lists are invalid")
    if payload["status"] == "FAILED":
        failed_stage = payload.get("failed_stage")
        if failed_stage not in expected or stages[failed_stage]["status"] != "FAILED":
            raise ContractError("daily_radar_job failed_stage is inconsistent")
    return payload


def validate_daily_radar_report(payload: dict) -> dict:
    _require_envelope(payload, "daily_radar_report", 1)
    if payload.get("market") != "us":
        raise ContractError("daily_radar_report market must be us")
    for key in (
        "profile", "job_date", "signal_date", "latest_market_date",
        "scan_snapshot_sha256", "tracking_snapshot_sha256",
    ):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ContractError(f"daily_radar_report {key} must be a non-empty string")
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ContractError("daily_radar_report summary must be an object")
    for key in (
        "candidates", "signals_tracked", "matured_outcomes", "pending_outcomes",
        "missing_outcomes", "delisted_outcomes",
    ):
        if type(summary.get(key)) is not int or summary[key] < 0:
            raise ContractError(f"daily_radar_report summary.{key} must be nonnegative integer")
    candidates = payload.get("candidates")
    horizons = payload.get("horizons")
    if not isinstance(candidates, list) or not isinstance(horizons, dict):
        raise ContractError("daily_radar_report candidates and horizons are invalid")
    for horizon, item in horizons.items():
        if not horizon.isdigit() or not isinstance(item, dict):
            raise ContractError("daily_radar_report horizon is invalid")
        if type(item.get("sample_count")) is not int or item["sample_count"] < 0:
            raise ContractError("daily_radar_report sample_count is invalid")
        for key in ("matured", "pending", "missing", "delisted"):
            if type(item.get(key)) is not int or item[key] < 0:
                raise ContractError(f"daily_radar_report horizon {key} is invalid")
    return payload


def _require_envelope(payload: dict, artifact_type: str, schema_version: int) -> None:
    if not isinstance(payload, dict):
        raise ContractError(f"{artifact_type} root must be an object")
    if payload.get("artifact_type") != artifact_type or payload.get("schema_version") != schema_version:
        raise ContractError(f"expected {artifact_type} schema_version {schema_version}")
