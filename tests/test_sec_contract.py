import hashlib
import json
from datetime import datetime, timezone

from quant.cli import main
from quant.contracts import ContractError, validate_sec_evidence


def evidence(filed_at: str = "2026-01-02T10:00:00Z") -> dict:
    content = "{\"revenue\":100}"
    return {
        "schema_version": 1, "artifact_type": "sec_evidence", "evidence_id": "0000123456:0001",
        "accession": "0001", "issuer_cik": "0000123456", "form_type": "10-K", "filed_at": filed_at,
        "period_end": "2025-12-31", "source_url": "https://www.sec.gov/Archives/0001",
        "content_sha256": hashlib.sha256(content.encode()).hexdigest(), "content": content,
        "retrieved_at": "2026-01-02T11:00:00Z",
    }


def test_sec_evidence_contract_and_as_of_boundary(tmp_path):
    payload = evidence()
    assert validate_sec_evidence(payload, as_of=datetime(2026, 1, 2, 12, tzinfo=timezone.utc)) == payload
    path = tmp_path / "sec.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert main(["validate-sec-evidence", str(path)]) == 0


def test_sec_evidence_rejects_future_or_tampered_payload():
    payload = evidence("2026-01-03T10:00:00Z")
    payload["retrieved_at"] = "2026-01-03T11:00:00Z"
    try:
        validate_sec_evidence(payload, as_of=datetime(2026, 1, 2, 12, tzinfo=timezone.utc))
    except ContractError as exc:
        assert "as_of" in str(exc)
    else:
        raise AssertionError("future SEC evidence was accepted")
    payload = evidence()
    payload["content"] = "tampered"
    try:
        validate_sec_evidence(payload)
    except ContractError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("tampered SEC evidence was accepted")
