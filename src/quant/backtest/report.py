"""回测结果落盘：results/<策略>_<市场>_<时间戳>/

- metrics.json  —— 绩效摘要（<2KB，agent 只读这个）
- nav.csv       —— 策略与基准净值
- nav.png       —— 净值对比图（给人看）
- weights.csv   —— 每日持仓权重
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

from quant.backtest.engine import BacktestResult

RESULTS_DIR = Path(__file__).resolve().parents[3] / "results"


def save(
    strategy: str,
    market: str,
    params: dict,
    result: BacktestResult,
    metrics: dict,
    benchmark_nav: pd.Series | None = None,
    benchmark_name: str = "",
    metadata: dict | None = None,
    benchmark_initial: float | None = None,
) -> Path:
    run_id = f"{strategy}_{market}_{datetime.now():%Y%m%d-%H%M%S-%f}"
    out = RESULTS_DIR / run_id
    out.mkdir(parents=True, exist_ok=True)

    payload = {
        "strategy": strategy,
        "market": market,
        "params": params,
        "benchmark_name": benchmark_name,
        **(metadata or {}),
        **metrics,
    }
    (out / "metrics.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    df = pd.DataFrame({"nav": result.nav})
    if benchmark_nav is not None:
        b = benchmark_nav.reindex(result.nav.index).ffill()
        initial = b.iloc[0] if benchmark_initial is None else benchmark_initial
        if pd.notna(initial) and initial > 0:
            df["benchmark"] = b / initial
    df.to_csv(out / "nav.csv", encoding="utf-8")
    result.weights.to_csv(out / "weights.csv", encoding="utf-8")
    if result.execution_events:
        pd.DataFrame(result.execution_events).to_csv(out / "execution.csv", index=False, encoding="utf-8")

    os.environ.setdefault("MPLCONFIGDIR", str(RESULTS_DIR / ".matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df.index, df["nav"], label=strategy, linewidth=1.5)
    if "benchmark" in df.columns:
        ax.plot(df.index, df["benchmark"], label=benchmark_name or "benchmark",
                linewidth=1.0, alpha=0.7)
    ax.set_title(f"{strategy} ({market})  NAV")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "nav.png", dpi=120)
    plt.close(fig)
    return out


def save_scan(
    strategy: str,
    market: str,
    records: list[dict],
    best_metrics: dict,
) -> Path:
    """Save a compact best-candidate summary and the complete scan table."""
    run_id = f"scan_{strategy}_{market}_{datetime.now():%Y%m%d-%H%M%S-%f}"
    out = RESULTS_DIR / run_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(
        json.dumps(best_metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "scan.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    rows = []
    for record in records:
        oos = record["training"]
        rows.append(
            {
                "rank": record["rank"],
                "eligible": record["eligible"],
                "params": json.dumps(record["params"], ensure_ascii=False, sort_keys=True),
                "selection_scope": "train_only",
                "train_cagr": oos["cagr"],
                "train_sharpe": oos["sharpe"],
                "train_max_drawdown": oos["max_drawdown"],
                "train_calmar": oos["calmar"],
                "train_completed_trades": oos["completed_trades"],
            }
        )
    pd.DataFrame(rows).to_csv(out / "ranking.csv", index=False, encoding="utf-8")
    return out
