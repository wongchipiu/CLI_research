"""Parquet 本地存储：data/daily/<market>/<symbol>.parquet

统一行情 schema（按列名约定，date 为升序、无重复）：
    date(datetime64) open high low close volume [amount]
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[3] / "data"

REQUIRED_COLS = ["date", "open", "high", "low", "close", "volume"]


def daily_path(market: str, symbol: str) -> Path:
    return DATA_DIR / "daily" / market / f"{symbol}.parquet"


def load_daily(market: str, symbol: str) -> pd.DataFrame | None:
    p = daily_path(market, symbol)
    if not p.exists():
        return None
    return pd.read_parquet(p)


def save_daily(market: str, symbol: str, df: pd.DataFrame) -> int:
    """增量合并写入，按 date 去重（保留新数据），返回合并后总行数。"""
    if df.empty:
        existing = load_daily(market, symbol)
        return 0 if existing is None else len(existing)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{market}/{symbol} 缺少列: {missing}")
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])

    existing = load_daily(market, symbol)
    if existing is not None:
        df = pd.concat([existing, df], ignore_index=True)
    df = (
        df.drop_duplicates(subset="date", keep="last")
        .sort_values("date")
        .reset_index(drop=True)
    )

    p = daily_path(market, symbol)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    return len(df)


def last_date(market: str, symbol: str) -> pd.Timestamp | None:
    df = load_daily(market, symbol)
    if df is None or df.empty:
        return None
    return pd.to_datetime(df["date"]).max()
