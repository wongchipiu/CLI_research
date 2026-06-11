"""运行回测。

用法:
    uv run python scripts/run_backtest.py --strategy sma_cross --market cn
    uv run python scripts/run_backtest.py --strategy momentum --market us -p lookback=60 -p top_n=2
策略名见 src/quant/strategies/baselines.py。结果写入 results/<run>/，
并在 stdout 打印 metrics.json 内容（agent 只需读 stdout 或该 json）。
"""

from __future__ import annotations

import argparse
import json
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")  # Windows GBK 控制台中文输出

from quant.backtest import engine, metrics, report
from quant.data import storage
from quant.data.universe import load_universe
from quant.strategies import get_strategy, list_strategies


def load_close(market: str, symbols: list[str]) -> pd.DataFrame:
    frames = {}
    for s in symbols:
        df = storage.load_daily(market, s)
        if df is None or df.empty:
            print(f"[warn] 缺数据: {market}/{s}，已跳过")
            continue
        frames[s] = df.set_index("date")["close"]
    if not frames:
        raise SystemExit(f"{market} 无任何数据，请先运行 scripts/update_data.py")
    return pd.DataFrame(frames).sort_index()


def parse_params(items: list[str]) -> dict:
    out = {}
    for it in items:
        k, _, v = it.partition("=")
        try:
            out[k] = int(v)
        except ValueError:
            try:
                out[k] = float(v)
            except ValueError:
                out[k] = v
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", required=True, help=f"可选: {list_strategies()}")
    ap.add_argument("--market", choices=["cn", "us"], required=True)
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("-p", "--param", action="append", default=[], help="策略参数 k=v，可多次")
    args = ap.parse_args()

    uni = load_universe()
    if args.market == "cn":
        symbols = uni["cn"]
        bench_market, bench_symbol = "cn-index", uni["cn_index"][0]
    else:
        bench_symbol = "SPY"
        symbols = [s for s in uni["us"] if s != bench_symbol]
        bench_market = "us"

    close = load_close(args.market, symbols)
    if args.start:
        close = close.loc[close.index >= pd.Timestamp(args.start)]
    if args.end:
        close = close.loc[close.index <= pd.Timestamp(args.end)]

    bench_df = storage.load_daily(bench_market, bench_symbol)
    bench_nav = None
    if bench_df is not None and not bench_df.empty:
        bench_nav = bench_df.set_index("date")["close"].reindex(close.index).ffill()

    params = parse_params(args.param)
    decision = get_strategy(args.strategy)(close, **params)
    result = engine.run(close, decision, engine.MARKETS[args.market])
    m = metrics.summarize(result.nav, result.returns, result.turnover, bench_nav)
    out = report.save(args.strategy, args.market, params, result, m,
                      bench_nav, benchmark_name=bench_symbol)

    print(json.dumps({"run_dir": out.name, "strategy": args.strategy,
                      "market": args.market, "params": params, **m},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
