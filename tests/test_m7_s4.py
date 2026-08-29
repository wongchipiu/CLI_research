import json
from pathlib import Path

import pytest

from quant.contracts import ContractError, validate_strategy_validation
from quant.services.workflow import WorkflowRequest, run_workflow
from quant.workspace import DEFAULT_CONFIG, WorkspaceConfig


def make_workspace(tmp_path: Path) -> WorkspaceConfig:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "universe.yaml").write_text(
        "default_profile: test\nprofiles:\n  test:\n    cn: []\n    us: []\n    cn_index: []\n",
        encoding="utf-8",
    )
    gpt_root = Path(__file__).resolve().parents[2] / "gpt_quant"
    config = tmp_path / "workspace.yaml"
    config.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "artifact_type: quant_workspace_config",
                "project_root: .",
                "paths:",
                "  data: data",
                "  results: artifacts/results",
                "  studies: artifacts/studies",
                "  universe: config/universe.yaml",
                f"  gpt_quant: {gpt_root}",
            ]
        ),
        encoding="utf-8",
    )
    return WorkspaceConfig.load(config)


def test_workspace_paths_do_not_depend_on_current_directory(tmp_path, monkeypatch):
    config = make_workspace(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    reloaded = WorkspaceConfig.load(config.config_path)

    assert reloaded.project_root == tmp_path.resolve()
    assert reloaded.results_dir == (tmp_path / "artifacts" / "results").resolve()
    assert reloaded.resolve_study_path("momentum-us.json") == (
        tmp_path / "artifacts" / "studies" / "momentum-us.json"
    ).resolve()
    assert DEFAULT_CONFIG.name == "workspace.yaml"


def test_workflow_uses_versioned_contracts_and_configured_result_root(tmp_path):
    config = make_workspace(tmp_path)
    run_dir = config.results_dir / "scan_momentum_us_test"
    calls = []

    def runner(command, cwd):
        calls.append((command, cwd))
        if command[2].endswith("check_data.py"):
            return {
                "schema_version": 1,
                "artifact_type": "data_quality_summary",
                "market": "us",
                "summary": {"symbols": 2, "ok": 2, "warnings": 0, "errors": 0},
                "reports": [],
            }
        run_dir.mkdir(parents=True)
        (run_dir / "metrics.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "artifact_type": "strategy_validation",
                    "execution_model": "next_open_v1",
                    "params": {"lookback": 20},
                    "research_protocol": {"selection_scope": "train_only"},
                    "validation": {"final_test_status": "completed"},
                }
            ),
            encoding="utf-8",
        )
        return {"run_dir": str(run_dir), "final_test_status": "completed"}

    def validator(metrics_path):
        assert metrics_path == run_dir / "metrics.json"
        return {
            "schema_version": 1,
            "artifact_type": "strategy_validation_decision",
            "decision": "PAPER_TRADING",
            "checks": [],
        }

    output = run_workflow(
        WorkflowRequest(
            strategy="momentum",
            market="us",
            params=("lookback=20,60", "top_n=1", "rebalance=20"),
            study_file="momentum-us.json",
            start="2018-01-01",
            end="2026-07-20",
            train_end="2022-12-30",
            final_start="2024-09-02",
        ),
        config,
        command_runner=runner,
        validator=validator,
    )

    assert output["decision"] == "PAPER_TRADING"
    assert Path(output["run_dir"]).parent == config.results_dir
    assert Path(output["study_file"]).parent == config.studies_dir
    assert json.loads((run_dir / "workflow.json").read_text())["schema_version"] == 1
    assert all(cwd == config.project_root for _, cwd in calls)
    scan_command = calls[1][0]
    assert scan_command[scan_command.index("--start") + 1] == "2018-01-01"
    assert scan_command[scan_command.index("--train-end") + 1] == "2022-12-30"


def test_bad_or_legacy_evidence_is_rejected_explicitly():
    with pytest.raises(ContractError, match="strategy_validation schema_version 2"):
        validate_strategy_validation(
            {
                "schema_version": 1,
                "artifact_type": "strategy_validation",
                "execution_model": "legacy_same_close",
            }
        )
