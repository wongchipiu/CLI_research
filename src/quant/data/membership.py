"""Point-in-time universe membership schema and masking."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = ["market", "symbol", "effective_from", "effective_to"]


@dataclass(frozen=True)
class MembershipHistory:
    path: Path
    market: str
    rows: pd.DataFrame
    sha256: str

    @property
    def symbols(self) -> list[str]:
        return sorted(self.rows["symbol"].unique().tolist())


def load_membership(path: str | Path, market: str) -> MembershipHistory:
    source = Path(path)
    raw = source.read_bytes()
    frame = pd.read_csv(source, dtype={"symbol": str, "market": str})
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"membership history missing columns: {missing}")
    rows = frame.loc[frame["market"].str.lower() == market.lower(), REQUIRED_COLUMNS].copy()
    if rows.empty:
        raise ValueError(f"membership history has no rows for market {market}")
    rows["symbol"] = rows["symbol"].str.upper()
    if market == "cn":
        rows["symbol"] = rows["symbol"].str.zfill(6)
    rows["effective_from"] = pd.to_datetime(rows["effective_from"])
    rows["effective_to"] = pd.to_datetime(rows["effective_to"], errors="coerce")
    if (rows["effective_to"].notna() & (rows["effective_to"] < rows["effective_from"])).any():
        raise ValueError("membership effective_to cannot precede effective_from")
    for symbol, group in rows.sort_values("effective_from").groupby("symbol"):
        previous_end = None
        for item in group.itertuples():
            if previous_end is None:
                previous_end = item.effective_to
                continue
            if pd.isna(previous_end) or item.effective_from <= previous_end:
                raise ValueError(f"overlapping membership intervals for {symbol}")
            previous_end = item.effective_to
    return MembershipHistory(source.resolve(), market, rows, hashlib.sha256(raw).hexdigest())


def apply_membership(close: pd.DataFrame, history: MembershipHistory) -> pd.DataFrame:
    masked = close.copy()
    for symbol in masked.columns:
        active = pd.Series(False, index=masked.index)
        rows = history.rows.loc[history.rows["symbol"] == symbol]
        for row in rows.itertuples():
            interval = masked.index >= row.effective_from
            if pd.notna(row.effective_to):
                interval &= masked.index <= row.effective_to
            active |= interval
        masked.loc[~active, symbol] = pd.NA
    return masked
