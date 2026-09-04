"""Offline tutorial using synthetic data; its evidence is never paper-ready."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant.backtest import engine, report
from quant.backtest.risk_overlay import RiskOverlayConfig
from quant.backtest.study import bounds, data_fingerprint, run_study
from quant.data.research import MarketBars
from quant.strategies import get_strategy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=report.RESULTS_DIR / "tutorial")
    args = parser.parse_args()
    index = pd.bdate_range("2020-01-01", periods=600)
    changes = np.resize([1.012, 1.002, .992, 1.006, 1.001], len(index))
    close = pd.DataFrame({"DEMO_A": 10 * changes.cumprod(), "DEMO_B": 10 * (2 - changes).cumprod()}, index=index)
    opens = close / 1.001
    bars = MarketBars(opens, close, close.notna(), opens["DEMO_A"], close["DEMO_A"], "DEMO_A", {"profile": "synthetic"})
    overlay = RiskOverlayConfig(max_position_weight=1.0)
    payload, records = run_study(bars, get_strategy("momentum"), {"lookback": [10, 20, 30], "top_n": [1], "rebalance": [10]},
                                 engine.US_MARKET, overlay, bounds(index), with_walk_forward=True, train_days=120, test_days=60)
    payload.update(strategy="momentum", market="us", universe="synthetic", synthetic_data=True,
                   universe_point_in_time=False, data_snapshot_sha256=data_fingerprint(bars),
                   warning="Synthetic tutorial only. These returns are not evidence about real stocks.")
    report.RESULTS_DIR = args.output_dir.resolve()
    out = report.save_scan("momentum", "us", records, payload)
    print(json.dumps({"synthetic_data": True, "metrics_path": str(out / "metrics.json"),
                      "selected_params": payload["params"], "final_test_status": payload["validation"]["final_test_status"],
                      "final_test": payload["validation"]["out_of_sample"],
                      "next_step": "Read docs/USER_GUIDE.md; never use this demo for trading."}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
