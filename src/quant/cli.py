"""Unified deterministic entry point for the cross-project research workflow."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Sequence
from zoneinfo import ZoneInfo

from quant.adapters import IntegrationError
from quant.contracts import ContractError, load_json_object
from quant.data.universe import load_universe
from quant.jobs import DailyJobRequest, run_daily_job
from quant.scanner import (
    RadarConfigError,
    RadarError,
    TrackingError,
    load_radar_profile,
    load_tracking_config,
    scan_us_daily,
    track_daily_radar,
    write_scan_artifact,
    write_tracking_artifact,
)
from quant.services.workflow import WorkflowError, WorkflowRequest, run_workflow
from quant.workspace import DEFAULT_CONFIG, WorkspaceConfig, WorkspaceConfigError


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quant")
    subparsers = parser.add_subparsers(dest="command", required=True)
    workflow = subparsers.add_parser("workflow", help="quality summary -> study -> gpt_quant validation")
    workflow.add_argument("--workspace", type=Path, default=DEFAULT_CONFIG)
    workflow.add_argument("--strategy", required=True)
    workflow.add_argument("--market", required=True, choices=("cn", "us"))
    workflow.add_argument("--universe")
    workflow.add_argument("--membership-file")
    workflow.add_argument("--start")
    workflow.add_argument("--end")
    workflow.add_argument("--study-file", required=True)
    workflow.add_argument("--train-ratio", type=float, default=0.6)
    workflow.add_argument("--validation-ratio", type=float, default=0.2)
    workflow.add_argument("--train-end")
    workflow.add_argument("--final-start")
    workflow.add_argument("--walk-forward", action="store_true")
    workflow.add_argument("--wf-train-days", type=int, default=756)
    workflow.add_argument("--wf-test-days", type=int, default=126)
    workflow.add_argument("--max-position-weight", type=float, default=1.0)
    workflow.add_argument("--max-gross-exposure", type=float, default=1.0)
    workflow.add_argument("--target-volatility", type=float)
    workflow.add_argument("--volatility-window", type=int, default=20)
    workflow.add_argument("--regime-window", type=int)
    workflow.add_argument("--risk-off-exposure", type=float, default=0.0)
    workflow.add_argument("-p", "--param", action="append", default=[])
    scan = subparsers.add_parser("scan", help="deterministic US daily watchlist radar")
    scan.add_argument("--workspace", type=Path, default=DEFAULT_CONFIG)
    scan.add_argument("--market", required=True, choices=("us",))
    scan.add_argument("--profile")
    scan.add_argument("--as-of", help="signal date; defaults to the latest loaded watchlist bar")
    scan.add_argument("--output", type=Path, help="JSON output path; defaults under results/radar/")
    signals = subparsers.add_parser("signals", help="persist and evaluate radar signals")
    signal_commands = signals.add_subparsers(dest="signals_command", required=True)
    track = signal_commands.add_parser("track", help="mature 1/3/5/10/20-session outcomes")
    track.add_argument("--workspace", type=Path, default=DEFAULT_CONFIG)
    track.add_argument("--market", required=True, choices=("us",))
    track.add_argument("--profile")
    track.add_argument(
        "--scan",
        type=Path,
        action="append",
        default=[],
        help="daily_radar_scan JSON; repeatable, defaults to discovered profile scans",
    )
    track.add_argument("--output", type=Path, help="tracking JSON output path")
    daily = subparsers.add_parser("daily", help="retryable update -> quality -> scan -> track -> report")
    daily.add_argument("--workspace", type=Path, default=DEFAULT_CONFIG)
    daily.add_argument("--market", required=True, choices=("us",))
    daily.add_argument("--profile")
    daily.add_argument(
        "--job-date",
        default=datetime.now(ZoneInfo("America/New_York")).date().isoformat(),
        help="idempotency/report date in YYYY-MM-DD; defaults to current New York date",
    )
    daily.add_argument("--as-of", help="optional radar signal date and update end date")
    daily.add_argument(
        "--skip-update",
        action="store_true",
        help="explicit offline/replay mode; uses existing local data",
    )
    args = parser.parse_args(argv)

    try:
        config = WorkspaceConfig.load(args.workspace)
        if args.command == "workflow":
            output = run_workflow(
                WorkflowRequest(
                    strategy=args.strategy,
                    market=args.market,
                    params=tuple(args.param),
                    study_file=args.study_file,
                    universe=args.universe,
                    membership_file=args.membership_file,
                    start=args.start,
                    end=args.end,
                    train_ratio=args.train_ratio,
                    validation_ratio=args.validation_ratio,
                    train_end=args.train_end,
                    final_start=args.final_start,
                    walk_forward=args.walk_forward,
                    wf_train_days=args.wf_train_days,
                    wf_test_days=args.wf_test_days,
                    max_position_weight=args.max_position_weight,
                    max_gross_exposure=args.max_gross_exposure,
                    target_volatility=args.target_volatility,
                    volatility_window=args.volatility_window,
                    regime_window=args.regime_window,
                    risk_off_exposure=args.risk_off_exposure,
                ),
                config,
            )
            print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
            return 2 if output["decision"] == "BLOCKED" else 0

        if args.command == "daily":
            output = run_daily_job(
                DailyJobRequest(
                    profile=args.profile,
                    job_date=args.job_date,
                    as_of=args.as_of,
                    skip_update=args.skip_update,
                ),
                config,
            )
            print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
            return 0 if output["status"] == "COMPLETED" else 2

        config.apply()
        profile = load_radar_profile(config.radar_path, args.profile)
        if args.command == "scan":
            universe = load_universe(profile.universe_profile)
            output = scan_us_daily(profile, universe["us"], as_of=args.as_of)
            output_path = (
                config.resolve_project_path(args.output)
                if args.output
                else config.results_dir
                / "radar"
                / "us"
                / profile.name
                / output["signal_date"]
                / "scan.json"
            )
            saved = write_scan_artifact(output, output_path)
            print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
            print(f"saved radar artifact: {saved}", file=sys.stderr)
            return 2 if output["status"] == "DEGRADED" else 0

        tracking_config = load_tracking_config(config.radar_path)
        output_path = (
            config.resolve_project_path(args.output)
            if args.output
            else config.results_dir / "radar" / "us" / profile.name / "tracking.json"
        )
        scan_paths = (
            [config.resolve_project_path(path) for path in args.scan]
            if args.scan
            else sorted(
                (config.results_dir / "radar" / "us" / profile.name).glob("*/scan.json")
            )
        )
        if not scan_paths:
            raise TrackingError(f"no radar scan artifacts found for profile {profile.name}")
        scan_artifacts = [load_json_object(path) for path in scan_paths]
        existing = load_json_object(output_path) if output_path.is_file() else None
        output = track_daily_radar(scan_artifacts, tracking_config, existing=existing)
        saved = write_tracking_artifact(output, output_path)
        print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
        print(f"saved tracking artifact: {saved}", file=sys.stderr)
        return 2 if output["summary"]["missing"] else 0
    except (
        WorkspaceConfigError,
        WorkflowError,
        ContractError,
        IntegrationError,
        RadarConfigError,
        RadarError,
        TrackingError,
        ValueError,
    ) as exc:
        parser.error(str(exc))
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
