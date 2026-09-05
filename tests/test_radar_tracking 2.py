import copy

import pandas as pd
import pytest

from quant.contracts import ContractError, validate_daily_radar_tracking
from quant.scanner import RadarProfile, TrackingConfig, scan_us_daily, track_daily_radar


def make_frame(periods=90, *, last_signal_index=69, volume_spike=True):
    dates = pd.bdate_range("2026-01-02", periods=periods)
    close = pd.Series([100.0 + index for index in range(periods)])
    volume = pd.Series([1000.0] * periods)
    if volume_spike:
        volume.iloc[last_signal_index] = 3000.0
    return pd.DataFrame(
        {
            "date": dates,
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": volume,
            "source": "synthetic",
            "adjustment": "qfq",
            "volume_unit": "share",
        }
    )


def radar_profile():
    return RadarProfile(
        name="test",
        market="us",
        universe_profile="test",
        exclude_symbols=(),
        min_history=61,
        min_price=1.0,
        min_average_dollar_volume_20=0.0,
        min_volume_ratio_20=1.5,
        min_ret_5d=0.01,
        max_results=10,
    )


def tracking_config():
    return TrackingConfig("SPY", (1, 3, 5, 10, 20), 0.001, 0.001)


def make_scan(symbol_frame, signal_index=69):
    signal_date = str(symbol_frame.iloc[signal_index]["date"].date())
    return scan_us_daily(
        radar_profile(),
        ["AAA"],
        as_of=signal_date,
        loader=lambda market, symbol: symbol_frame,
    )


def test_tracking_matures_on_benchmark_sessions_with_separate_return_bases():
    symbol = make_frame(periods=75)
    benchmark = make_frame(periods=73, volume_spike=False)
    scan = make_scan(symbol)

    def loader(market, ticker):
        return benchmark if ticker == "SPY" else symbol

    artifact = track_daily_radar([scan], tracking_config(), loader=loader)
    signal = artifact["signals"][0]
    one_day = signal["outcomes"]["1"]
    three_day = signal["outcomes"]["3"]

    assert one_day["status"] == "MATURED"
    assert three_day["status"] == "MATURED"
    assert signal["outcomes"]["5"]["status"] == "PENDING"
    assert one_day["descriptive"]["basis"] == "signal_close_to_future_close"
    assert one_day["executable"]["basis"] == "next_session_open_to_future_close_after_fees"
    expected_gross = symbol.iloc[70]["close"] / symbol.iloc[70]["open"] - 1.0
    assert one_day["executable"]["gross_return"] == pytest.approx(expected_gross)
    assert one_day["executable"]["net_return"] < one_day["executable"]["gross_return"]
    assert "benchmark_return" in one_day["descriptive"]
    assert "excess_net_return" in one_day["executable"]


def test_tracking_is_idempotent_and_future_updates_do_not_rewrite_matured_horizon():
    symbol = make_frame(periods=73)
    benchmark = make_frame(periods=73, volume_spike=False)
    scan = make_scan(symbol)
    frames = {"AAA": symbol, "SPY": benchmark}
    loader = lambda market, ticker: frames[ticker]

    first = track_daily_radar([scan], tracking_config(), loader=loader)
    repeated = track_daily_radar([scan], tracking_config(), existing=first, loader=loader)
    assert repeated == first

    extended_symbol = make_frame(periods=80)
    extended_benchmark = make_frame(periods=80, volume_spike=False)
    extended_frames = {"AAA": extended_symbol, "SPY": extended_benchmark}
    updated = track_daily_radar(
        [scan],
        tracking_config(),
        existing=first,
        loader=lambda market, ticker: extended_frames[ticker],
    )
    assert updated["signals"][0]["outcomes"]["1"] == first["signals"][0]["outcomes"]["1"]
    assert updated["signals"][0]["outcomes"]["10"]["status"] == "MATURED"


def test_missing_symbol_bar_is_not_filled_or_counted_as_pending():
    symbol = make_frame(periods=75)
    benchmark = make_frame(periods=75, volume_spike=False)
    scan = make_scan(symbol)
    missing_date = symbol.iloc[72]["date"]
    symbol = symbol.loc[symbol["date"] != missing_date]

    artifact = track_daily_radar(
        [scan],
        tracking_config(),
        loader=lambda market, ticker: benchmark if ticker == "SPY" else symbol,
    )

    outcome = artifact["signals"][0]["outcomes"]["3"]
    assert outcome["status"] == "MISSING"
    assert outcome["descriptive"] == {
        "status": "MISSING",
        "reasons": ["missing_symbol_exit_close"],
    }
    assert artifact["summary"]["missing"] >= 1


def test_explicit_delisting_is_separate_from_missing_data():
    symbol = make_frame(periods=71)
    benchmark = make_frame(periods=75, volume_spike=False)
    scan = make_scan(symbol)
    final_trading_date = str(symbol.iloc[-1]["date"].date())
    config = TrackingConfig(
        "SPY",
        (1, 3, 5, 10, 20),
        0.001,
        0.001,
        (("AAA", final_trading_date),),
    )

    artifact = track_daily_radar(
        [scan],
        config,
        loader=lambda market, ticker: benchmark if ticker == "SPY" else symbol,
    )

    assert artifact["signals"][0]["outcomes"]["1"]["status"] == "MATURED"
    assert artifact["signals"][0]["outcomes"]["3"]["status"] == "DELISTED"
    assert artifact["signals"][0]["outcomes"]["3"]["final_trading_date"] == final_trading_date
    assert artifact["summary"]["delisted"] >= 1


def test_tracking_contract_rejects_duplicate_signal_ids():
    symbol = make_frame(periods=73)
    benchmark = make_frame(periods=73, volume_spike=False)
    scan = make_scan(symbol)
    artifact = track_daily_radar(
        [scan],
        tracking_config(),
        loader=lambda market, ticker: benchmark if ticker == "SPY" else symbol,
    )
    broken = copy.deepcopy(artifact)
    broken["signals"].append(copy.deepcopy(broken["signals"][0]))
    broken["summary"]["signals"] += 1
    broken["summary"]["outcomes"] += len(broken["horizons"])
    with pytest.raises(ContractError, match="duplicated"):
        validate_daily_radar_tracking(broken)
