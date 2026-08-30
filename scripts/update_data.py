"""一键增量更新日线数据。

用法:
    uv run python scripts/update_data.py                # 更新全部市场
    uv run python scripts/update_data.py --market cn    # 只更新 A股
    uv run python scripts/update_data.py --start 2018-01-01
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import time

sys.stdout.reconfigure(encoding="utf-8")  # Windows GBK 控制台中文输出
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from quant.data import fetchers, storage
from quant.data.universe import load_universe
from quant.workspace import WorkspaceConfig

DEFAULT_START = "2018-01-01"


def update_symbol(market: str, symbol: str, fetch_fn, start: str, end: str) -> str:
    last = storage.last_date(market, symbol)
    fetch_start = (last + pd.Timedelta(days=1)).strftime("%Y-%m-%d") if last is not None else start
    if pd.Timestamp(fetch_start) > pd.Timestamp(end):
        return f"{market}/{symbol}: 已是最新 (至 {last.date()})"
    try:
        df = fetch_fn(symbol, fetch_start, end)
    except Exception as e:
        return f"{market}/{symbol}: !! 拉取失败 {type(e).__name__}: {e}"
    total = storage.save_daily(market, symbol, df)
    return f"{market}/{symbol}: +{len(df)} 行, 共 {total} 行"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", choices=["all", "cn", "us"], default="all")
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--universe", help="股票池 profile；由 workspace 指向的 universe.yaml 校验")
    ap.add_argument("--symbol", action="append", default=[], help="只更新股票池内指定代码，可多次")
    ap.add_argument("--workspace", type=Path, help="versioned workspace YAML; paths are cwd-independent")
    args = ap.parse_args()

    if args.workspace:
        WorkspaceConfig.load(args.workspace).apply()

    uni = load_universe(args.universe)
    jobs: list[tuple[str, str, object]] = []
    if args.market in ("all", "cn"):
        jobs += [("cn", s, fetchers.fetch_cn_daily) for s in uni["cn"]]
        jobs += [("cn-index", s, fetchers.fetch_cn_index_daily) for s in uni["cn_index"]]
    if args.market in ("all", "us"):
        jobs += [("us", s, fetchers.fetch_us_daily) for s in uni["us"]]
    if args.symbol:
        requested = {symbol.upper() for symbol in args.symbol}
        available = {symbol.upper() for _, symbol, _ in jobs}
        unknown = requested - available
        if unknown:
            ap.error(f"指定代码不在 {uni['profile']} 股票池或所选市场中: {sorted(unknown)}")
        jobs = [job for job in jobs if job[1].upper() in requested]

    failed = 0
    for market, symbol, fn in jobs:
        msg = update_symbol(market, symbol, fn, args.start, args.end)
        print(msg, flush=True)
        if "!!" in msg:
            failed += 1
        time.sleep(0.5)  # 免费数据源限频，礼貌性间隔

    print(f"\n完成: {len(jobs) - failed}/{len(jobs)} 成功")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
