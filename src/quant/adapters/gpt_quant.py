"""Invoke the sibling gpt_quant validator through its public CLI contract."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from quant.contracts import ContractError, validate_strategy_decision
from quant.workspace import WorkspaceConfig


class IntegrationError(RuntimeError):
    """Raised when the validator cannot be invoked or violates its contract."""


class GPTQuantAdapter:
    def __init__(self, workspace: WorkspaceConfig):
        self.workspace = workspace

    def validate(self, metrics_path: str | Path) -> dict:
        env = dict(os.environ)
        source = str(self.workspace.gpt_quant_root / "src")
        env["PYTHONPATH"] = os.pathsep.join(filter(None, (source, env.get("PYTHONPATH"))))
        process = subprocess.run(
            [sys.executable, "-B", "-m", "gpt_quant.cli", "validate-cli-result", str(Path(metrics_path).resolve())],
            cwd=self.workspace.gpt_quant_root,
            env=env,
            capture_output=True,
            text=True,
        )
        if process.returncode:
            detail = (process.stderr or process.stdout).strip().splitlines()
            raise IntegrationError(f"gpt_quant validation failed: {detail[-1] if detail else 'unknown error'}")
        try:
            payload = json.loads(process.stdout)
            return validate_strategy_decision(payload)
        except (json.JSONDecodeError, ContractError) as exc:
            raise IntegrationError(f"gpt_quant returned an invalid decision contract: {exc}") from exc
