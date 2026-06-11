import pandas as pd
import pytest

from quant.data import storage


@pytest.fixture(autouse=True)
def tmp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)


def make_df(dates, close=10.0):
    return pd.DataFrame({
        "date": pd.to_datetime(dates),
        "open": close, "high": close + 1, "low": close - 1,
        "close": close, "volume": 1000,
    })


def test_save_and_load_roundtrip():
    df = make_df(["2024-01-02", "2024-01-03"])
    n = storage.save_daily("cn", "600519", df)
    assert n == 2
    loaded = storage.load_daily("cn", "600519")
    assert len(loaded) == 2
    assert list(loaded["date"]) == list(df["date"])


def test_incremental_merge_dedup():
    storage.save_daily("cn", "600519", make_df(["2024-01-02", "2024-01-03"], close=10))
    # 与已有数据重叠一天，且重叠日数值更新
    n = storage.save_daily("cn", "600519", make_df(["2024-01-03", "2024-01-04"], close=20))
    assert n == 3
    df = storage.load_daily("cn", "600519")
    assert df["date"].is_monotonic_increasing
    assert not df["date"].duplicated().any()
    # 重叠日保留新值
    overlap = df.loc[df["date"] == pd.Timestamp("2024-01-03"), "close"].iloc[0]
    assert overlap == 20


def test_save_empty_keeps_existing():
    storage.save_daily("us", "AAPL", make_df(["2024-01-02"]))
    n = storage.save_daily("us", "AAPL", pd.DataFrame())
    assert n == 1


def test_missing_columns_raises():
    bad = pd.DataFrame({"date": [pd.Timestamp("2024-01-02")], "close": [1.0]})
    with pytest.raises(ValueError):
        storage.save_daily("cn", "000001", bad)


def test_last_date():
    assert storage.last_date("cn", "999999") is None
    storage.save_daily("cn", "600036", make_df(["2024-01-02", "2024-01-05"]))
    assert storage.last_date("cn", "600036") == pd.Timestamp("2024-01-05")
