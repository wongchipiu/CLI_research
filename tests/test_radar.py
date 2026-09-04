import json
from pathlib import Path

import pandas as pd
import pytest

from quant.cli import main
from quant.contracts import ContractError, validate_daily_radar_scan
from quant.features import FeatureUnavailable, compute_daily_radar_features
from quant.scanner import RadarError, RadarProfile, scan_us_daily


def make_frame(
    *,
    periods: int = 70,
    final_volume: float = 300.0,
    volume_unit: str = "share",
) -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-02", periods=periods)
    close = pd.Series([10.0 + index * 0.1 for index in range(periods)])
    volume = pd.Series([100.0] * periods)
    volume.iloc[-1] = final_volume
    return pd.DataFrame(
        {
            "date": dates,
            "open": close - 0.05,
            "high": close + 0.1,
            "low": close - 0.1,
            "close": close,
            "volume": volume,
            "source": "synthetic",
            "adjustment": "qfq",
            "volume_unit": volume_unit,
        }
    )


def profile(**overrides) -> RadarProfile:
    values = {
        "name": "test",
        "market": "us",
        "universe_profile": "test-universe",
        "exclude_symbols": (),
        "min_history": 61,
        "min_price": 1.0,
        "min_average_dollar_volume_20": 0.0,
        "min_volume_ratio_20": 1.5,
        "min_ret_5d": 0.01,
        "max_results": 20,
    }
    values.update(overrides)
    return RadarProfile(**values)


def test_features_exclude_current_volume_and_future_bars():
    frame = make_frame()
    signal_date = str(frame.iloc[-2]["date"].date())
    frame.loc[frame.index[-2], "volume"] = 250.0
    features = compute_daily_radar_features(frame, signal_date)

    assert features.volume_ratio_20 == pytest.approx(2.5)
    assert features.ret_5d == pytest.approx(
        frame.iloc[-2]["close"] / frame.iloc[-7]["close"] - 1.0
    )
    assert features.breakout_20 is True
    assert features.breakout_60 is True

    changed_future = frame.copy()
    changed_future.loc[changed_future.index[-1], ["close", "volume"]] = [9999.0, 999999.0]
    assert compute_daily_radar_features(changed_future, signal_date) == features


def test_features_require_a_normalized_volume_unit():
    with pytest.raises(FeatureUnavailable, match="volume_unit_not_share"):
        compute_daily_radar_features(make_frame(volume_unit="unknown"), "2026-04-09")


def test_scan_is_deterministic_ranked_and_explicitly_degraded_for_missing_data():
    frames = {
        "AAA": make_frame(final_volume=300.0),
        "BBB": make_frame(final_volume=300.0),
    }
    signal_date = str(frames["AAA"].iloc[-1]["date"].date())

    def loader(market, symbol):
        assert market == "us"
        return frames.get(symbol)

    first = scan_us_daily(profile(), ["BBB", "MISSING", "AAA"], as_of=signal_date, loader=loader)
    second = scan_us_daily(profile(), ["AAA", "BBB", "MISSING"], as_of=signal_date, loader=loader)

    assert first == second
    assert first["status"] == "DEGRADED"
    assert [item["symbol"] for item in first["candidates"]] == ["AAA", "BBB"]
    assert [item["rank"] for item in first["candidates"]] == [1, 2]
    assert first["candidates"][0]["score"] == first["candidates"][1]["score"]
    assert first["excluded"] == [{"symbol": "MISSING", "reasons": ["no_data"]}]
    assert first["candidates"][0]["signal_id"].startswith("radar-")


def test_scan_fails_when_the_watchlist_has_no_local_data():
    with pytest.raises(RadarError, match="no local daily data"):
        scan_us_daily(profile(), ["AAA"], loader=lambda market, symbol: None)


def test_no_candidate_is_an_ok_scan_not_a_data_failure():
    frame = make_frame(final_volume=100.0)
    signal_date = str(frame.iloc[-1]["date"].date())
    artifact = scan_us_daily(
        profile(), ["AAA"], as_of=signal_date, loader=lambda market, symbol: frame
    )

    assert artifact["status"] == "OK"
    assert artifact["candidates"] == []
    assert artifact["excluded"][0]["reasons"] == ["volume_ratio_below_threshold"]


def test_radar_contract_rejects_nonconsecutive_ranks():
    frame = make_frame()
    signal_date = str(frame.iloc[-1]["date"].date())
    artifact = scan_us_daily(
        profile(), ["AAA"], as_of=signal_date, loader=lambda market, symbol: frame
    )
    artifact["candidates"][0]["rank"] = 2
    with pytest.raises(ContractError, match="ranks"):
        validate_daily_radar_scan(artifact)


def test_scan_cli_writes_a_versioned_artifact(tmp_path: Path, capsys):
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data" / "daily" / "us"
    config_dir.mkdir()
    data_dir.mkdir(parents=True)
    (tmp_path / "scripts").symlink_to(
        Path(__file__).resolve().parents[1] / "scripts", target_is_directory=True
    )
    frame = make_frame()
    frame.to_parquet(data_dir / "AAA.parquet", index=False)
    frame.to_parquet(data_dir / "SPY.parquet", index=False)
    (config_dir / "universe.yaml").write_text(
        "default_profile: test\nprofiles:\n  test:\n    us: [AAA]\n    cn: []\n    cn_index: []\n",
        encoding="utf-8",
    )
    (config_dir / "radar.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                "artifact_type: daily_radar_config",
                "default_profile: test",
                "tracking:",
                "  benchmark: SPY",
                "  horizons: [1, 3, 5, 10, 20]",
                "  buy_fee: 0.001",
                "  sell_fee: 0.001",
                "profiles:",
                "  test:",
                "    market: us",
                "    universe_profile: test",
                "    exclude_symbols: []",
                "    min_history: 61",
                "    min_price: 1",
                "    min_average_dollar_volume_20: 0",
                "    min_volume_ratio_20: 1.5",
                "    min_ret_5d: 0.01",
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

    assert main(["scan", "--workspace", str(workspace), "--market", "us"]) == 0
    output = json.loads(capsys.readouterr().out)
    artifact_path = (
        tmp_path / "results" / "radar" / "us" / "test" / output["signal_date"] / "scan.json"
    )
    assert artifact_path.is_file()
    assert json.loads(artifact_path.read_text(encoding="utf-8"))["artifact_type"] == "daily_radar_scan"

    assert main(
        [
            "signals",
            "track",
            "--workspace",
            str(workspace),
            "--market",
            "us",
            "--scan",
            str(artifact_path),
        ]
    ) == 0
    tracking_output = json.loads(capsys.readouterr().out)
    tracking_path = tmp_path / "results" / "radar" / "us" / "test" / "tracking.json"
    assert tracking_path.is_file()
    assert tracking_output["artifact_type"] == "daily_radar_tracking"
    assert tracking_output["summary"]["pending"] == 5

    signal_date = output["signal_date"]
    daily_args = [
        "daily",
        "--workspace",
        str(workspace),
        "--market",
        "us",
        "--profile",
        "test",
        "--job-date",
        "2026-08-30",
        "--as-of",
        signal_date,
        "--skip-update",
    ]
    assert main(daily_args) == 2
    daily_output = json.loads(capsys.readouterr().out)
    assert daily_output["status"] == "COMPLETED_WITH_WARNINGS"
    assert daily_output["stages"]["update"]["status"] == "SKIPPED"
    assert daily_output["stages"]["report"]["status"] == "COMPLETED"
    report_root = tmp_path / "results" / "radar" / "us" / "test" / "reports"
    assert (report_root / "2026-08-30.json").is_file()
    assert (report_root / "2026-08-30.md").is_file()

    assert main(daily_args) == 2
    repeated = json.loads(capsys.readouterr().out)
    assert repeated["job_id"] == daily_output["job_id"]
    assert repeated["attempt"] == 2
    assert json.loads(tracking_path.read_text(encoding="utf-8"))["summary"]["signals"] == 1
