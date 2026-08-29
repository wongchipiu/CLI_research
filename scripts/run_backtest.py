"""Exploratory backtest; use run_parameter_scan.py for independent validation."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant.backtest import engine, metrics, report
from quant.backtest.risk_overlay import RiskOverlayConfig, apply_risk_overlay
from quant.backtest.study import sliced
from quant.data.research import load_market_bars
from quant.data.universe import list_universe_profiles
from quant.strategies import get_strategy, list_strategies


def parse_params(items):
    output = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key or key in output:
            raise ValueError(f"invalid/repeated parameter: {item}")
        try:
            output[key] = int(value)
        except ValueError:
            try:
                output[key] = float(value)
            except ValueError:
                output[key] = value
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", required=True, choices=list_strategies())
    parser.add_argument("--market", required=True, choices=["cn", "us"])
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--universe", choices=list_universe_profiles())
    parser.add_argument("--membership-file")
    parser.add_argument("--execution-model", choices=["next_open_v1", "legacy_same_close"], default="next_open_v1")
    parser.add_argument("--max-position-weight", type=float, default=1.0)
    parser.add_argument("--max-gross-exposure", type=float, default=1.0)
    parser.add_argument("--target-volatility", type=float)
    parser.add_argument("--volatility-window", type=int, default=20)
    parser.add_argument("--regime-window", type=int)
    parser.add_argument("--risk-off-exposure", type=float, default=0.0)
    parser.add_argument("-p", "--param", action="append", default=[])
    args = parser.parse_args()
    try:
        bars = load_market_bars(args.market, args.universe, args.membership_file)
        index = bars.close.index
        bars = sliced(bars, int(index.searchsorted(args.start)) if args.start else 0,
                      int(index.searchsorted(args.end, side="right")) if args.end else len(index))
        params = parse_params(args.param)
        overlay = RiskOverlayConfig(max_position_weight=args.max_position_weight, max_gross_exposure=args.max_gross_exposure,
                                    target_volatility=args.target_volatility, volatility_window=args.volatility_window,
                                    regime_window=args.regime_window, risk_off_exposure=args.risk_off_exposure)
        decision = apply_risk_overlay(bars.signal_close, get_strategy(args.strategy)(bars.signal_close, **params), overlay)
        decision = decision.where(bars.eligible, 0.0)
        result = engine.run(bars.close, decision, engine.MARKETS[args.market], open_prices=bars.open,
                            execution_model=args.execution_model)
        summary = metrics.summarize(result.nav, result.returns, result.turnover, bars.benchmark_close, result.weights,
                                    benchmark_initial=float(bars.benchmark_open.iloc[0]) if bars.benchmark_open is not None else None)
        summary.update(schema_version=2, artifact_type="exploratory_backtest", execution_model=result.execution_model,
                       stale_valuation_days=result.stale_valuation_days, research_only=True)
        out = report.save(args.strategy, args.market, params, result, summary, bars.benchmark_close, bars.benchmark_name,
                          metadata={"universe": bars.universe["profile"], "risk_overlay": asdict(overlay),
                                    "costs": asdict(engine.MARKETS[args.market])},
                          benchmark_initial=float(bars.benchmark_open.iloc[0]) if bars.benchmark_open is not None else None)
        print(json.dumps({"run_dir": str(out.resolve()), **summary}, ensure_ascii=False, indent=2, allow_nan=False))
    except (ValueError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
