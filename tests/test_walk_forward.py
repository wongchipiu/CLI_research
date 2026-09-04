import numpy as np
import pandas as pd
import pytest

from quant.backtest.engine import MarketConfig
from quant.backtest.evaluation import evaluate_walk_forward


NO_FEE = MarketConfig(buy_cost=0.0, sell_cost=0.0, limit_pct=None)


def test_walk_forward_builds_non_overlapping_oos_folds():
    index = pd.bdate_range("2020-01-01", periods=400)
    close = pd.DataFrame({"A": np.linspace(10.0, 30.0, 400)}, index=index)
    decision = pd.DataFrame(1.0, index=index, columns=["A"])
    evaluation = evaluate_walk_forward(
        close, decision, NO_FEE, train_days=100, test_days=50
    )
    payload = evaluation.to_dict()
    assert payload["fold_count"] == 6
    assert payload["positive_fold_ratio"] == 1.0
    assert payload["aggregate"]["total_return"] > 0


def test_walk_forward_rejects_insufficient_history():
    index = pd.bdate_range("2024-01-01", periods=100)
    close = pd.DataFrame({"A": np.linspace(10.0, 11.0, 100)}, index=index)
    decision = pd.DataFrame(1.0, index=index, columns=["A"])
    with pytest.raises(ValueError):
        evaluate_walk_forward(close, decision, NO_FEE, train_days=80, test_days=30)


def test_train_selected_folds_do_not_stitch_independent_accounts():
    from quant.backtest.study import walk_forward
    from quant.backtest.risk_overlay import RiskOverlayConfig
    from test_evaluation import synthetic_bars, choose_asset
    bars = synthetic_bars(120)
    output = walk_forward(bars, choose_asset, {"choice": ["A", "B"]}, NO_FEE,
                          RiskOverlayConfig(max_position_weight=1), train_days=40, test_days=20)
    assert output["fold_count"] == 4
    assert output["accounting"] == "independent_folds_not_continuous_nav"
    assert "aggregate" not in output
    for fold in output["folds"]:
        assert fold["train"]["end"] == fold["selected_at"] < fold["test"]["start"]
    first_params = output["folds"][0]["selected_params"]
    bars.close.iloc[40:60, 1] *= 10
    changed = walk_forward(bars, choose_asset, {"choice": ["A", "B"]}, NO_FEE,
                           RiskOverlayConfig(max_position_weight=1), train_days=40, test_days=20)
    assert changed["folds"][0]["selected_params"] == first_params
