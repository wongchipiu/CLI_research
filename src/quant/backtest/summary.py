"""Read compact metrics files and build a holdout-first research leaderboard."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


SUMMARY_COLUMNS = [
    "run",
    "strategy",
    "market",
    "params",
    "scope",
    "oos_validated",
    "stability_passed",
    "parameter_robustness_passed",
    "walk_forward_passed",
    "point_in_time_universe",
    "start",
    "end",
    "n_days",
    "total_return",
    "cagr",
    "sharpe",
    "max_drawdown",
    "calmar",
    "completed_trades",
    "excess_cagr",
]


def collect_results(results_dir: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(results_dir.glob("*/metrics.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not payload.get("strategy") or not payload.get("market"):
            continue
        validation = payload.get("validation")
        has_oos = isinstance(validation, dict) and isinstance(
            validation.get("out_of_sample"), dict
        )
        selected = validation["out_of_sample"] if has_oos else payload
        stability = validation.get("stability", {}) if has_oos else {}
        current = (payload.get("schema_version") == 2 and payload.get("artifact_type") == "strategy_validation"
                   and payload.get("execution_model") == "next_open_v1" and payload.get("synthetic_data") is not True
                   and has_oos and validation.get("final_test_status") == "completed")
        rows.append(
            {
                "run": path.parent.name,
                "strategy": payload.get("strategy", ""),
                "market": payload.get("market", ""),
                "params": json.dumps(
                    payload.get("params", {}), ensure_ascii=False, sort_keys=True
                ),
                "scope": "final_test" if current else "legacy_or_exploratory",
                "oos_validated": current,
                "stability_passed": bool(stability.get("passed", False)),
                "parameter_robustness_passed": bool(
                    validation.get("parameter_robustness", {}).get("passed", False)
                ) if has_oos else False,
                "walk_forward_passed": bool(
                    validation.get("walk_forward", {}).get("passed", False)
                ) if has_oos else False,
                "point_in_time_universe": bool(payload.get("universe_point_in_time", False)),
                **{column: selected.get(column) for column in SUMMARY_COLUMNS[10:]},
            }
        )
    frame = pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
    if frame.empty:
        return frame
    # Final-test performance is descriptive, never a new selection leaderboard.
    return frame.sort_values("run", ascending=False).reset_index(drop=True)


def render_monthly_review(frame: pd.DataFrame, month: str) -> str:
    lines = [
        f"# {month} 策略月度复盘",
        "",
        "> 按运行记录展示，不依据最终测试收益选冠军；旧口径和示例仅供观察。",
        "",
    ]
    if frame.empty:
        return "\n".join(lines + ["本月暂无可汇总的回测结果。", ""])

    candidates = frame[
        frame["oos_validated"]
        & frame["stability_passed"]
        & frame["parameter_robustness_passed"]
        & frame["walk_forward_passed"]
        & frame["point_in_time_universe"]
    ]
    lines.extend(["## 待独立验证器复核的研究记录", ""])
    if candidates.empty:
        lines.extend(["暂无同时通过时点股票池、holdout、walk-forward 和参数稳健性检查的候选策略。", ""])
    else:
        lines.extend(
            [
                "| 序号 | 策略 | 市场 | 参数 | 最终测试 CAGR | Sharpe | 最大回撤 | Calmar | 完成持仓 |",
                "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for rank, (_, row) in enumerate(candidates.iterrows(), start=1):
            lines.append(
                f"| {rank} | {row['strategy']} | {row['market']} | `{row['params']}` | "
                f"{_pct(row['cagr'])} | {_num(row['sharpe'])} | {_pct(row['max_drawdown'])} | "
                f"{_num(row['calmar'])} | {_integer(row['completed_trades'])} |"
            )
        lines.append("")

    lines.extend(
        [
            "## 证据覆盖",
            "",
            f"- 回测结果：{len(frame)} 组",
            f"- 含样本外验证：{int(frame['oos_validated'].sum())} 组",
            f"- 通过时点股票池及全部研究检查：{len(candidates)} 组",
            f"- 旧口径/探索/示例/未完成最终测试，不可准入：{int((~frame['oos_validated']).sum())} 组",
            "",
            "## 风险结论",
            "",
            "本报告仅用于研究筛选。未通过样本外验证、模拟交易和人工复核的策略不得进入实盘。",
            "",
        ]
    )
    return "\n".join(lines)


def _pct(value) -> str:
    return "-" if pd.isna(value) else f"{float(value):.2%}"


def _num(value) -> str:
    return "-" if pd.isna(value) else f"{float(value):.2f}"


def _integer(value) -> str:
    return "-" if pd.isna(value) else str(int(value))
