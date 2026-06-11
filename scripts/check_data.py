"""数据质量检查：输出文本摘要（agent 只读这个摘要，不读 parquet）。

用法:
    uv run python scripts/check_data.py
摘要同时写入 data/quality_summary.txt
"""

from __future__ import annotations

import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")  # Windows GBK 控制台中文输出

from quant.data import storage


def check_symbol(market: str, symbol: str) -> list[str]:
    df = storage.load_daily(market, symbol)
    issues = []
    if df is None or df.empty:
        return [f"{market}/{symbol}: 无数据"]
    dates = pd.to_datetime(df["date"])
    line = (
        f"{market}/{symbol}: {len(df)} 行, "
        f"{dates.min().date()} ~ {dates.max().date()}"
    )
    if dates.duplicated().any():
        issues.append("存在重复日期")
    if not dates.is_monotonic_increasing:
        issues.append("日期未升序")
    nan_cols = df[storage.REQUIRED_COLS].isna().sum()
    nan_cols = nan_cols[nan_cols > 0]
    if not nan_cols.empty:
        issues.append(f"NaN: {dict(nan_cols)}")
    price_cols = df[["open", "high", "low", "close"]]
    if (price_cols <= 0).any().any():
        issues.append("存在非正价格")
    if (df["high"] < df["low"]).any():
        issues.append("high < low")
    gaps = dates.diff().dt.days
    big_gap = gaps[gaps > 15]
    if not big_gap.empty:
        issues.append(f"{len(big_gap)} 处 >15 自然日缺口(停牌/休市)")
    # 与最新交易日的距离（数据新鲜度）
    staleness = (pd.Timestamp.today() - dates.max()).days
    if staleness > 7:
        issues.append(f"数据已 {staleness} 天未更新")
    return [line + ("  [" + "; ".join(issues) + "]" if issues else "  [OK]")]


def main() -> None:
    daily_dir = storage.DATA_DIR / "daily"
    if not daily_dir.exists():
        print("无数据，请先运行 scripts/update_data.py")
        raise SystemExit(1)

    lines = []
    for market_dir in sorted(daily_dir.iterdir()):
        for f in sorted(market_dir.glob("*.parquet")):
            lines += check_symbol(market_dir.name, f.stem)

    report = "\n".join(lines)
    print(report)
    out = storage.DATA_DIR / "quality_summary.txt"
    out.write_text(report, encoding="utf-8")
    print(f"\n摘要已写入 {out}")


if __name__ == "__main__":
    main()
