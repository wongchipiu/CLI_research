"""Deterministic holdout evaluation helpers for portfolio backtests."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quant.backtest import engine, metrics


@dataclass(frozen=True)
class HoldoutEvaluation:
    split_date: str
    train_ratio: float
    in_sample: dict
    out_of_sample: dict
    stability: dict

    def to_dict(self) -> dict:
        return {
            "method": "legacy_holdout",
            "split_date": self.split_date,
            "train_ratio": round(self.train_ratio, 4),
            "in_sample": self.in_sample,
            "out_of_sample": self.out_of_sample,
            "stability": self.stability,
        }


@dataclass(frozen=True)
class WalkForwardEvaluation:
    train_days: int
    test_days: int
    folds: tuple[dict, ...]
    aggregate: dict
    positive_fold_ratio: float
    median_sharpe: float
    worst_drawdown: float
    passed: bool

    def to_dict(self) -> dict:
        return {
            "method": "legacy_fixed_windows",
            "train_days": self.train_days,
            "test_days": self.test_days,
            "fold_count": len(self.folds),
            "positive_fold_ratio": round(self.positive_fold_ratio, 3),
            "median_sharpe": round(self.median_sharpe, 3),
            "worst_drawdown": round(self.worst_drawdown, 4),
            "passed": self.passed,
            "aggregate": self.aggregate,
            "folds": list(self.folds),
        }


def resolve_split_position(
    index: pd.Index,
    *,
    train_ratio: float = 0.7,
    split_date: str | None = None,
) -> int:
    if len(index) < 4:
        raise ValueError("样本内/样本外评估至少需要 4 个交易日")
    if split_date is not None:
        position = int(index.searchsorted(pd.Timestamp(split_date), side="left"))
    else:
        if not 0.1 <= train_ratio <= 0.9:
            raise ValueError("train_ratio 必须在 0.1 到 0.9 之间")
        position = int(len(index) * train_ratio)
    if position < 2 or len(index) - position < 2:
        raise ValueError("切分点两侧都必须至少保留 2 个交易日")
    return position


def evaluate_holdout(
    close: pd.DataFrame,
    decision: pd.DataFrame,
    cfg: engine.MarketConfig,
    benchmark_nav: pd.Series | None = None,
    *,
    train_ratio: float = 0.7,
    split_date: str | None = None,
) -> HoldoutEvaluation:
    """Evaluate train/test independently while retaining pre-split signal warmup."""
    position = resolve_split_position(
        close.index, train_ratio=train_ratio, split_date=split_date
    )
    train_close = close.iloc[:position]
    test_close = close.iloc[position:]
    train_decision = decision.reindex(train_close.index)
    test_decision = decision.reindex(test_close.index)

    train_benchmark = _slice_benchmark(benchmark_nav, train_close.index)
    test_benchmark = _slice_benchmark(benchmark_nav, test_close.index)
    train_result = engine.run(train_close, train_decision, cfg, execution_model="legacy_same_close")
    test_result = engine.run(test_close, test_decision, cfg, execution_model="legacy_same_close")
    train_metrics = metrics.summarize(
        train_result.nav,
        train_result.returns,
        train_result.turnover,
        train_benchmark,
        train_result.weights,
    )
    test_metrics = metrics.summarize(
        test_result.nav,
        test_result.returns,
        test_result.turnover,
        test_benchmark,
        test_result.weights,
    )
    stability = _stability(train_metrics, test_metrics)
    return HoldoutEvaluation(
        split_date=str(test_close.index[0].date()),
        train_ratio=position / len(close),
        in_sample=train_metrics,
        out_of_sample=test_metrics,
        stability=stability,
    )


def evaluate_walk_forward(
    close: pd.DataFrame,
    decision: pd.DataFrame,
    cfg: engine.MarketConfig,
    benchmark_nav: pd.Series | None = None,
    *,
    train_days: int = 756,
    test_days: int = 126,
) -> WalkForwardEvaluation:
    if train_days < 20 or test_days < 20:
        raise ValueError("walk-forward 训练和测试窗口都至少需要 20 个交易日")
    starts = list(range(train_days, len(close) - test_days + 1, test_days))
    if not starts:
        raise ValueError("数据不足以形成一个完整 walk-forward 窗口")

    fold_summaries = []
    fold_results = []
    benchmark_parts = []
    for fold_number, start in enumerate(starts, start=1):
        end = start + test_days
        test_close = close.iloc[start:end]
        test_decision = decision.reindex(test_close.index)
        test_benchmark = _slice_benchmark(benchmark_nav, test_close.index)
        result = engine.run(test_close, test_decision, cfg, execution_model="legacy_same_close")
        summary = metrics.summarize(
            result.nav,
            result.returns,
            result.turnover,
            test_benchmark,
            result.weights,
        )
        fold_summaries.append(
            {
                "fold": fold_number,
                "train_start": str(close.index[start - train_days].date()),
                "train_end": str(close.index[start - 1].date()),
                "test_start": summary["start"],
                "test_end": summary["end"],
                "total_return": summary["total_return"],
                "cagr": summary["cagr"],
                "sharpe": summary["sharpe"],
                "max_drawdown": summary["max_drawdown"],
                "completed_trades": summary["completed_trades"],
            }
        )
        fold_results.append(result)
        if test_benchmark is not None:
            benchmark_parts.append(test_benchmark)

    combined_returns = pd.concat([result.returns for result in fold_results])
    combined_nav = (1.0 + combined_returns).cumprod()
    combined_turnover = pd.concat([result.turnover for result in fold_results])
    combined_weights = pd.concat([result.weights for result in fold_results])
    combined_benchmark = pd.concat(benchmark_parts) if benchmark_parts else None
    aggregate = metrics.summarize(
        combined_nav,
        combined_returns,
        combined_turnover,
        combined_benchmark,
        combined_weights,
    )
    positive_ratio = sum(fold["total_return"] > 0 for fold in fold_summaries) / len(fold_summaries)
    median_sharpe = float(pd.Series([fold["sharpe"] for fold in fold_summaries]).median())
    worst_drawdown = min(float(fold["max_drawdown"]) for fold in fold_summaries)
    passed = (
        len(fold_summaries) >= 3
        and positive_ratio >= 2 / 3
        and median_sharpe >= 0.5
        and aggregate["total_return"] > 0
        and worst_drawdown >= -0.25
    )
    return WalkForwardEvaluation(
        train_days=train_days,
        test_days=test_days,
        folds=tuple(fold_summaries),
        aggregate=aggregate,
        positive_fold_ratio=positive_ratio,
        median_sharpe=median_sharpe,
        worst_drawdown=worst_drawdown,
        passed=passed,
    )


def _slice_benchmark(
    benchmark_nav: pd.Series | None, index: pd.Index
) -> pd.Series | None:
    if benchmark_nav is None:
        return None
    return benchmark_nav.reindex(index).ffill()


def _stability(in_sample: dict, out_of_sample: dict) -> dict:
    is_sharpe = float(in_sample.get("sharpe", 0.0))
    oos_sharpe = float(out_of_sample.get("sharpe", 0.0))
    is_cagr = float(in_sample.get("cagr", 0.0))
    oos_cagr = float(out_of_sample.get("cagr", 0.0))
    sharpe_floor = max(0.0, is_sharpe * 0.5)
    return {
        "passed": oos_cagr > 0.0 and oos_sharpe >= sharpe_floor,
        "cagr_delta": round(oos_cagr - is_cagr, 4),
        "sharpe_delta": round(oos_sharpe - is_sharpe, 3),
        "oos_to_is_cagr": round(oos_cagr / is_cagr, 3) if is_cagr > 0 else None,
    }
