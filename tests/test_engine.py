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
    # 买入金额必须预留买入费，随后全卖时扣除卖出费。
    bought = 1.0 / (1.0 + cfg.buy_cost)
    assert res.nav.iloc[-1] == pytest.approx(bought * (1 - cfg.sell_cost))
    assert res.turnover.sum() == pytest.approx((bought + 1.0) / 2.0)


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


@pytest.mark.parametrize("cfg", [NOFEE_US, engine.US_MARKET])
def test_suspended_full_position_cannot_fund_rotation(cfg):
    close = make({"A": [10.0, np.nan, 12.0], "B": [10.0, 10.0, 10.0]})
    dec = pd.DataFrame({"A": [1.0, 0.0, 0.0], "B": [0.0, 1.0, 1.0]}, index=close.index)
    res = engine.run(close, dec, cfg)

    assert res.weights.iloc[1].to_dict() == pytest.approx({"A": 1.0, "B": 0.0})
    assert res.costs.iloc[1] == pytest.approx(0.0)
    assert res.weights.iloc[2].to_dict() == pytest.approx({"A": 0.0, "B": 1.0})
    assert res.nav.iloc[2] == pytest.approx(
        res.nav.iloc[0] * 1.2 * (1 - cfg.sell_cost) / (1 + cfg.buy_cost)
    )


def test_limit_down_position_cannot_fund_another_buy():
    close = make({"A": [10.0, 9.0, 9.0], "B": [10.0, 10.0, 10.0]})
    dec = pd.DataFrame({"A": [1.0, 0.0, 0.0], "B": [0.0, 1.0, 1.0]}, index=close.index)
    res = engine.run(close, dec, engine.CN_MARKET)

    assert res.weights.iloc[1].to_dict() == pytest.approx({"A": 1.0, "B": 0.0})
    assert res.turnover.iloc[1] == pytest.approx(0.0)
    assert res.weights.iloc[2, 1] == pytest.approx(1.0)
    assert (res.weights.sum(axis=1) <= 1.0 + 1e-12).all()


def test_partial_freeze_preserves_quantity_and_scales_buys_after_sell_fees():
    cfg = MarketConfig(buy_cost=0.01, sell_cost=0.02, limit_pct=None)
    close = make({"A": [10.0, np.nan], "B": [10.0, 10.0], "C": [10.0, 10.0], "D": [10.0, 10.0]})
    dec = pd.DataFrame(
        {"A": [0.5, 0.0], "B": [0.25, 0.0], "C": [0.0, 0.6], "D": [0.0, 0.4]},
        index=close.index,
    )
    res = engine.run(close, dec, cfg)
    values = res.weights.mul(res.nav, axis=0)

    # 初始 A=0.5、B=0.25，扣除买入费后现金=0.2425。
    available = 1.0 - 0.75 * (1 + cfg.buy_cost) + 0.25 * (1 - cfg.sell_cost)
    bought = available / (1 + cfg.buy_cost)
    assert values.iloc[1].to_dict() == pytest.approx(
        {"A": 0.5, "B": 0.0, "C": bought * 0.6, "D": bought * 0.4}
    )
    assert res.nav.iloc[1] == pytest.approx(0.5 + bought)
    assert res.costs.iloc[1] * res.nav.iloc[0] == pytest.approx(0.25 * cfg.sell_cost + bought * cfg.buy_cost)
    assert (1.0 - res.weights.sum(axis=1) >= -1e-12).all()


def test_sale_and_gross_return_use_consistent_equity_for_costs():
    cfg = MarketConfig(buy_cost=0.01, sell_cost=0.02, limit_pct=None)
    close = make({"A": [10.0, 20.0]})
    dec = pd.DataFrame({"A": [0.5, 0.0]}, index=close.index)
    res = engine.run(close, dec, cfg)

    # 第一天买 0.5，现金 0.495；第二天持仓价值 1，卖出净收入 0.98。
    assert res.nav.iloc[0] == pytest.approx(0.995)
    assert res.nav.iloc[1] == pytest.approx(1.475)
    assert res.costs.iloc[1] * res.nav.iloc[0] == pytest.approx(0.02)
    assert res.returns.iloc[1] == pytest.approx(1.475 / 0.995 - 1.0)


def test_missing_initial_and_all_symbol_quotes_are_not_backfilled_or_traded():
    close = make({"A": [np.nan, 10.0, np.nan, 12.0], "B": [10.0, 10.0, np.nan, 10.0]})
    dec = pd.DataFrame({"A": [1.0, 1.0, 0.0, 0.0], "B": [0.0, 0.0, 1.0, 1.0]}, index=close.index)
    res = engine.run(close, dec, NOFEE_US)

    assert res.weights.iloc[0].sum() == 0.0
    assert res.weights.iloc[2].to_dict() == pytest.approx({"A": 1.0, "B": 0.0})
    assert res.nav.to_list() == pytest.approx([1.0, 1.0, 1.0, 1.2])


@pytest.mark.parametrize("cfg", [NOFEE_US, engine.US_MARKET, engine.CN_MARKET])
def test_cash_ledger_reconciles_mixed_rebalances_and_frozen_quantities(cfg):
    rng = np.random.default_rng(20260828)
    values = 10.0 * np.cumprod(1 + rng.uniform(-0.15, 0.15, (64, 3)), axis=0)
    values[rng.random(values.shape) < 0.2] = np.nan
    close = make(dict(zip(["A", "B", "C"], values.T)))
    raw_weights = rng.random(values.shape)
    raw_weights[raw_weights < 0.4] = 0.0
    dec = pd.DataFrame(raw_weights / np.maximum(raw_weights.sum(axis=1, keepdims=True), 1.0),
                       index=close.index, columns=close.columns)
    result = engine.run(close, dec, cfg)

    # 独立用成交数量与现金收支对账，不复用引擎的预算/权重计算。
    marks = close.ffill()
    quantities = result.weights.mul(result.nav, axis=0).div(marks).fillna(0.0)
    changes = quantities - quantities.shift(1, fill_value=0.0)
    traded_values = (changes * marks).fillna(0.0)
    buys = traded_values.clip(lower=0.0).sum(axis=1)
    sells = -traded_values.clip(upper=0.0).sum(axis=1)
    fees = buys * cfg.buy_cost + sells * cfg.sell_cost
    cash = 1.0 + (sells - buys - fees).cumsum()

    assert cash.min() >= -1e-12
    np.testing.assert_allclose(result.nav, cash + (quantities * marks).sum(axis=1), atol=1e-12)
    np.testing.assert_allclose(result.costs * result.nav.shift(1, fill_value=1.0), fees, atol=1e-12)
    assert np.abs(changes.to_numpy()[close.isna().to_numpy()]).max() < 1e-12
    if cfg.limit_pct is not None:
        returns = marks.pct_change(fill_method=None).fillna(0.0)
        assert not ((returns >= cfg.limit_pct) & (changes > 1e-12)).any().any()
        assert not ((returns <= -cfg.limit_pct) & (changes < -1e-12)).any().any()


@pytest.mark.parametrize("invalid_price", [0.0, -1.0, np.inf, -np.inf])
def test_invalid_prices_cannot_create_cash_or_exposure(invalid_price):
    close = make({"A": [10.0, invalid_price]})
    with pytest.raises(ValueError, match="price|价格"):
        engine.run(close, full_weight(close), NOFEE_US)


@pytest.mark.parametrize("invalid_weight", [np.inf, -np.inf])
def test_nonfinite_decisions_are_rejected(invalid_weight):
    close = make({"A": [10.0, 10.0]})
    with pytest.raises(ValueError):
        engine.run(close, full_weight(close, invalid_weight), NOFEE_US)


@pytest.mark.parametrize("buy_cost,sell_cost", [(-0.1, 0.0), (np.nan, 0.0), (0.0, np.inf), (0.0, 1.0)])
def test_invalid_fees_are_rejected(buy_cost, sell_cost):
    with pytest.raises(ValueError, match="cost|费率"):
        MarketConfig(buy_cost=buy_cost, sell_cost=sell_cost, limit_pct=None)
