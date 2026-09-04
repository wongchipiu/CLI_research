"""Quality-summary -> validation study -> independent validator workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable

from quant.adapters import GPTQuantAdapter
from quant.contracts import (
    ContractError,
    load_json_object,
    validate_data_quality_summary,
    validate_strategy_decision,
    validate_strategy_validation,
)
from quant.workspace import WorkspaceConfig


class WorkflowError(RuntimeError):
    """Raised when a deterministic workflow stage fails."""


@dataclass(frozen=True)
class WorkflowRequest:
    strategy: str
    market: str
    params: tuple[str, ...]
    study_file: str
    universe: str | None = None
    membership_file: str | None = None
    start: str | None = None
    end: str | None = None
    train_ratio: float = 0.6
    validation_ratio: float = 0.2
    train_end: str | None = None
    final_start: str | None = None
    walk_forward: bool = False
    wf_train_days: int = 756
    wf_test_days: int = 126
    max_position_weight: float = 1.0
    max_gross_exposure: float = 1.0
    target_volatility: float | None = None
    volatility_window: int = 20
    regime_window: int | None = None
    risk_off_exposure: float = 0.0


CommandRunner = Callable[[list[str], Path], dict]
Validator = Callable[[Path], dict]


def run_workflow(
    request: WorkflowRequest,
    workspace: WorkspaceConfig,
    *,
    command_runner: CommandRunner | None = None,
    validator: Validator | None = None,
) -> dict:
    if not request.params:
        raise WorkflowError("workflow requires at least one parameter grid")
    runner = command_runner or _run_json_command
    validate = validator or GPTQuantAdapter(workspace).validate
    workspace.apply()

    quality_command = [
        sys.executable, "-B", str(workspace.project_root / "scripts" / "check_data.py"),
        "--quiet", "--allow-errors", "--market", request.market,
        "--workspace", str(workspace.config_path),
    ]
    quality = validate_data_quality_summary(runner(quality_command, workspace.project_root))
    if not quality["summary"]["symbols"]:
        raise WorkflowError(f"data quality blocked the workflow: no local {request.market} symbols")
    if quality["summary"]["errors"]:
        raise WorkflowError(
            f"data quality blocked the workflow: {quality['summary']['errors']} error symbol(s)"
        )

    study_path = workspace.resolve_study_path(request.study_file)
    scan_command = [
        sys.executable, "-B", str(workspace.project_root / "scripts" / "run_parameter_scan.py"),
        "--strategy", request.strategy, "--market", request.market,
        "--study-file", str(study_path), "--compact", "--workspace", str(workspace.config_path),
        "--train-ratio", str(request.train_ratio), "--validation-ratio", str(request.validation_ratio),
        "--max-position-weight", str(request.max_position_weight),
        "--max-gross-exposure", str(request.max_gross_exposure),
        "--volatility-window", str(request.volatility_window),
        "--risk-off-exposure", str(request.risk_off_exposure),
    ]
    if request.universe:
        scan_command.extend(("--universe", request.universe))
    if request.membership_file:
        scan_command.extend(("--membership-file", str(workspace.resolve_project_path(request.membership_file))))
    for option, value in (
        ("--start", request.start),
        ("--end", request.end),
        ("--train-end", request.train_end),
        ("--final-start", request.final_start),
        ("--target-volatility", request.target_volatility),
        ("--regime-window", request.regime_window),
    ):
        if value is not None:
            scan_command.extend((option, str(value)))
    if request.walk_forward:
        scan_command.extend(("--walk-forward", "--wf-train-days", str(request.wf_train_days),
                             "--wf-test-days", str(request.wf_test_days)))
    for parameter in request.params:
        scan_command.extend(("-p", parameter))
    scan = runner(scan_command, workspace.project_root)
    run_dir = Path(str(scan.get("run_dir", ""))).resolve()
    if not run_dir.is_relative_to(workspace.results_dir):
        raise WorkflowError(f"scan result escaped configured results directory: {run_dir}")
    metrics_path = run_dir / "metrics.json"
    validate_strategy_validation(load_json_object(metrics_path))
    decision = validate_strategy_decision(validate(metrics_path))

    output = {
        "schema_version": 1,
        "artifact_type": "research_workflow",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "workspace_root": str(workspace.project_root),
        "data_quality": quality["summary"],
        "run_dir": str(run_dir),
        "metrics_path": str(metrics_path),
        "study_file": str(study_path),
        "decision": decision["decision"],
        "checks": decision["checks"],
    }
    (run_dir / "workflow.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    return output


def _run_json_command(command: list[str], cwd: Path) -> dict:
    env = dict(os.environ)
    source = str(cwd / "src")
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (source, env.get("PYTHONPATH"))))
    process = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    if process.returncode:
        detail = (process.stderr or process.stdout).strip().splitlines()
        raise WorkflowError(f"workflow command failed: {detail[-1] if detail else command[0]}")
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"workflow command returned invalid JSON: {command[-1]}") from exc
    if not isinstance(payload, dict):
        raise WorkflowError("workflow command JSON root must be an object")
    return payload
