from datetime import datetime, timezone
from pathlib import Path

from quant.jobs import DailyJobHandlers, DailyJobRequest, StageResult, run_daily_job
from quant.jobs.daily import build_daily_report, render_daily_report
from quant.workspace import WorkspaceConfig


def make_workspace(tmp_path: Path) -> WorkspaceConfig:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "universe.yaml").write_text(
        "default_profile: test\nprofiles:\n  test:\n    us: [AAA, SPY]\n    cn: []\n    cn_index: []\n",
        encoding="utf-8",
    )
    (config_dir / "radar.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                "artifact_type: daily_radar_config",
                "default_profile: test",
                "profiles:",
                "  test:",
                "    market: us",
                "    universe_profile: test",
                "    exclude_symbols: [SPY]",
                "    min_history: 61",
                "    min_price: 1",
                "    min_average_dollar_volume_20: 0",
                "    min_volume_ratio_20: 1",
                "    min_ret_5d: 0",
                "    max_results: 10",
            ]
        ),
        encoding="utf-8",
    )
    gpt_root = Path(__file__).resolve().parents[2] / "gpt_quant"
    workspace = config_dir / "workspace.yaml"
    workspace.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "artifact_type: quant_workspace_config",
                "project_root: ..",
                "paths:",
                "  data: data",
                "  results: results",
                "  studies: var/studies",
                "  universe: config/universe.yaml",
                "  radar: config/radar.yaml",
                f"  gpt_quant: {gpt_root}",
            ]
        ),
        encoding="utf-8",
    )
    return WorkspaceConfig.load(workspace)


def fixed_now():
    return datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def successful_handlers(calls, *, warnings=()):
    def update(request):
        calls.append("update")
        return StageResult(details={"updated": True})

    def quality(request):
        calls.append("quality")
        return StageResult(payload={"quality": True}, warnings=warnings)

    def scan(request):
        calls.append("scan")
        return StageResult(payload={"scan": True}, artifacts=("scan.json",))

    def track(request, scan_payload):
        assert scan_payload == {"scan": True}
        calls.append("track")
        return StageResult(payload={"track": True}, artifacts=("tracking.json",))

    def report(request, scan_payload, tracking_payload):
        assert tracking_payload == {"track": True}
        calls.append("report")
        return StageResult(payload={"report": True}, artifacts=("report.md",))

    return DailyJobHandlers(update, quality, scan, track, report)


def test_daily_job_same_date_rerun_is_same_job_and_new_attempt(tmp_path):
    workspace = make_workspace(tmp_path)
    calls = []
    request = DailyJobRequest("test", "2026-08-30")

    first = run_daily_job(
        request, workspace, handlers=successful_handlers(calls), now=fixed_now
    )
    second = run_daily_job(
        request, workspace, handlers=successful_handlers(calls), now=fixed_now
    )

    assert first["status"] == "COMPLETED"
    assert second["status"] == "COMPLETED"
    assert second["job_id"] == first["job_id"]
    assert second["attempt"] == 2
    assert calls == ["update", "quality", "scan", "track", "report"] * 2
    assert Path(second["state_path"]).is_file()


def test_daily_job_persists_failure_and_can_retry(tmp_path):
    workspace = make_workspace(tmp_path)
    calls = []
    handlers = successful_handlers(calls)

    def fail_track(request, scan_payload):
        raise RuntimeError("synthetic tracking failure")

    failed_handlers = DailyJobHandlers(
        handlers.update, handlers.quality, handlers.scan, fail_track, handlers.report
    )
    request = DailyJobRequest("test", "2026-08-30", skip_update=True)
    failed = run_daily_job(request, workspace, handlers=failed_handlers, now=fixed_now)

    assert failed["status"] == "FAILED"
    assert failed["failed_stage"] == "track"
    assert failed["stages"]["update"]["status"] == "SKIPPED"
    assert failed["stages"]["report"]["status"] == "PENDING"

    recovered = run_daily_job(
        request, workspace, handlers=successful_handlers([]), now=fixed_now
    )
    assert recovered["status"] == "COMPLETED"
    assert recovered["attempt"] == 2


def test_daily_job_warning_is_visible_without_failing_later_stages(tmp_path):
    workspace = make_workspace(tmp_path)
    state = run_daily_job(
        DailyJobRequest("test", "2026-08-30"),
        workspace,
        handlers=successful_handlers([], warnings=("stale local data",)),
        now=fixed_now,
    )

    assert state["status"] == "COMPLETED_WITH_WARNINGS"
    assert state["warnings"] == ["quality: stale local data"]
    assert state["stages"]["report"]["status"] == "COMPLETED"


def test_daily_report_excludes_pending_and_missing_from_statistics():
    matured = {
        "status": "MATURED",
        "descriptive": {"return": 0.10, "excess_return": 0.03},
        "executable": {"net_return": 0.08, "excess_net_return": 0.02},
    }
    pending = {"status": "PENDING", "descriptive": None, "executable": None}
    scan = {
        "profile": "test",
        "signal_date": "2026-08-28",
        "status": "OK",
        "data_snapshot": {"sha256": "a" * 64},
        "summary": {"candidates_returned": 1},
        "candidates": [{"rank": 1, "symbol": "AAA", "score": 42.0}],
    }
    tracking = {
        "horizons": [1, 3],
        "latest_market_date": "2026-08-31",
        "tracking_snapshot": {"sha256": "b" * 64},
        "summary": {
            "signals": 1,
            "matured": 1,
            "pending": 1,
            "missing": 0,
            "delisted": 0,
            "by_horizon": {
                "1": {"matured": 1, "pending": 0, "missing": 0, "delisted": 0},
                "3": {"matured": 0, "pending": 1, "missing": 0, "delisted": 0},
            },
        },
        "signals": [{"outcomes": {"1": matured, "3": pending}}],
    }

    report = build_daily_report("2026-08-30", scan, tracking)

    assert report["horizons"]["1"]["sample_count"] == 1
    assert report["horizons"]["1"]["executable_median_net_return"] == 0.08
    assert report["horizons"]["3"]["sample_count"] == 0
    assert report["horizons"]["3"]["executable_median_net_return"] is None
    assert "未成熟不计入样本" in render_daily_report(report)
