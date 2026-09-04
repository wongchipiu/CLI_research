"""Fetch a US stock and print a compact event-aware price summary.

Example:
    uv run python scripts/analyze_stock_event.py --symbol COHR \
      --event-date 2026-08-12 --peer LITE --peer AAOI
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant.data.fetchers import fetch_us_daily
from quant.research.event_analysis import analyze_event, peer_snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--benchmark", default="SPY")
    parser.add_argument("--peer", action="append", default=[])
    parser.add_argument("--event-date", required=True)
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    frames = {}
    for symbol in [args.symbol, args.benchmark, *args.peer]:
        frames[symbol.upper()] = fetch_us_daily(symbol.upper(), args.start, args.end)
        if frames[symbol.upper()].empty:
            parser.error(f"no price data returned for {symbol}")

    result = analyze_event(
        frames[args.symbol.upper()],
        frames[args.benchmark.upper()],
        symbol=args.symbol,
        benchmark_symbol=args.benchmark,
        event_date=args.event_date,
    )
    result["peers"] = [
        peer_snapshot(frames[symbol.upper()], symbol) for symbol in args.peer
    ]
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
