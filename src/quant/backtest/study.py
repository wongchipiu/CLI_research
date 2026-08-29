"""Chronological research: select on train, validate, then expose one final test.

Strategies must be causal (prefix-invariant). Selection never receives future
bars. A fold evaluates the selection procedure, not a stitched trading account.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import itertools
import inspect
import json
from pathlib import Path

import numpy as np
import pandas as pd

from quant.backtest import engine, metrics
from quant.backtest.risk_overlay import RiskOverlayConfig, apply_risk_overlay
from quant.data.research import MarketBars


def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def data_fingerprint(bars: MarketBars) -> str:
    h = hashlib.sha256()
    for frame in (bars.open, bars.close, bars.eligible, bars.benchmark_open, bars.benchmark_close):
        if frame is not None:
            h.update(str(getattr(frame, "columns", frame.name if isinstance(frame, pd.Series) else "")).encode())
            h.update(pd.util.hash_pandas_object(frame, index=True).values.tobytes())
    return h.hexdigest()


def bounds(index: pd.Index, train_ratio: float = .6, validation_ratio: float = .2,
           train_end: str | None = None, final_start: str | None = None) -> tuple[int, int]:
    if not index.is_unique or not index.is_monotonic_increasing:
        raise ValueError("research dates must be unique and chronological")
    if not 0 < train_ratio < 1 or not 0 < validation_ratio < 1 or train_ratio + validation_ratio >= 1:
        raise ValueError("train/validation ratios must leave a nonempty final test")
    if bool(train_end) != bool(final_start):
        raise ValueError("provide both --train-end and --final-start, or neither")
    first = int(index.searchsorted(pd.Timestamp(train_end), side="right")) if train_end else int(len(index) * train_ratio)
    second = int(index.searchsorted(pd.Timestamp(final_start), side="left")) if final_start else int(len(index) * (train_ratio + validation_ratio))
    if first < 20 or second - first < 2 or len(index) - second < 2:
        raise ValueError("need >=20 training sessions and >=2 sessions in each later interval")
    return first, second


def interval(index, start, end) -> dict:
    return {"start": str(index[start].date()), "end": str(index[end - 1].date()), "n_days": end - start}


def sliced(bars: MarketBars, start: int, end: int) -> MarketBars:
    return MarketBars(bars.open.iloc[start:end], bars.close.iloc[start:end], bars.eligible.iloc[start:end],
                      bars.benchmark_open.iloc[start:end] if bars.benchmark_open is not None else None,
                      bars.benchmark_close.iloc[start:end] if bars.benchmark_close is not None else None,
                      bars.benchmark_name, bars.universe)


def evaluate_segment(bars, strategy, params, cfg, overlay, start, end) -> dict:
    # Parameters are frozen before this function sees the later interval.
    signals = strategy(bars.signal_close.iloc[:end], **params)
    signals = apply_risk_overlay(bars.signal_close.iloc[:end], signals, overlay)
    signals = signals.where(bars.eligible.iloc[:end], 0.0)
    result = engine.run(
        bars.close.iloc[start:end], signals.iloc[start:end], cfg,
        open_prices=bars.open.iloc[start:end],
        initial_signal=signals.iloc[start - 1] if start else None,
        initial_signal_date=bars.close.index[start - 1] if start else None,
        previous_close=bars.close.iloc[:start].combine_first(bars.open.iloc[:start]).ffill().iloc[-1] if start else None,
    )
    benchmark = bars.benchmark_close.iloc[start:end] if bars.benchmark_close is not None else None
    benchmark_initial = float(bars.benchmark_open.iloc[start]) if bars.benchmark_open is not None else None
    summary = metrics.summarize(result.nav, result.returns, result.turnover, benchmark, result.weights,
                                benchmark_initial=benchmark_initial)
    summary.update(stale_valuation_days=result.stale_valuation_days,
                   end_open_positions=int((result.weights.iloc[-1] > 1e-8).sum()),
                   execution_model=result.execution_model)
    return summary


def parameter_sets(grid: dict) -> list[dict]:
    if not grid or any(not isinstance(values, list) or not values for values in grid.values()):
        raise ValueError("parameter grid must have nonempty lists")
    keys = sorted(grid)
    combinations = [dict(zip(keys, values)) for values in itertools.product(*(grid[key] for key in keys))]
    # Validation also rejects JSON NaN/infinity and removes repeated candidates.
    unique = {json.dumps(p, sort_keys=True, allow_nan=False): p for p in combinations}
    return [unique[key] for key in sorted(unique)]


def select_parameters(train_bars, strategy, grid, cfg, overlay) -> list[dict]:
    records = []
    for params in parameter_sets(grid):
        defaults = {name: parameter.default for name, parameter in inspect.signature(strategy).parameters.items()
                    if parameter.default is not inspect.Parameter.empty}
        values = {**defaults, **params}
        windows = [values[key] for key in ("lookback", "slow", "fast", "window", "vol_window", "trend_window")
                   if isinstance(values.get(key), int)]
        if windows and len(train_bars.close) < max(windows) + 2:
            raise ValueError("training window is too short for indicator warmup and next-open execution")
        summary = evaluate_segment(train_bars, strategy, params, cfg, overlay, 0, len(train_bars.close))
        eligible = summary["total_return"] > 0 and summary["sharpe"] > 0 and summary["stale_valuation_days"] == 0
        records.append({"params": params, "eligible": eligible, "training": summary})
    records.sort(key=lambda r: (-int(r["eligible"]), -r["training"]["sharpe"],
                               -r["training"]["cagr"], json.dumps(r["params"], sort_keys=True)))
    for rank, record in enumerate(records, 1):
        record["rank"] = rank
    return records


def robustness(records, grid, selected) -> dict:
    neighbors = set()
    for key, values in grid.items():
        values = list(dict.fromkeys(values))
        position = values.index(selected[key])
        for adjacent in (position - 1, position + 1):
            if 0 <= adjacent < len(values):
                params = {**selected, key: values[adjacent]}
                neighbors.add(json.dumps(params, sort_keys=True))
    matched = [r for r in records if json.dumps(r["params"], sort_keys=True) in neighbors]
    positive = sum(r["training"]["total_return"] > 0 for r in matched)
    return {"scope": "train_only", "neighbor_count": len(matched),
            "positive_neighbor_ratio": positive / len(matched) if matched else 0.0,
            "passed": bool(matched) and positive / len(matched) >= 2 / 3}


def walk_forward(bars, strategy, grid, cfg, overlay, *, train_days=756, test_days=126) -> dict:
    if train_days < 20 or test_days < 2:
        raise ValueError("walk-forward requires >=20 training and >=2 test sessions")
    folds = []
    for start in range(train_days, len(bars.close) - test_days + 1, test_days):
        local = sliced(bars, start - train_days, start + test_days)
        ranked = select_parameters(sliced(local, 0, train_days), strategy, grid, cfg, overlay)
        best = ranked[0]
        score = evaluate_segment(local, strategy, best["params"], cfg, overlay, train_days, len(local.close))
        folds.append({"train": interval(local.close.index, 0, train_days),
                      "test": interval(local.close.index, train_days, len(local.close)),
                      "selected_at": str(local.close.index[train_days - 1].date()),
                      "selected_params": best["params"], "training_eligible": best["eligible"], "metrics": score})
    positive = sum(f["metrics"]["total_return"] > 0 for f in folds) / len(folds) if folds else 0.0
    median = float(np.median([f["metrics"]["sharpe"] for f in folds])) if folds else 0.0
    worst = min((f["metrics"]["max_drawdown"] for f in folds), default=0.0)
    passed = len(folds) >= 3 and positive >= 2 / 3 and median >= .5 and worst >= -.25
    passed = passed and all(f["training_eligible"] and f["metrics"]["stale_valuation_days"] == 0 for f in folds)
    return {"method": "train_selected_walk_forward_v1", "selection_scope": "train_only",
            "scope": "development_only", "accounting": "independent_folds_not_continuous_nav",
            "fold_count": len(folds), "positive_fold_ratio": positive, "median_sharpe": median,
            "worst_drawdown": worst, "passed": passed, "folds": folds}


def run_study(bars, strategy, grid, cfg, overlay, splits, *, with_walk_forward=False,
              train_days=756, test_days=126, before_final=None) -> tuple[dict, list[dict]]:
    first, second = splits
    train = sliced(bars, 0, first)
    ranked = select_parameters(train, strategy, grid, cfg, overlay)
    best = ranked[0]
    chosen = dict(best["params"])
    validation = evaluate_segment(bars, strategy, chosen, cfg, overlay, first, second)
    stable = (best["eligible"] and validation["total_return"] > 0
              and validation["sharpe"] >= max(0.0, best["training"]["sharpe"] * .5)
              and validation["stale_valuation_days"] == 0)
    wf = walk_forward(sliced(bars, 0, second), strategy, grid, cfg, overlay,
                      train_days=train_days, test_days=test_days) if with_walk_forward else {"passed": False, "status": "not_run"}
    protocol = {"name": "chronological_three_way_v1", "selection_scope": "train_only",
                "train": interval(bars.close.index, 0, first),
                "validation": interval(bars.close.index, first, second),
                "final_test": interval(bars.close.index, second, len(bars.close)),
                "selected_at": str(bars.close.index[first - 1].date()), "selected_params": chosen,
                "frozen_params_sha256": digest(chosen)}
    final = {}
    reason = "validation_or_training_failed"
    if stable and (not with_walk_forward or wf["passed"]):
        if before_final is not None:
            before_final(protocol)
        final = evaluate_segment(bars, strategy, chosen, cfg, overlay, second, len(bars.close))
        reason = "completed"
    elif stable:
        reason = "walk_forward_failed"
    evidence = {"in_sample": best["training"], "validation_sample": validation,
                "out_of_sample": final, "final_test_status": "completed" if final else "not_run",
                "final_test_reason": reason, "stability": {"passed": stable},
                "parameter_robustness": robustness(ranked, grid, chosen), "walk_forward": wf}
    return {"schema_version": 2, "artifact_type": "strategy_validation",
            "execution_model": "next_open_v1", "params": chosen, "n_days": len(bars.close),
            "research_protocol": protocol, "validation": evidence}, ranked


@contextmanager
def locked_manifest(path: Path, identity: dict):
    """Freeze one experiment; consume the final test before exposing its prices.

    This protects reuse of this manifest, not deliberate reuse under another name.
    The guide requires a research log across experiments as well.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(path.suffix + ".lock")
    try:
        lock.touch(exist_ok=False)
    except FileExistsError as exc:
        raise ValueError(f"study locked: {lock}; verify no process is running before recovery") from exc
    try:
        state = json.loads(path.read_text()) if path.exists() else {"identity": identity, "final_test_consumed": False}
        if state.get("identity") != identity:
            raise ValueError("study inputs/snapshot changed; frozen dates, data and parameters must match")
        if state.get("final_test_consumed") is not False:
            raise ValueError("final test already consumed; read the saved result, do not relabel it as unseen")
        def save():
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
            temporary.replace(path)
        def consume(protocol):
            state.update(final_test_consumed=True, consumed_at=datetime.now(timezone.utc).isoformat(),
                         frozen_protocol=protocol)
            save()
        save()
        yield state, consume, save
    finally:
        lock.unlink(missing_ok=True)
