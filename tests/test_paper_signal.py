import json
import os
from pathlib import Path
import subprocess
import sys


def test_v4_paper_signal_binds_calendar_and_has_no_execution_prices(tmp_path):
    root = Path(__file__).resolve().parents[1]
    metrics = tmp_path / "metrics.json"
    metrics.write_text(json.dumps({
        "schema_version": 2,
        "artifact_type": "strategy_validation",
        "execution_model": "next_open_v1",
        "strategy": "momentum",
        "market": "us",
        "params": {"lookback": 5, "top_n": 1, "rebalance": 5},
        "universe": "synthetic",
        "universe_point_in_time": True,
        "membership_sha256": "m" * 64,
        "source_sha256": "s" * 64,
        "data_snapshot_sha256": "d" * 64,
        "risk_overlay": {},
        "research_protocol": {"selection_scope": "train_only"},
        "validation": {
            "final_test_status": "completed",
            "walk_forward": {"passed": True},
            "parameter_robustness": {"passed": True},
        },
    }), encoding="utf-8")
    code = '''
import runpy,sys
import numpy as np
import pandas as pd
from quant.data import research
from quant.data.research import MarketBars
index=pd.bdate_range(end=pd.Timestamp('2026-09-01'),periods=40)
close=pd.DataFrame({'A':10*np.cumprod(np.resize([1.01,1.002,.998],len(index)))},index=index)
opens=close/1.001
bars=MarketBars(opens,close,close.notna(),opens['A'],close['A'],'A',
                {'profile':'synthetic','point_in_time':True,'membership_sha256':'m'*64})
research.load_market_bars=lambda *args: bars
sys.argv=['scripts/generate_paper_signal.py',sys.argv[1]]
namespace=runpy.run_path('scripts/generate_paper_signal.py')
namespace['main'](pd.Timestamp('2026-09-02T00:00:00Z').to_pydatetime())
'''
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    command = [sys.executable, "-B", "-c", code, str(metrics)]
    first = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
    second = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
    assert first.returncode == second.returncode == 0, first.stderr or second.stderr
    one, two = json.loads(first.stdout), json.loads(second.stdout)
    assert one["schema_version"] == 4
    assert one["artifact_type"] == "paper_target_signal"
    assert one["execution_model"] == "next_open_v1"
    assert one["signal_id"] == two["signal_id"]
    assert len(one["strategy_package_sha256"]) == 64
    assert len(one["signal_data_sha256"]) == 64
    assert one["calendar_id"] == "exchange_calendars:4.13.2:XNYS"
    assert one["execution_prices_required"] is True
    assert "prices" not in one
    assert "reference_close_prices" in one

    gpt_src = root.parent / "gpt_quant" / "src"
    sys.path.insert(0, str(gpt_src))
    try:
        from gpt_quant.paper import PaperSignal

        parsed = PaperSignal.from_payload(one)
    finally:
        sys.path.remove(str(gpt_src))
    assert parsed.signal_id == one["signal_id"]
