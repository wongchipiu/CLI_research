import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from quant.llm_experiments import (
    ExperimentLedger,
    ExperimentSeries,
    LLMExperimentManifest,
    build_experiment_report,
    compare_series,
    evaluate_experiment,
    negative_control,
)
from quant.cli import main


def test_compare_series_is_deterministic_and_blocks_small_or_uncertain_samples():
    baseline = ExperimentSeries("B2", tuple([0.01] * 40))
    challenger = ExperimentSeries("B3", tuple([0.02] * 40), model_cost=0.01)
    first = compare_series(baseline, challenger, bootstrap_samples=100, seed=7)
    second = compare_series(baseline, challenger, bootstrap_samples=100, seed=7)
    assert first == second
    assert first.status == "PASS"
    assert compare_series(ExperimentSeries("B2", (0.0,)), ExperimentSeries("B3", (0.1,))).status == "INCONCLUSIVE"


def test_negative_control_preserves_values_but_changes_order():
    source = ExperimentSeries("B3", (0.01, 0.02, 0.03, 0.04))
    shuffled = negative_control(source, seed=3)
    assert shuffled.name == "N1"
    assert sorted(shuffled.net_returns) == list(source.net_returns)
    assert shuffled.net_returns != source.net_returns


def test_compare_rejects_mismatched_samples():
    with pytest.raises(ValueError, match="same event sample"):
        compare_series(ExperimentSeries("B2", (0.1,)), ExperimentSeries("B3", (0.1, 0.2)))


def test_build_report_requires_all_baselines_and_is_inconclusive_on_small_samples():
    series = {name: ExperimentSeries(name, tuple([0.01] * 3)) for name in ("B0", "B1", "B2", "B3")}
    report = build_experiment_report("exp-1", series, bootstrap_samples=20)
    assert report.status == "INCONCLUSIVE"
    assert len(report.comparisons) == 3
    assert report.to_dict()["artifact_type"] == "llm_experiment_report"


def manifest(**overrides):
    values = {
        "hypothesis": "cited LLM features add value beyond deterministic events",
        "universe_sha256": "a" * 64,
        "data_snapshot_sha256": "b" * 64,
        "feature_version": "llm-feature-v1",
        "final_test_start": "2026-01-01",
        "final_test_end": "2026-06-30",
        "min_samples": 30,
        "cost_stress_bps": (0.0, 10.0, 25.0),
    }
    values.update(overrides)
    return LLMExperimentManifest(**values)


def series(name, value, **kwargs):
    return ExperimentSeries(name, tuple([value] * 40), **kwargs)


def test_manifest_id_is_deterministic_and_changes_when_protocol_changes():
    assert manifest().experiment_id == manifest().experiment_id
    assert manifest(feature_version="llm-feature-v2").experiment_id != manifest().experiment_id


def test_evaluate_experiment_checks_quality_stress_and_negative_controls():
    items = {
        "B0": series("B0", 0.005, capacity_notional=100_000),
        "B1": series("B1", 0.01, capacity_notional=100_000),
        "B2": series("B2", 0.02, coverage=0.95, abstention_rate=0.05, turnover=1.0, capacity_notional=100_000),
        "B3": series("B3", 0.03, model_cost=0.01, coverage=0.9, abstention_rate=0.1, turnover=1.0, capacity_notional=100_000),
        "N1": series("N1", 0.019),
        "N2": series("N2", 0.018),
    }
    report = evaluate_experiment(manifest(min_capacity_notional=50_000), items)
    assert report.status == "PASS"
    assert all(item.status == "PASS" for item in report.stress)
    assert all(item["status"] == "PASS" for item in report.negative_controls)

    bad = dict(items)
    bad["B3"] = series("B3", 0.03, coverage=0.4, capacity_notional=100_000)
    assert evaluate_experiment(manifest(), bad).status == "INCONCLUSIVE"


def test_final_test_ledger_is_frozen_and_single_use():
    items = {
        name: series(name, value, coverage=0.95, capacity_notional=100_000)
        for name, value in {"B0": 0.005, "B1": 0.01, "B2": 0.02, "B3": 0.03, "N1": 0.019, "N2": 0.018}.items()
    }
    with TemporaryDirectory() as directory:
        ledger = ExperimentLedger(Path(directory) / "ledger.jsonl")
        protocol = manifest()
        ledger.register(protocol)
        ledger.freeze()
        report = evaluate_experiment(protocol, items, phase="final_test", ledger=ledger)
        assert report.final_test_sha256 and ledger.final_test_consumed
        with pytest.raises(ValueError, match="already been consumed"):
            evaluate_experiment(protocol, items, phase="final_test", ledger=ledger)
        assert ExperimentLedger(Path(directory) / "ledger.jsonl").final_test_consumed


def test_experiment_evaluate_cli_consumes_final_test_once():
    protocol = manifest()
    manifest_payload = {
        "schema_version": 1,
        "artifact_type": "llm_experiment_manifest",
        **protocol.__dict__,
        "cost_stress_bps": list(protocol.cost_stress_bps),
    }
    values = {"B0": 0.005, "B1": 0.01, "B2": 0.02, "B3": 0.03, "N1": 0.019, "N2": 0.018}
    with TemporaryDirectory() as directory:
        root = Path(directory)
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
        series_args = []
        for name, value in values.items():
            path = root / f"{name}.json"
            path.write_text(json.dumps({
                "net_returns": [value] * 40,
                "coverage": 0.95,
                "abstention_rate": 0.05,
                "capacity_notional": 100_000,
            }), encoding="utf-8")
            series_args.extend(["--series", f"{name}={path}"])
        output = StringIO()
        with redirect_stdout(output):
            exit_code = main([
                "experiment-evaluate", "--manifest", str(manifest_path),
                *series_args, "--output", str(root / "evaluation"),
                "--phase", "final_test", "--ledger", str(root / "ledger.jsonl"),
            ])
        assert exit_code == 0
        assert json.loads((root / "evaluation.json").read_text())['status'] == "PASS"
        assert json.loads(output.getvalue())["status"] == "PASS"
