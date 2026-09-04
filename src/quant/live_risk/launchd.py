"""Render, but never install, a macOS launchd job for the night guard."""

from __future__ import annotations

from pathlib import Path
import plistlib


def render_launchd_plist(
    project_root: str | Path,
    config_path: str | Path,
    *,
    python_path: str | Path | None = None,
    label: str = "com.quant.live-risk-paper",
) -> bytes:
    root = Path(project_root).expanduser().resolve()
    config = Path(config_path).expanduser().resolve()
    # Preserve the virtualenv executable path instead of resolving its symlink
    # to the base interpreter, which would lose the environment's packages.
    python = Path(python_path).expanduser().absolute() if python_path else root / ".venv" / "bin" / "python"
    service_script = root / "scripts" / "run_live_risk.py"
    if not config.is_file():
        raise ValueError(f"live-risk config does not exist: {config}")
    if not python.is_file():
        raise ValueError(f"Python executable does not exist: {python}")
    if not service_script.is_file():
        raise ValueError(f"live-risk service script does not exist: {service_script}")
    if not label or any(character.isspace() for character in label):
        raise ValueError("launchd label must be nonempty and contain no whitespace")

    runtime = root / "var" / "live_risk"
    payload = {
        "Label": label,
        "ProgramArguments": [
            "/usr/bin/caffeinate",
            "-im",
            str(python),
            "-B",
            str(service_script),
            "--config",
            str(config),
        ],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "ProcessType": "Background",
        "WorkingDirectory": str(root),
        "StandardOutPath": str(runtime / "launchd.stdout.log"),
        "StandardErrorPath": str(runtime / "launchd.stderr.log"),
    }
    return plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=True)
