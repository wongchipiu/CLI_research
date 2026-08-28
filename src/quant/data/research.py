"""Load aligned raw close matrices; missing quotes remain non-tradeable.

The backtest engine forward-fills a separate valuation matrix. Filling here
would lose the missing-quote mask and permit trades at stale prices.
"""

from __future__ import annotations

import pandas as pd

from quant.data import storage
from quant.data.membership import apply_membership, load_membership
from quant.data.universe import load_universe


def load_market_close(
    market: str,
    profile: str | None = None,
    membership_file: str | None = None,
) -> tuple[pd.DataFrame, pd.Series | None, str, dict]:
    universe = load_universe(profile)
    history = load_membership(membership_file, market) if membership_file else None
    if market == "cn":
        symbols = history.symbols if history else universe["cn"]
        benchmark_market, benchmark_symbol = "cn-index", universe["cn_index"][0]
    elif market == "us":
        benchmark_symbol = "SPY"
        symbols = history.symbols if history else [symbol for symbol in universe["us"] if symbol != benchmark_symbol]
        benchmark_market = "us"
    else:
        raise ValueError(f"unsupported market: {market}")

    frames = {}
    for symbol in symbols:
        frame = storage.load_daily(market, symbol)
        if frame is not None and not frame.empty:
            frames[symbol] = frame.set_index("date")["close"]
    if not frames:
        raise ValueError(f"no local data for {market}/{universe['profile']}")
    missing_symbols = set(symbols) - set(frames)
    if missing_symbols:
        raise ValueError(f"missing local history for point-in-time members: {sorted(missing_symbols)}")
    close = pd.DataFrame(frames).sort_index()
    if history:
        close = apply_membership(close, history)
        universe["point_in_time"] = True
        universe["membership_file"] = str(history.path)
        universe["membership_sha256"] = history.sha256
    benchmark_frame = storage.load_daily(benchmark_market, benchmark_symbol)
    benchmark = None
    if benchmark_frame is not None and not benchmark_frame.empty:
        benchmark = benchmark_frame.set_index("date")["close"].reindex(close.index).ffill()
    return close, benchmark, benchmark_symbol, universe
