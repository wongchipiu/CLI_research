import numpy as np
import pandas as pd
import pytest

from quant.backtest import engine
from quant.backtest.engine import MarketConfig

NOFEE_CN = MarketConfig(buy_cost=0.0, sell_cost=0.0, limit_pct=0.098)
NOFEE_US = MarketConfig(buy_cost=0.0, sell_cost=0.0, limit_pct=None)


def make(prices: dict, dates=None) -> pd.DataFrame:
    df = pd.DataFrame(prices)
    df.index = pd.bdate_range("2024-01-01", periods=len(df)) if dates is None else pd.to_datetime(dates)
    return df


def full_weight(close, w=1.0):
    return pd.DataFrame(w, index=close.index, columns=close.columns)


def test_costs_charged_on_buy_and_sell():
    cfg = MarketConfig(buy_cost=0.001, sell_cost=0.002, limit_pct=None)
    close = make({"A": [10.0, 10.0, 10.0, 10.0]})
    dec = full_weight(close, 0.0)
    dec.iloc[1] = 1.0  # 第2天买入
    dec.iloc[2] = 0.0  # 第3天清仓
    res = engine.run(close, dec, cfg)
    # 价格不动：nav = (1-0.001) * (1-0.002)
    assert res.nav.iloc[-1] == pytest.approx((1 - 0.001) * (1 - 0.002))
    assert res.turnover.sum() == pytest.approx(1.0)  # 单边 0.5 + 0.5


def test_execution_lag_no_lookahead():
    # 决策日当天的涨幅不应计入收益：t 日收盘买入，赚 t+1 收益
    close = make({"A": [10.0, 20.0, 30.0]})
    dec = full_weight(close, 0.0)
    dec.iloc[1] = 1.0  # 信号在第2天（当天涨100%不应赚到）
    res = engine.run(close, dec, NOFEE_US)
    # 只赚第3天的 50%
    assert res.nav.iloc[-1] == pytest.approx(1.5)


def test_limit_up_blocks_buy():
    # 第2天涨停（+10%）当天发出买入信号，应被禁止；第3天涨幅正常后买入
    close = make({"A": [10.0, 11.0, 11.5, 12.0]})
    dec = full_weight(close, 1.0)
    dec.iloc[0] = 0.0  # 第1天无信号
    res = engine.run(close, dec, NOFEE_CN)
    assert res.weights.iloc[1, 0] == 0.0   # 涨停日买不进
    assert res.weights.iloc[2, 0] == 1.0   # 次日买入
    # 收益只来自第4天: 12/11.5
    assert res.nav.iloc[-1] == pytest.approx(12.0 / 11.5)


def test_limit_down_blocks_sell():
    # 持仓后第3天跌停（-10%），清仓指令被禁止，仓位冻结到次日
    close = make({"A": [10.0, 10.0, 9.0, 9.0]})
    dec = full_weight(close, 0.0)
    dec.iloc[0] = 1.0
    dec.iloc[1] = 1.0
    dec.iloc[2] = 0.0  # 跌停日想卖
    dec.iloc[3] = 0.0
    res = engine.run(close, dec, NOFEE_CN)
    assert res.weights.iloc[2, 0] > 0.99   # 跌停日卖不出（漂移后仍满仓）
    assert res.weights.iloc[3, 0] == 0.0   # 次日卖出
    assert res.nav.iloc[-1] == pytest.approx(0.9)


def test_suspension_freezes_position():
    close = make({"A": [10.0, np.nan, np.nan, 12.0], "B": [10.0, 10.0, 10.0, 10.0]})
    dec = pd.DataFrame({"A": [0.5, 0.0, 0.0, 0.0], "B": [0.5, 0.5, 0.5, 0.5]},
                       index=close.index)
    res = engine.run(close, dec, NOFEE_US)
    # 停牌期间 A 仓位冻结、收益为 0；复牌日按累计涨幅一次性体现
    assert res.weights.iloc[1]["A"] == pytest.approx(0.5)
    assert res.returns.iloc[1] == pytest.approx(0.0)
    assert res.returns.iloc[2] == pytest.approx(0.0)
    assert res.nav.iloc[-1] == pytest.approx(1 + 0.5 * 0.2)  # A 复牌 +20%


def test_weights_sum_validation():
    close = make({"A": [10.0, 11.0], "B": [10.0, 11.0]})
    dec = full_weight(close, 0.6)  # 行和 1.2 > 1
    with pytest.raises(ValueError):
        engine.run(close, dec, NOFEE_US)
    with pytest.raises(ValueError):
        engine.run(close, full_weight(close, -0.1), NOFEE_US)


def test_cash_earns_zero():
    close = make({"A": [10.0, 12.0, 15.0]})
    dec = full_weight(close, 0.5)  # 半仓
    res = engine.run(close, dec, NOFEE_US)
    # 第2天半仓赚 20% 的一半 = 10%
    assert res.returns.iloc[1] == pytest.approx(0.10)
