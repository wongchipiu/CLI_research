"""Retryable update -> quality -> scan -> track -> report daily radar job."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
from typing import Callable

from quant.contracts import (
    load_json_object,
    validate_daily_radar_job,
    validate_daily_radar_report,
    validate_data_quality_summary,
)
from quant.data.universe import load_universe
from quant.scanner import (
    load_radar_profile,
    load_tracking_config,
    scan_us_daily,
    track_daily_radar,
    write_scan_artifact,
    write_tracking_artifact,
)
from quant.workspace import WorkspaceConfig


@dataclass(frozen=True)
class DailyJobRequest:
    profile: str | None
    job_date: str
    as_of: str | None = None
    skip_update: bool = False


@dataclass(frozen=True)
class StageResult:
    payload: dict | None = None
    details: dict | None = None
    artifacts: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DailyJobHandlers:
    update: Callable[[DailyJobRequest], StageResult]
    quality: Callable[[DailyJobRequest], StageResult]
    scan: Callable[[DailyJobRequest], StageResult]
    track: Callable[[DailyJobRequest, dict], StageResult]
    report: Callable[[DailyJobRequest, dict, dict], StageResult]


def run_daily_job(
    request: DailyJobRequest,
    workspace: WorkspaceConfig,
    *,
    handlers: DailyJobHandlers | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict:
    profile = load_radar_profile(workspace.radar_path, request.profile)
    normalized_date = _date(request.job_date)
    request = DailyJobRequest(profile.name, normalized_date, request.as_of, request.skip_update)
    state_path = _job_state_path(workspace, profile.name, normalized_date)
    state = _initial_state(request, state_path, now)
    if state_path.is_file():
        prior = load_json_object(state_path)
        validate_daily_radar_job(prior)
        if prior["job_id"] != state["job_id"]:
            raise ValueError("daily job state has a conflicting job_id")
        state["attempt"] = prior["attempt"] + 1
    active_handlers = handlers or _default_handlers(workspace, profile.name)
    payloads: dict[str, dict] = {}
    warning_messages: list[str] = []

    for stage_name in ("update", "quality", "scan", "track", "report"):
        if stage_name == "update" and request.skip_update:
            state["stages"][stage_name] = {
                "status": "SKIPPED",
                "started_at": _timestamp(now()),
                "finished_at": _timestamp(now()),
                "details": {"reason": "explicit --skip-update"},
                "artifacts": [],
                "warnings": [],
                "error": None,
            }
            _write_state(state, state_path)
            continue

        stage = state["stages"][stage_name]
        stage.update(status="RUNNING", started_at=_timestamp(now()), error=None)
        _write_state(state, state_path)
        try:
            if stage_name in {"update", "quality", "scan"}:
                result = getattr(active_handlers, stage_name)(request)
            elif stage_name == "track":
                result = active_handlers.track(request, payloads["scan"])
            else:
                result = active_handlers.report(request, payloads["scan"], payloads["track"])
        except Exception as exc:
            stage.update(
                status="FAILED",
                finished_at=_timestamp(now()),
                error=f"{type(exc).__name__}: {exc}",
            )
            state["status"] = "FAILED"
            state["failed_stage"] = stage_name
            state["finished_at"] = _timestamp(now())
            _write_state(state, state_path)
            return state

        if result.payload is not None:
            payloads[stage_name] = result.payload
        warnings = list(result.warnings)
        warning_messages.extend(f"{stage_name}: {message}" for message in warnings)
        stage.update(
            status="COMPLETED",
            finished_at=_timestamp(now()),
            details=result.details or {},
            artifacts=list(result.artifacts),
            warnings=warnings,
            error=None,
        )
        _write_state(state, state_path)

    state["status"] = "COMPLETED_WITH_WARNINGS" if warning_messages else "COMPLETED"
    state["warnings"] = warning_messages
    state["failed_stage"] = None
    state["finished_at"] = _timestamp(now())
    _write_state(state, state_path)
    return state


def _default_handlers(workspace: WorkspaceConfig, profile_name: str) -> DailyJobHandlers:
    workspace.apply()
    profile = load_radar_profile(workspace.radar_path, profile_name)
    tracking_config = load_tracking_config(workspace.radar_path)

    def update(request: DailyJobRequest) -> StageResult:
        command = [
            sys.executable,
            str(workspace.project_root / "scripts" / "update_data.py"),
            "--workspace",
            str(workspace.config_path),
            "--market",
            "us",
            "--universe",
            profile.universe_profile,
            "--end",
            request.as_of or request.job_date,
        ]
        completed = _run(command, workspace.project_root)
        return StageResult(details={"output_tail": _tail(completed.stdout)})

    def quality(request: DailyJobRequest) -> StageResult:
        command = [
            sys.executable,
            str(workspace.project_root / "scripts" / "check_data.py"),
            "--workspace",
            str(workspace.config_path),
            "--market",
            "us",
            "--quiet",
        ]
        completed = subprocess.run(
            command,
            cwd=workspace.project_root,
            text=True,
            capture_output=True,
            check=False,
        )
        try:
            payload = _last_json_object(completed.stdout)
        except RuntimeError:
            if completed.returncode != 0:
                raise RuntimeError(
                    f"data quality command failed ({completed.returncode}): "
                    f"{_tail(completed.stderr or completed.stdout)}"
                ) from None
            raise
        validate_data_quality_summary(payload)
        if completed.returncode != 0 or payload["summary"]["errors"]:
            raise RuntimeError(
                f"data quality failed with {payload['summary']['errors']} errors: "
                f"{_tail(completed.stderr or completed.stdout)}"
            )
        warnings = (
            (f"{payload['summary']['warnings']} quality warnings",)
            if payload["summary"]["warnings"]
            else ()
        )
        return StageResult(payload=payload, details=payload["summary"], warnings=warnings)

    def scan(request: DailyJobRequest) -> StageResult:
        universe = load_universe(profile.universe_profile)
        artifact = scan_us_daily(profile, universe["us"], as_of=request.as_of)
        path = (
            workspace.results_dir
            / "radar"
            / "us"
            / profile.name
            / artifact["signal_date"]
            / "scan.json"
        )
        write_scan_artifact(artifact, path)
        warnings = ("scan completed with unavailable symbols",) if artifact["status"] == "DEGRADED" else ()
        return StageResult(
            payload=artifact,
            details={"status": artifact["status"], **artifact["summary"]},
            artifacts=(str(path.resolve()),),
            warnings=warnings,
        )

    def track(request: DailyJobRequest, scan_artifact: dict) -> StageResult:
        root = workspace.results_dir / "radar" / "us" / profile.name
        scan_paths = sorted(root.glob("*/scan.json"))
        scans = [load_json_object(path) for path in scan_paths]
        path = root / "tracking.json"
        existing = load_json_object(path) if path.is_file() else None
        artifact = track_daily_radar(scans, tracking_config, existing=existing)
        write_tracking_artifact(artifact, path)
        warnings = (
            (f"{artifact['summary']['missing']} matured outcomes have missing prices",)
            if artifact["summary"]["missing"]
            else ()
        )
        return StageResult(
            payload=artifact,
            details=artifact["summary"],
            artifacts=(str(path.resolve()),),
            warnings=warnings,
        )

    def report(request: DailyJobRequest, scan_artifact: dict, tracking_artifact: dict) -> StageResult:
        artifact = build_daily_report(request.job_date, scan_artifact, tracking_artifact)
        root = workspace.results_dir / "radar" / "us" / profile.name / "reports"
        json_path = root / f"{request.job_date}.json"
        markdown_path = root / f"{request.job_date}.md"
        _write_json(artifact, json_path)
        _write_text(render_daily_report(artifact), markdown_path)
        return StageResult(
            payload=artifact,
            details=artifact["summary"],
            artifacts=(str(json_path.resolve()), str(markdown_path.resolve())),
        )

    return DailyJobHandlers(update, quality, scan, track, report)


def build_daily_report(job_date: str, scan: dict, tracking: dict) -> dict:
    horizons = {}
    for horizon in tracking["horizons"]:
        matured = [
            signal["outcomes"][str(horizon)]
            for signal in tracking["signals"]
            if signal["outcomes"][str(horizon)]["status"] == "MATURED"
        ]
        descriptive = [item["descriptive"]["return"] for item in matured]
        descriptive_excess = [item["descriptive"]["excess_return"] for item in matured]
        executable = [item["executable"]["net_return"] for item in matured]
        executable_excess = [item["executable"]["excess_net_return"] for item in matured]
        counts = tracking["summary"]["by_horizon"][str(horizon)]
        total = sum(counts.values())
        horizons[str(horizon)] = {
            "sample_count": len(matured),
            "descriptive_median_return": _median(descriptive),
            "descriptive_win_rate": _win_rate(descriptive),
            "descriptive_median_excess": _median(descriptive_excess),
            "descriptive_worst_return": min(descriptive) if descriptive else None,
            "executable_median_net_return": _median(executable),
            "executable_win_rate": _win_rate(executable),
            "executable_median_excess": _median(executable_excess),
            "executable_worst_net_return": min(executable) if executable else None,
            **counts,
            "pending_ratio": counts["pending"] / total if total else 0.0,
            "missing_ratio": counts["missing"] / total if total else 0.0,
            "delisted_ratio": counts["delisted"] / total if total else 0.0,
        }
    artifact = {
        "schema_version": 1,
        "artifact_type": "daily_radar_report",
        "market": "us",
        "profile": scan["profile"],
        "job_date": _date(job_date),
        "signal_date": scan["signal_date"],
        "latest_market_date": tracking["latest_market_date"],
        "scan_snapshot_sha256": scan["data_snapshot"]["sha256"],
        "tracking_snapshot_sha256": tracking["tracking_snapshot"]["sha256"],
        "summary": {
            "scan_status": scan["status"],
            "candidates": scan["summary"]["candidates_returned"],
            "signals_tracked": tracking["summary"]["signals"],
            "matured_outcomes": tracking["summary"]["matured"],
            "pending_outcomes": tracking["summary"]["pending"],
            "missing_outcomes": tracking["summary"]["missing"],
            "delisted_outcomes": tracking["summary"]["delisted"],
        },
        "candidates": [
            {"rank": item["rank"], "symbol": item["symbol"], "score": item["score"]}
            for item in scan["candidates"]
        ],
        "horizons": horizons,
    }
    return validate_daily_radar_report(artifact)


def render_daily_report(artifact: dict) -> str:
    summary = artifact["summary"]
    lines = [
        f"# {artifact['job_date']} 美股日线 Radar 报告",
        "",
        f"扫描交易日：{artifact['signal_date']}；最新基准交易日：{artifact['latest_market_date']}。",
        f"扫描状态：{summary['scan_status']}；候选 {summary['candidates']}；累计跟踪信号 {summary['signals_tracked']}。",
        "",
        "## 当日候选",
        "",
        "| 排名 | 标的 | 透明评分 |",
        "|---:|---|---:|",
    ]
    if artifact["candidates"]:
        lines.extend(
            f"| {item['rank']} | {item['symbol']} | {item['score']:.4f} |"
            for item in artifact["candidates"]
        )
    else:
        lines.append("| - | 无候选 | - |")
    lines.extend(
        [
            "",
            "## 后续表现",
            "",
            "| 期限 | 成熟样本 | 描述中位数 | 描述胜率 | 描述超额中位数 | 可执行净收益中位数 | 可执行胜率 | 最差可执行净收益 | 待成熟 | 缺失 | 退市 |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for horizon, item in artifact["horizons"].items():
        lines.append(
            f"| {horizon} | {item['sample_count']} | {_percent(item['descriptive_median_return'])} | "
            f"{_percent(item['descriptive_win_rate'])} | {_percent(item['descriptive_median_excess'])} | "
            f"{_percent(item['executable_median_net_return'])} | {_percent(item['executable_win_rate'])} | "
            f"{_percent(item['executable_worst_net_return'])} | {item['pending']} | {item['missing']} | {item['delisted']} |"
        )
    lines.extend(
        [
            "",
            "> 评分不是上涨概率；报告只描述已保存信号。未成熟不计入样本，缺失和退市不填 0。",
            "",
        ]
    )
    return "\n".join(lines)


def _initial_state(
    request: DailyJobRequest, state_path: Path, now: Callable[[], datetime]
) -> dict:
    raw = f"us|{request.profile}|{request.job_date}"
    job_id = "radar-daily-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
    stages = {
        name: {
            "status": "PENDING",
            "started_at": None,
            "finished_at": None,
            "details": {},
            "artifacts": [],
            "warnings": [],
            "error": None,
        }
        for name in ("update", "quality", "scan", "track", "report")
    }
    return {
        "schema_version": 1,
        "artifact_type": "daily_radar_job",
        "job_id": job_id,
        "market": "us",
        "profile": request.profile,
        "job_date": request.job_date,
        "requested_as_of": request.as_of,
        "skip_update": request.skip_update,
        "attempt": 1,
        "status": "RUNNING",
        "started_at": _timestamp(now()),
        "finished_at": None,
        "failed_stage": None,
        "state_path": str(state_path.resolve()),
        "warnings": [],
        "stages": stages,
    }


def _job_state_path(workspace: WorkspaceConfig, profile: str, job_date: str) -> Path:
    return workspace.results_dir / "radar" / "us" / profile / "jobs" / f"{job_date}.json"


def _write_state(state: dict, path: Path) -> None:
    validate_daily_radar_job(state)
    _write_json(state, path)


def _write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_text(content: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {_tail(completed.stderr or completed.stdout)}"
        )
    return completed


def _last_json_object(output: str) -> dict:
    for line in reversed(output.splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise RuntimeError("command did not emit a JSON object")


def _tail(output: str, limit: int = 500) -> str:
    return output.strip()[-limit:]


def _date(value: str) -> str:
    try:
        return str(datetime.fromisoformat(value).date())
    except (TypeError, ValueError):
        raise ValueError(f"invalid ISO job date: {value}") from None


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("daily job clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _median(values: list[float]) -> float | None:
    return round(float(statistics.median(values)), 8) if values else None


def _win_rate(values: list[float]) -> float | None:
    return round(sum(value > 0 for value in values) / len(values), 8) if values else None


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{value:.2%}"
