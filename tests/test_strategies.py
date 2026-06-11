import numpy as np
import pandas as pd

from quant.strategies import get_strategy, list_strategies


def idx(n):
    return pd.bdate_range("2023-01-02", periods=n)


def test_registry():
    assert {"sma_cross", "momentum", "boll_revert"} <= set(list_strategies())


def test_sma_cross_uptrend_long():
    n = 100
    close = pd.DataFrame({"A": np.linspace(10, 30, n)}, index=idx(n))
    w = get_strategy("sma_cross")(close, fast=5, slow=20)
    assert w.iloc[-1, 0] == 1.0          # 持续上涨 → 满份额（单标的 1/1）
    assert (w.iloc[:19] == 0).all().all()  # 慢线未形成前不开仓


def test_momentum_picks_winner():
    n = 200
    close = pd.DataFrame({
        "WIN": np.linspace(10, 40, n),    # 强势
        "LOSE": np.linspace(40, 10, n),   # 下跌（绝对动量过滤应排除）
        "FLAT": np.full(n, 20.0),
    }, index=idx(n))
    w = get_strategy("momentum")(close, lookback=60, top_n=1, rebalance=20)
    assert w["WIN"].iloc[-1] == 1.0
    assert w["LOSE"].sum() == 0.0


def test_boll_revert_state_machine():
    n = 60
    base = np.full(n, 100.0)
    base[40] = 80.0   # 第41天暴跌破下轨
    close = pd.DataFrame({"A": base}, index=idx(n))
    w = get_strategy("boll_revert")(close, window=20, num_std=2.0)
    assert w.iloc[40, 0] > 0      # 破下轨 → 买入
    assert w.iloc[41, 0] == 0.0   # 次日回到中轨上方 → 卖出


def test_weights_valid_range():
    n = 150
    rng = np.random.default_rng(7)
    close = pd.DataFrame(
        100 * np.cumprod(1 + rng.normal(0, 0.02, size=(n, 4)), axis=0),
        index=idx(n), columns=list("ABCD"))
    for name in list_strategies():
        w = get_strategy(name)(close)
        assert (w.to_numpy() >= 0).all(), name
        assert (w.sum(axis=1) <= 1.0 + 1e-9).all(), name
