"""Versioned workspace configuration with paths independent of the shell cwd."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys

import yaml


def _default_config_path() -> Path:
    override = os.environ.get("QUANT_WORKSPACE")
    if override:
        return Path(override).expanduser().resolve()
    candidates = (
        Path(sys.prefix).resolve().parent / "config" / "workspace.yaml",
        Path(__file__).resolve().parents[2] / "config" / "workspace.yaml",
    )
    return next((path for path in candidates if path.is_file()), candidates[-1])


DEFAULT_CONFIG = _default_config_path()


class WorkspaceConfigError(ValueError):
    """Raised when the workspace contract is missing or unsupported."""


@dataclass(frozen=True)
class WorkspaceConfig:
    config_path: Path
    project_root: Path
    data_dir: Path
    results_dir: Path
    studies_dir: Path
    universe_path: Path
    radar_path: Path
    gpt_quant_root: Path

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG) -> "WorkspaceConfig":
        config_path = Path(path).expanduser().resolve()
        try:
            payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise WorkspaceConfigError(f"cannot read workspace config: {config_path}") from exc
        except yaml.YAMLError as exc:
            raise WorkspaceConfigError(f"invalid workspace YAML: {config_path}") from exc
        if not isinstance(payload, dict):
            raise WorkspaceConfigError("workspace config root must be an object")
        if payload.get("schema_version") != 1 or payload.get("artifact_type") != "quant_workspace_config":
            raise WorkspaceConfigError("workspace config requires quant_workspace_config schema_version 1")
        paths = payload.get("paths")
        if not isinstance(paths, dict):
            raise WorkspaceConfigError("workspace config paths must be an object")
        required = {"data", "results", "studies", "universe", "gpt_quant"}
        missing = required - paths.keys()
        if missing:
            raise WorkspaceConfigError(f"workspace config missing paths: {sorted(missing)}")

        project_value = payload.get("project_root", "..")
        project_root = _resolve(config_path.parent, project_value)
        config = cls(
            config_path=config_path,
            project_root=project_root,
            data_dir=_resolve(project_root, paths["data"]),
            results_dir=_resolve(project_root, paths["results"]),
            studies_dir=_resolve(project_root, paths["studies"]),
            universe_path=_resolve(project_root, paths["universe"]),
            radar_path=_resolve(project_root, paths.get("radar", "config/radar.yaml")),
            gpt_quant_root=_resolve(project_root, paths["gpt_quant"]),
        )
        if not config.universe_path.is_file():
            raise WorkspaceConfigError(f"universe config does not exist: {config.universe_path}")
        if not (config.gpt_quant_root / "src" / "gpt_quant" / "cli.py").is_file():
            raise WorkspaceConfigError(f"gpt_quant source tree does not exist: {config.gpt_quant_root}")
        return config

    def apply(self) -> None:
        """Configure legacy modules for this process without changing their APIs."""
        from quant.backtest import report
        from quant.data import storage, universe

        storage.DATA_DIR = self.data_dir
        report.RESULTS_DIR = self.results_dir
        universe.CONFIG_PATH = self.universe_path

    def resolve_project_path(self, value: str | Path) -> Path:
        return _resolve(self.project_root, value)

    def resolve_study_path(self, value: str | Path) -> Path:
        path = Path(value).expanduser()
        return path.resolve() if path.is_absolute() else (self.studies_dir / path).resolve()


def _resolve(base: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()
