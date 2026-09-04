"""Aligned raw opening/closing quotes and separate point-in-time eligibility."""
from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

from quant.data import storage
from quant.data.membership import apply_membership, load_membership
from quant.data.universe import load_universe


@dataclass(frozen=True)
class MarketBars:
    open: pd.DataFrame
    close: pd.DataFrame
    eligible: pd.DataFrame
    benchmark_open: pd.Series | None
    benchmark_close: pd.Series | None
    benchmark_name: str
    universe: dict

    @property
    def signal_close(self) -> pd.DataFrame:
        return self.close.where(self.eligible)


def load_market_bars(market: str, profile: str | None = None,
                     membership_file: str | None = None) -> MarketBars:
    universe = load_universe(profile)
    history = load_membership(membership_file, market) if membership_file else None
    if market == "cn":
        symbols = history.symbols if history else universe["cn"]
        benchmark_market, benchmark_symbol = "cn-index", universe["cn_index"][0]
    elif market == "us":
        benchmark_symbol = "SPY"
        symbols = history.symbols if history else [s for s in universe["us"] if s != benchmark_symbol]
        benchmark_market = "us"
    else:
        raise ValueError(f"unsupported market: {market}")
    frames = {}
    for symbol in symbols:
        frame = storage.load_daily(market, symbol)
        if frame is not None and not frame.empty:
            frames[symbol] = frame.set_index("date")
    if not frames:
        raise ValueError(f"no local data for {market}/{universe['profile']}")
    missing = set(symbols) - set(frames)
    if missing:
        raise ValueError(f"missing local history for members: {sorted(missing)}")
    close = pd.DataFrame({s: f["close"] for s, f in frames.items()}).sort_index()
    opens = pd.DataFrame({s: f.get("open", pd.Series(dtype=float)) for s, f in frames.items()})
    benchmark_frame = storage.load_daily(benchmark_market, benchmark_symbol)
    benchmark_open = benchmark_close = None
    if benchmark_frame is not None and not benchmark_frame.empty:
        benchmark_frame = benchmark_frame.set_index("date").sort_index()
        # Include known market sessions where every member has missing quotes.
        sessions = close.index.union(benchmark_frame.index).sort_values()
        sessions = sessions[(sessions >= close.index.min()) & (sessions <= close.index.max())]
        close = close.reindex(sessions)
        benchmark_close = benchmark_frame["close"].reindex(sessions)
        benchmark_open = benchmark_frame.get("open", pd.Series(dtype=float)).reindex(sessions)
    opens = opens.reindex(index=close.index, columns=close.columns)
    eligible = pd.DataFrame(True, index=close.index, columns=close.columns)
    if history:
        eligible = apply_membership(eligible.astype(float), history).notna()
        universe.update(point_in_time=True, membership_file=str(history.path), membership_sha256=history.sha256)
    # Eligibility controls signals, not valuation: removed members can still be sold.
    return MarketBars(opens, close, eligible, benchmark_open, benchmark_close, benchmark_symbol, universe)


def load_market_close(market: str, profile: str | None = None,
                      membership_file: str | None = None) -> tuple[pd.DataFrame, pd.Series | None, str, dict]:
    bars = load_market_bars(market, profile, membership_file)
    return bars.signal_close, bars.benchmark_close, bars.benchmark_name, bars.universe
