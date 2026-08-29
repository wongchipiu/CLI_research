"""组合级日频回测引擎。

执行约定（无前视）：
- 输入 decision 权重矩阵（date × symbol），decision.loc[t] 是基于 t 日及以前数据
  做出的目标权重，在 t 日收盘成交，持有该仓位赚取 t+1 日的收益。
- 现金隐含为 1 - sum(权重)，收益为 0。
- 目标金额按调仓前净值计算，实际持仓权重按扣费后净值计算。

A股约束（市场配置 limit_pct 非 None 时生效）：
- T+1：日频收盘调仓下天然满足（同一收盘时点不存在当日买入又卖出）。
- 涨跌停：当日涨幅 >= limit_pct 禁止加仓（买不进）；跌幅 <= -limit_pct 禁止减仓（卖不出），
  当日维持漂移后的实际仓位，次日继续尝试向目标调整。
- 停牌（价格 NaN）：当日收益按 0 计，仓位冻结不可交易。

费用模型：按实际成交金额计费，买卖可不同费率（A股卖出含印花税）。
先卖后买；买入金额与费用之和不得超过可用现金，冻结资产不参与融资。
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

    def __post_init__(self) -> None:
        if any(not np.isfinite(cost) or not 0 <= cost < 1 for cost in (self.buy_cost, self.sell_cost)):
            raise ValueError("buy_cost/sell_cost 费率必须为 [0, 1) 内的有限数")
        if self.limit_pct is not None and not 0 < self.limit_pct < 1:
            raise ValueError("limit_pct 必须为 (0, 1) 内的有限数或 None")


# A股：佣金约 0.03% + 滑点 0.1%；卖出另加印花税 0.05%
CN_MARKET = MarketConfig(buy_cost=0.0013, sell_cost=0.0018, limit_pct=0.098)
# 美股：零佣金时代，留 0.1% 覆盖滑点与点差
US_MARKET = MarketConfig(buy_cost=0.001, sell_cost=0.001, limit_pct=None)

MARKETS = {"cn": CN_MARKET, "us": US_MARKET}


@dataclass
class BacktestResult:
    nav: pd.Series           # 净值（初始资金=1，首日成交也扣费）
    returns: pd.Series       # 日收益（费后）
    weights: pd.DataFrame    # 每日实际持仓权重（收盘调仓后）
    turnover: pd.Series      # 实际成交金额 / 调仓前净值 / 2
    costs: pd.Series         # 每日费用 / 上一日净值（首日分母为 1）


def run(close: pd.DataFrame, decision: pd.DataFrame, cfg: MarketConfig) -> BacktestResult:
    """close 保留缺失报价 NaN；decision 取值 [0,1] 且行和 <= 1，缺失目标按零处理。"""
    if close.empty:
        raise ValueError("close 价格矩阵不能为空")
    close = close.sort_index()
    decision = decision.reindex(index=close.index, columns=close.columns).fillna(0.0)
    if not np.isfinite(decision.to_numpy(dtype=float)).all():
        raise ValueError("decision 权重必须为有限数")
    if (decision.sum(axis=1) > 1.0 + 1e-9).any():
        raise ValueError("decision 权重行和不能超过 1")
    if ((decision < 0).any()).any():
        raise ValueError("不支持做空：decision 权重必须 >= 0")

    px = close.to_numpy(dtype=float)
    quoted = ~np.isnan(px)
    if (quoted & (~np.isfinite(px) | (px <= 0))).any():
        raise ValueError("close 价格必须为正有限数或 NaN")
    dec = decision.to_numpy(dtype=float)
    n_days, n_sym = px.shape

    # 先从原始报价建立可交易掩码；前填仅用于估值，不能创造交易报价。
    tradeable = quoted
    valuation_px = pd.DataFrame(px).ffill().to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        rets = valuation_px[1:] / valuation_px[:-1] - 1.0
    rets = np.vstack([np.zeros((1, n_sym)), np.nan_to_num(rets, nan=0.0)])

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
        target[~tradeable[t]] = w_drift[~tradeable[t]]
        if cfg.limit_pct is not None and t > 0:
            up = r >= cfg.limit_pct      # 涨停禁买
            dn = r <= -cfg.limit_pct     # 跌停禁卖
            blocked_buy = up & (target > w_drift)
            blocked_sell = dn & (target < w_drift)
            target[blocked_buy] = w_drift[blocked_buy]
            target[blocked_sell] = w_drift[blocked_sell]

        # 所有成交金额先以调仓前净值计量。仅可执行的卖出才释放现金。
        sell_amounts = np.maximum(w_drift - target, 0.0)
        buy_amounts = np.maximum(target - w_drift, 0.0)
        sells = float(sell_amounts.sum())
        requested_buys = float(buy_amounts.sum())
        cash = max(0.0, 1.0 - float(w_drift.sum()))
        available = cash + sells * (1.0 - cfg.sell_cost)
        if requested_buys > 0:
            scale = min(1.0, available / (requested_buys * (1.0 + cfg.buy_cost)))
            buy_amounts *= scale
        buys = float(buy_amounts.sum())
        fee = buys * cfg.buy_cost + sells * cfg.sell_cost
        net_factor = 1.0 - fee
        # 冻结数量保持不变；费用改变分母，因此输出必须是费后实际权重。
        held = w_drift - sell_amounts + buy_amounts
        actual_weights = held / net_factor

        day_ret[t] = (1.0 + gross) * net_factor - 1.0
        nav[t] = (nav[t - 1] if t > 0 else 1.0) * (1.0 + day_ret[t])
        turnover[t] = (buys + sells) / 2.0
        costs[t] = (1.0 + gross) * fee
        weights[t] = actual_weights
        w_prev = actual_weights

    idx = close.index
    return BacktestResult(
        nav=pd.Series(nav, index=idx, name="nav"),
        returns=pd.Series(day_ret, index=idx, name="return"),
        weights=pd.DataFrame(weights, index=idx, columns=close.columns),
        turnover=pd.Series(turnover, index=idx, name="turnover"),
        costs=pd.Series(costs, index=idx, name="cost"),
    )
