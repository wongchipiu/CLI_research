"""Parquet 本地存储：data/daily/<market>/<symbol>.parquet

统一行情 schema（按列名约定，date 为升序、无重复）：
    date(datetime64) open high low close volume [amount]
    [source adjustment volume_unit volume_scale_applied]

volume 入库后一律为“股”。东财返回“手”时乘以 100；旧数据若有 amount，
通过 amount / (volume * close) 的稳健中位数识别量纲并迁移。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[3] / "data"

REQUIRED_COLS = ["date", "open", "high", "low", "close", "volume"]
METADATA_COLS = ["source", "adjustment", "volume_unit", "volume_scale_applied"]


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
    df = normalize_volume(df, market=market)
    df["date"] = pd.to_datetime(df["date"])

    existing = load_daily(market, symbol)
    if existing is not None:
        existing = normalize_volume(existing, market=market)
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


def normalize_volume(df: pd.DataFrame, market: str | None = None) -> pd.DataFrame:
    """Return a copy whose volume is expressed in shares with provenance metadata."""
    out = df.copy()
    if out.empty or "volume" not in out.columns:
        return out

    if "source" not in out.columns:
        out["source"] = "legacy_unknown"
    if "adjustment" not in out.columns:
        out["adjustment"] = "qfq_unknown"

    explicit_lot = pd.Series(False, index=out.index)
    if "volume_unit" in out.columns:
        explicit_lot = out["volume_unit"].astype(str).str.lower().eq("lot")

    inferred_lot = False
    has_explicit_unit = "volume_unit" in out.columns and out["volume_unit"].notna().any()
    if not has_explicit_unit and "amount" in out.columns:
        denominator = out["volume"] * out["close"]
        ratio = (out["amount"] / denominator.where(denominator > 0)).replace(
            [float("inf"), float("-inf")], pd.NA
        ).dropna()
        if not ratio.empty:
            inferred_lot = 50.0 <= float(ratio.median()) <= 150.0

    scale = pd.Series(1.0, index=out.index)
    scale.loc[explicit_lot] = 100.0
    if inferred_lot:
        scale[:] = 100.0
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce") * scale
    out["volume_scale_applied"] = scale
    known_daily_market = market in {"cn", "cn-index", "us"}
    out["volume_unit"] = (
        "share" if (has_explicit_unit or "amount" in out.columns or known_daily_market) else "unknown"
    )
    return out


def last_date(market: str, symbol: str) -> pd.Timestamp | None:
    df = load_daily(market, symbol)
    if df is None or df.empty:
        return None
    return pd.to_datetime(df["date"]).max()
