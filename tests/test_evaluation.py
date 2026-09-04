import numpy as np
import pandas as pd
import pytest

from quant.backtest.engine import MarketConfig
from quant.backtest.evaluation import evaluate_holdout, resolve_split_position


NO_FEE = MarketConfig(buy_cost=0.0, sell_cost=0.0, limit_pct=None)


def test_holdout_uses_prior_history_for_signal_warmup_but_restarts_nav():
    index = pd.bdate_range("2020-01-01", periods=100)
    close = pd.DataFrame({"A": np.linspace(10.0, 20.0, 100)}, index=index)
    decision = pd.DataFrame(1.0, index=index, columns=["A"])

    evaluation = evaluate_holdout(close, decision, NO_FEE, train_ratio=0.7)

    assert evaluation.split_date == str(index[70].date())
    assert evaluation.in_sample["n_days"] == 70
    assert evaluation.out_of_sample["n_days"] == 30
    assert evaluation.out_of_sample["total_return"] > 0


def test_split_date_must_leave_data_on_both_sides():
    index = pd.bdate_range("2024-01-01", periods=10)
    with pytest.raises(ValueError):
        resolve_split_position(index, split_date="2024-01-02")


def synthetic_bars(n=150):
    from quant.data.research import MarketBars
    index = pd.bdate_range("2020-01-01", periods=n)
    growth = np.resize([1.01, 1.003, .998, 1.007, 1.002], n)
    close = pd.DataFrame({"A": 10 * np.cumprod(growth), "B": 10 * np.cumprod(2 - growth)}, index=index)
    opens = close / 1.001
    return MarketBars(opens, close, close.notna(), opens["A"], close["A"], "A", {"profile": "synthetic"})


def choose_asset(close, choice="A"):
    weights = close * 0.0
    weights[choice] = 1.0
    return weights


def test_final_prices_cannot_change_selection_or_expose_other_candidates():
    from quant.backtest.study import bounds, run_study
    from quant.backtest.risk_overlay import RiskOverlayConfig
    bars = synthetic_bars()
    calls = []
    def strategy(close, choice):
        calls.append((choice, close.index.max()))
        return choose_asset(close, choice)
    splits = bounds(bars.close.index)
    overlay = RiskOverlayConfig(max_position_weight=1.0)
    original, _ = run_study(bars, strategy, {"choice": ["A", "B"]}, NO_FEE, overlay, splits)
    assert original["validation"]["final_test_status"] == "completed"
    assert all(date <= bars.close.index[splits[0] - 1] for choice, date in calls if choice == "B")
    bars.close.iloc[splits[1]:, 0] *= np.linspace(1, .5, len(bars.close) - splits[1])
    bars.open.iloc[splits[1]:, 0] = bars.close.iloc[splits[1]:, 0] / 1.001
    changed, _ = run_study(bars, strategy, {"choice": ["A", "B"]}, NO_FEE, overlay, splits)
    assert changed["params"] == original["params"] == {"choice": "A"}
    assert changed["research_protocol"] == original["research_protocol"]
    assert changed["validation"]["out_of_sample"]["total_return"] < original["validation"]["out_of_sample"]["total_return"]


def test_failed_validation_leaves_final_test_unexposed():
    from quant.backtest.study import bounds, run_study
    from quant.backtest.risk_overlay import RiskOverlayConfig
    bars = synthetic_bars()
    first, second = bounds(bars.close.index)
    bars.close.iloc[first:second, 0] *= np.linspace(1, .3, second - first)
    bars.open.iloc[first:second, 0] = bars.close.iloc[first:second, 0] / 1.001
    consumed = []
    result, _ = run_study(bars, choose_asset, {"choice": ["A"]}, NO_FEE,
                          RiskOverlayConfig(max_position_weight=1), (first, second), before_final=consumed.append)
    assert result["validation"]["final_test_status"] == "not_run"
    assert result["validation"]["out_of_sample"] == {}
    assert consumed == []


def test_manifest_freezes_inputs_and_consumes_final_before_results(tmp_path):
    from quant.backtest.study import locked_manifest
    path = tmp_path / "study.json"
    with locked_manifest(path, {"final_start": "2024-01-01"}):
        pass
    with pytest.raises(ValueError, match="changed"):
        with locked_manifest(path, {"final_start": "2025-01-01"}):
            pass
    with locked_manifest(path, {"final_start": "2024-01-01"}) as (_, consume, _):
        consume({"selected_params": {"lookback": 20}})
    with pytest.raises(ValueError, match="consumed"):
        with locked_manifest(path, {"final_start": "2024-01-01"}):
            pass


def test_benchmark_slice_never_backfills():
    from quant.backtest.evaluation import _slice_benchmark
    index = pd.bdate_range("2026-01-05", periods=3)
    series = pd.Series([np.nan, 10., 11.], index=index)
    assert pd.isna(_slice_benchmark(series, index).iloc[0])


def test_training_rejects_insufficient_indicator_warmup():
    from quant.backtest.study import select_parameters
    from quant.backtest.risk_overlay import RiskOverlayConfig
    from quant.strategies import get_strategy
    with pytest.raises(ValueError, match="warmup"):
        select_parameters(synthetic_bars(30), get_strategy("momentum"), {"lookback": [60]}, NO_FEE,
                          RiskOverlayConfig(max_position_weight=1))


def test_scan_cli_writes_v2_evidence_and_rejects_second_final_use(tmp_path):
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[1]
    code = '''
import runpy,sys
from pathlib import Path
from test_evaluation import synthetic_bars
from quant.data import research
from quant.backtest import report
research.load_market_bars=lambda *args: synthetic_bars(150)
report.RESULTS_DIR=Path(sys.argv[1]) / 'results'
sys.argv=['scripts/run_parameter_scan.py','--strategy','momentum','--market','us',
          '--study-file',str(Path(sys.argv[1])/'experiment.json'),'-p','lookback=3,5',
          '-p','top_n=1','-p','rebalance=5','--compact']
runpy.run_path('scripts/run_parameter_scan.py',run_name='__main__')
'''
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(root / "src"), str(root / "tests")])}
    command = [sys.executable, "-B", "-c", code, str(tmp_path)]
    preview = subprocess.run([sys.executable, "-B", "-c", code.replace("'--compact'", "'--preview'"), str(tmp_path)],
                             cwd=root, env=env, capture_output=True, text=True)
    assert preview.returncode == 0, preview.stderr
    assert json.loads(preview.stdout)["preview_only"] is True
    assert not (tmp_path / "experiment.json").exists()
    first = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    output = json.loads(first.stdout)
    assert output["final_test_status"] == "completed"
    artifact = json.loads((Path(output["run_dir"]) / "metrics.json").read_text())
    assert artifact["schema_version"] == 2
    assert artifact["research_protocol"]["selection_scope"] == "train_only"
    records = json.loads((Path(output["run_dir"]) / "scan.json").read_text())
    assert all("training" in record and "validation" not in record for record in records)
    second = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
    assert second.returncode != 0
    assert "final test already consumed" in second.stderr


def test_exploratory_backtest_cli_writes_new_execution_label(tmp_path):
    import json, os, subprocess, sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    code = '''
import runpy,sys
from pathlib import Path
from test_evaluation import synthetic_bars
from quant.data import research
from quant.backtest import report
research.load_market_bars=lambda *args: synthetic_bars(80)
report.RESULTS_DIR=Path(sys.argv[1])
sys.argv=['scripts/run_backtest.py','--strategy','momentum','--market','us','-p','lookback=5','-p','top_n=1']
runpy.run_path('scripts/run_backtest.py',run_name='__main__')
'''
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(root / "src"), str(root / "tests")]),
           "MPLCONFIGDIR": str(tmp_path / "matplotlib")}
    proc = subprocess.run([sys.executable, "-B", "-c", code, str(tmp_path)], cwd=root, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    output = json.loads(proc.stdout)
    assert output["execution_model"] == "next_open_v1"
    assert output["artifact_type"] == "exploratory_backtest"
    assert (Path(output["run_dir"]) / "execution.csv").exists()
