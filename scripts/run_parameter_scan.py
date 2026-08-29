"""Train-only parameter selection, validation and one frozen final test."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant.backtest import engine, report
from quant.backtest.risk_overlay import RiskOverlayConfig
from quant.backtest.study import bounds, data_fingerprint, interval, locked_manifest, run_study, sliced
from quant.data.research import load_market_bars
from quant.data.universe import list_universe_profiles
from quant.strategies import get_strategy, list_strategies


def parse_value(value):
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def parse_grid(items):
    grid = {}
    for item in items:
        key, sep, values = item.partition("=")
        values = [parse_value(v.strip()) for v in values.split(",") if v.strip()]
        if not sep or not key.strip() or not values or key.strip() in grid:
            raise ValueError(f"invalid or repeated parameter grid: {item!r}")
        grid[key.strip()] = values
    if not grid:
        raise ValueError("provide at least one -p name=v1,v2")
    return grid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", required=True, choices=list_strategies())
    parser.add_argument("--market", required=True, choices=["cn", "us"])
    parser.add_argument("--universe", choices=list_universe_profiles())
    parser.add_argument("--membership-file")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--study-file", required=True, type=Path, help="persistent experiment record; do not reuse a consumed final test")
    parser.add_argument("--train-ratio", type=float, default=.6)
    parser.add_argument("--validation-ratio", type=float, default=.2)
    parser.add_argument("--train-end", help="last training date; requires --final-start")
    parser.add_argument("--final-start", help="first final-test date; requires --train-end")
    parser.add_argument("--walk-forward", action="store_true")
    parser.add_argument("--wf-train-days", type=int, default=756)
    parser.add_argument("--wf-test-days", type=int, default=126)
    parser.add_argument("--max-position-weight", type=float, default=1.0)
    parser.add_argument("--max-gross-exposure", type=float, default=1.0)
    parser.add_argument("--target-volatility", type=float)
    parser.add_argument("--volatility-window", type=int, default=20)
    parser.add_argument("--regime-window", type=int)
    parser.add_argument("--risk-off-exposure", type=float, default=0.0)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--preview", action="store_true", help="print fixed date boundaries without selecting parameters or exposing test results")
    parser.add_argument("-p", "--param", action="append", default=[])
    args = parser.parse_args()
    try:
        grid = parse_grid(args.param)
        bars = load_market_bars(args.market, args.universe, args.membership_file)
        index = bars.close.index
        start = int(index.searchsorted(args.start)) if args.start else 0
        end = int(index.searchsorted(args.end, side="right")) if args.end else len(index)
        bars = sliced(bars, start, end)
        splits = bounds(bars.close.index, args.train_ratio, args.validation_ratio, args.train_end, args.final_start)
        overlay = RiskOverlayConfig(max_position_weight=args.max_position_weight, max_gross_exposure=args.max_gross_exposure,
                                    target_volatility=args.target_volatility, volatility_window=args.volatility_window,
                                    regime_window=args.regime_window, risk_off_exposure=args.risk_off_exposure)
        root = Path(__file__).resolve().parents[1]
        sources = sorted((root / "src/quant").rglob("*.py")) + [Path(__file__).resolve()]
        source_hash = hashlib.sha256(b"".join(p.read_bytes() for p in sources)).hexdigest()
        snapshot = data_fingerprint(bars)
        identity = {"strategy": args.strategy, "market": args.market, "grid": grid, "overlay": asdict(overlay),
                    "costs": asdict(engine.MARKETS[args.market]), "data_snapshot_sha256": snapshot,
                    "source_sha256": source_hash, "start": str(bars.close.index[0].date()),
                    "end": str(bars.close.index[-1].date()), "split_positions": list(splits),
                    "walk_forward": args.walk_forward, "wf_train_days": args.wf_train_days,
                    "wf_test_days": args.wf_test_days, "execution_model": "next_open_v1",
                    "universe": bars.universe["profile"], "membership_sha256": bars.universe.get("membership_sha256")}
        if args.preview:
            print(json.dumps({"preview_only": True,
                "train": interval(bars.close.index, 0, splits[0]),
                "validation": interval(bars.close.index, splits[0], splits[1]),
                "final_test": interval(bars.close.index, splits[1], len(bars.close)),
                "study_file": str(args.study_file.resolve()), "execution_model": "next_open_v1"}, indent=2))
            return
        with locked_manifest(args.study_file, identity) as (state, consume, save):
            payload, records = run_study(bars, get_strategy(args.strategy), grid, engine.MARKETS[args.market], overlay,
                                         splits, with_walk_forward=args.walk_forward, train_days=args.wf_train_days,
                                         test_days=args.wf_test_days, before_final=consume)
            payload.update(strategy=args.strategy, market=args.market, universe=bars.universe["profile"],
                           universe_point_in_time=bars.universe.get("point_in_time", False),
                           membership_file=bars.universe.get("membership_file"), membership_sha256=bars.universe.get("membership_sha256"),
                           risk_overlay=asdict(overlay), costs=asdict(engine.MARKETS[args.market]), benchmark_name=bars.benchmark_name,
                           data_snapshot_sha256=snapshot, source_sha256=source_hash, run_type="parameter_scan",
                           scan_size=len(records), study_file=str(args.study_file.resolve()))
            out = report.save_scan(args.strategy, args.market, records, payload)
            state["result_dir"] = str(out.resolve())
            state["status"] = payload["validation"]["final_test_status"]
            save()
        if args.compact:
            evidence = payload["validation"]
            output = {"run_dir": str(out.resolve()), "params": payload["params"],
                      "selection_scope": "train_only", "final_test_status": evidence["final_test_status"],
                      "final_test_reason": evidence["final_test_reason"], "out_of_sample": evidence["out_of_sample"],
                      "stability": evidence["stability"], "parameter_robustness": evidence["parameter_robustness"],
                      "walk_forward_passed": evidence["walk_forward"]["passed"]}
        else:
            output = {"run_dir": str(out.resolve()), "best": payload}
        print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
    except (ValueError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
