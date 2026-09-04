import pandas as pd
import pytest

from quant.backtest.engine import MarketConfig, run
from quant.data import research, storage, universe as universe_config


def test_load_market_close_preserves_missing_quotes_for_execution(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        research,
        "load_universe",
        lambda profile=None: {
            "profile": "test", "as_of": "2026-01-01",
            "cn": [], "cn_index": [], "us": ["A", "B", "SPY"],
        },
    )
    for symbol, dates in {
        "A": ["2026-01-05", "2026-01-06", "2026-01-07"],
        "B": ["2026-01-05", "2026-01-07"],
        "SPY": ["2026-01-05", "2026-01-06", "2026-01-07"],
    }.items():
        frame = pd.DataFrame({
            "date": pd.to_datetime(dates), "open": 10, "high": 10,
            "low": 10, "close": 10, "volume": 100,
        })
        storage.save_daily("us", symbol, frame)
    close, benchmark, benchmark_name, universe = research.load_market_close("us", "test")
    assert pd.isna(close.loc[pd.Timestamp("2026-01-06"), "B"])
    assert benchmark_name == "SPY"
    assert benchmark is not None
    assert universe["profile"] == "test"

    # 即使策略要求换仓，缺报价期间也不能出售 B 为 A 提供资金。
    decision = pd.DataFrame({"A": [0.0, 1.0, 1.0], "B": [1.0, 0.0, 0.0]}, index=close.index)
    result = run(close, decision, MarketConfig(buy_cost=0.0, sell_cost=0.0, limit_pct=None), execution_model="legacy_same_close")
    assert result.weights.iloc[1].to_dict() == pytest.approx({"A": 0.0, "B": 1.0})
    assert result.weights.iloc[2].to_dict() == pytest.approx({"A": 1.0, "B": 0.0})
    assert result.nav.tolist() == pytest.approx([1.0, 1.0, 1.0])


@pytest.mark.parametrize("config_text,profile", [
    ("us: [a, SPY]\n", "default"),
    ("default_profile: baseline\nprofiles:\n  baseline:\n    us: [a, SPY]\n", "baseline"),
])
def test_market_loader_accepts_legacy_and_profile_universe_files(tmp_path, monkeypatch, config_text, profile):
    config_path = tmp_path / "universe.yaml"
    config_path.write_text(config_text, encoding="utf-8")
    monkeypatch.setattr(universe_config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path / "bars")
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-05"]), "open": 10, "high": 10,
        "low": 10, "close": 10, "volume": 100,
    })
    for symbol in ("A", "SPY"):
        storage.save_daily("us", symbol, frame)

    close, benchmark, name, metadata = research.load_market_close("us")
    assert close.columns.tolist() == ["A"]
    assert benchmark.iloc[0] == 10
    assert name == "SPY"
    assert metadata["profile"] == profile


def test_removed_member_keeps_execution_quotes_but_loses_signal_eligibility(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path / "bars")
    monkeypatch.setattr(research, "load_universe", lambda profile=None: {"profile": "test", "us": ["A", "SPY"]})
    history = tmp_path / "members.csv"
    history.write_text("market,symbol,effective_from,effective_to\nus,A,2026-01-05,2026-01-05\n")
    frame = pd.DataFrame({"date": pd.to_datetime(["2026-01-05", "2026-01-06"]),
                          "open": 10., "high": 10., "low": 10., "close": 10., "volume": 100})
    storage.save_daily("us", "A", frame)
    bars = research.load_market_bars("us", membership_file=str(history))
    assert not bars.eligible.iloc[-1, 0]
    assert pd.isna(bars.signal_close.iloc[-1, 0])
    assert bars.open.iloc[-1, 0] == bars.close.iloc[-1, 0] == 10.
