"""组合级日频回测引擎。

执行约定（无前视）：
- 输入 decision 权重矩阵（date × symbol），decision.loc[t] 是基于 t 日及以前数据
  做出的目标权重，在 t 日收盘成交，持有该仓位赚取 t+1 日的收益。
- 现金隐含为 1 - sum(权重)，收益为 0。

A股约束（市场配置 limit_pct 非 None 时生效）：
- T+1：日频收盘调仓下天然满足（同一收盘时点不存在当日买入又卖出）。
- 涨跌停：当日涨幅 >= limit_pct 禁止加仓（买不进）；跌幅 <= -limit_pct 禁止减仓（卖不出），
  当日维持漂移后的实际仓位，次日继续尝试向目标调整。
- 停牌（价格 NaN）：当日收益按 0 计，仓位冻结不可交易。

费用模型：按调仓金额比例计费，买卖可不同费率（A股卖出含印花税）。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MarketConfig:
    buy_cost: float            # 买入费率（佣金+滑点）
    sell_cost: float           # 卖出费率（佣金+印花税+滑点）
    limit_pct: float | None    # 涨跌停判定阈值；None 表示无涨跌停


# A股：佣金约 0.03% + 滑点 0.1%；卖出另加印花税 0.05%
CN_MARKET = MarketConfig(buy_cost=0.0013, sell_cost=0.0018, limit_pct=0.098)
# 美股：零佣金时代，留 0.1% 覆盖滑点与点差
US_MARKET = MarketConfig(buy_cost=0.001, sell_cost=0.001, limit_pct=None)

MARKETS = {"cn": CN_MARKET, "us": US_MARKET}


@dataclass
class BacktestResult:
    nav: pd.Series           # 净值（首日=1）
    returns: pd.Series       # 日收益（费后）
    weights: pd.DataFrame    # 每日实际持仓权重（收盘调仓后）
    turnover: pd.Series      # 每日单边换手（|Δw| 之和 / 2）
    costs: pd.Series         # 每日费用（占 nav 比例）


def run(close: pd.DataFrame, decision: pd.DataFrame, cfg: MarketConfig) -> BacktestResult:
    """close 与 decision 需同 index（升序日期）、同 columns。decision 取值 [0,1] 且行和 <= 1。"""
    close = close.sort_index()
    decision = decision.reindex(index=close.index, columns=close.columns).fillna(0.0)
    if (decision.sum(axis=1) > 1.0 + 1e-9).any():
        raise ValueError("decision 权重行和不能超过 1")
    if ((decision < -1e-12).any()).any():
        raise ValueError("不支持做空：decision 权重必须 >= 0")

    px = close.to_numpy(dtype=float)
    dec = decision.to_numpy(dtype=float)
    n_days, n_sym = px.shape

    # 日收益：停牌(NaN)按 0 收益、价格沿用（仓位冻结由 tradeable 掩码保证）
    px_ffill = pd.DataFrame(px).ffill().to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        rets = px_ffill[1:] / px_ffill[:-1] - 1.0
    rets = np.vstack([np.zeros((1, n_sym)), np.nan_to_num(rets, nan=0.0)])
    suspended = np.isnan(px)

    w_prev = np.zeros(n_sym)
    nav = np.ones(n_days)
    day_ret = np.zeros(n_days)
    turnover = np.zeros(n_days)
    costs = np.zeros(n_days)
    weights = np.zeros((n_days, n_sym))

    for t in range(n_days):
        r = rets[t]
        gross = float(w_prev @ r)
        # 持仓随价格漂移（含隐含现金，分母为组合总收益）
        w_drift = w_prev * (1.0 + r) / (1.0 + gross) if gross > -1.0 else np.zeros(n_sym)

        target = dec[t].copy()
        # 停牌：冻结在漂移仓位
        target[suspended[t]] = w_drift[suspended[t]]
        if cfg.limit_pct is not None and t > 0:
            up = r >= cfg.limit_pct      # 涨停禁买
            dn = r <= -cfg.limit_pct     # 跌停禁卖
            blocked_buy = up & (target > w_drift)
            blocked_sell = dn & (target < w_drift)
            target[blocked_buy] = w_drift[blocked_buy]
            target[blocked_sell] = w_drift[blocked_sell]

        delta = target - w_drift
        buys = float(delta[delta > 0].sum())
        sells = float(-delta[delta < 0].sum())
        cost = buys * cfg.buy_cost + sells * cfg.sell_cost

        day_ret[t] = gross - cost
        nav[t] = (nav[t - 1] if t > 0 else 1.0) * (1.0 + day_ret[t])
        turnover[t] = (buys + sells) / 2.0
        costs[t] = cost
        weights[t] = target
        w_prev = target

    idx = close.index
    return BacktestResult(
        nav=pd.Series(nav, index=idx, name="nav"),
        returns=pd.Series(day_ret, index=idx, name="return"),
        weights=pd.DataFrame(weights, index=idx, columns=close.columns),
        turnover=pd.Series(turnover, index=idx, name="turnover"),
        costs=pd.Series(costs, index=idx, name="cost"),
    )
