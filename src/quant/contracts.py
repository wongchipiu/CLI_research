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


def _require_envelope(payload: dict, artifact_type: str, schema_version: int) -> None:
    if not isinstance(payload, dict):
        raise ContractError(f"{artifact_type} root must be an object")
    if payload.get("artifact_type") != artifact_type or payload.get("schema_version") != schema_version:
        raise ContractError(f"expected {artifact_type} schema_version {schema_version}")
