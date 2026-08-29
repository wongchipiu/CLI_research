"""三个基线策略：双均线、动量轮动、布林带均值回归。

权重分配约定：信号型策略每个标的固定份额 1/N（N=池内标的数），无信号部分留现金，
避免单一标的信号导致全仓集中。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from quant.strategies.base import register


@register("sma_cross")
def sma_cross(close: pd.DataFrame, fast: int = 20, slow: int = 60) -> pd.DataFrame:
    """双均线：快线在慢线上方持有，否则空仓。"""
    f = close.rolling(fast, min_periods=fast).mean()
    s = close.rolling(slow, min_periods=slow).mean()
    sig = (f > s).astype(float)
    return sig / close.shape[1]


@register("momentum")
def momentum(close: pd.DataFrame, lookback: int = 120, top_n: int = 2,
             rebalance: int = 20) -> pd.DataFrame:
    """动量轮动：每 rebalance 个交易日，按过去 lookback 日收益取前 top_n 等权持有。
    动量为负的标的不持有（绝对动量过滤）。"""
    mom = close / close.shift(lookback) - 1.0
    w = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    reb_idx = range(lookback, len(close), rebalance)
    for i in reb_idx:
        row = mom.iloc[i].dropna()
        row = row[row > 0]
        picks = row.nlargest(top_n).index
        if len(picks):
            w.iloc[i, [close.columns.get_loc(p) for p in picks]] = 1.0 / top_n
    # 调仓日之间维持权重；调仓日之前全为 0
    mask = pd.Series(False, index=close.index)
    mask.iloc[list(reb_idx)] = True
    w.loc[~mask] = np.nan
    return w.ffill().fillna(0.0)


@register("boll_revert")
def boll_revert(close: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    """布林带均值回归：跌破下轨买入，回到中轨卖出。"""
    mid = close.rolling(window, min_periods=window).mean()
    sd = close.rolling(window, min_periods=window).std()
    lower = mid - num_std * sd
    entry = close < lower
    exit_ = close > mid
    # 状态机：entry→1, exit→0, 其余沿用前值
    state = pd.DataFrame(np.nan, index=close.index, columns=close.columns)
    state[entry] = 1.0
    state[exit_] = 0.0
    state = state.ffill().fillna(0.0)
    return state / close.shape[1]


@register("momentum_vol")
def momentum_vol(
    close: pd.DataFrame,
    lookback: int = 120,
    vol_window: int = 20,
    top_n: int = 3,
    rebalance: int = 20,
) -> pd.DataFrame:
    """Positive momentum selection with inverse-volatility position sizing."""
    momentum_score = close / close.shift(lookback) - 1.0
    volatility = close.pct_change(fill_method=None).rolling(
        vol_window, min_periods=vol_window
    ).std() * np.sqrt(252)
    weights = pd.DataFrame(np.nan, index=close.index, columns=close.columns)
    for index in range(max(lookback, vol_window), len(close), rebalance):
        scores = momentum_score.iloc[index].dropna()
        picks = scores[scores > 0].nlargest(top_n).index
        if len(picks):
            inverse_vol = 1.0 / volatility.loc[close.index[index], picks].replace(0.0, np.nan)
            inverse_vol = inverse_vol.dropna()
            if len(inverse_vol):
                weights.loc[close.index[index], inverse_vol.index] = inverse_vol / inverse_vol.sum()
        weights.loc[close.index[index]] = weights.loc[close.index[index]].fillna(0.0)
    return weights.ffill().fillna(0.0)


@register("trend_momentum")
def trend_momentum(
    close: pd.DataFrame,
    lookback: int = 120,
    trend_window: int = 200,
    top_n: int = 3,
    rebalance: int = 20,
) -> pd.DataFrame:
    """Momentum rotation that moves to cash when the equal-weight market trend is weak."""
    weights = momentum(close, lookback=lookback, top_n=top_n, rebalance=rebalance)
    first_valid = close.apply(lambda series: series.dropna().iloc[0] if series.notna().any() else np.nan)
    market_proxy = close.div(first_valid).mean(axis=1, skipna=True)
    trend = market_proxy.rolling(trend_window, min_periods=trend_window).mean()
    risk_on = (market_proxy >= trend).astype(float)
    return weights.mul(risk_on, axis=0)


@register("relative_strength")
def relative_strength(
    close: pd.DataFrame,
    lookback: int = 120,
    top_n: int = 3,
    rebalance: int = 20,
) -> pd.DataFrame:
    """Hold positive assets whose momentum also exceeds the cross-sectional median."""
    score = close / close.shift(lookback) - 1.0
    weights = pd.DataFrame(np.nan, index=close.index, columns=close.columns)
    for index in range(lookback, len(close), rebalance):
        row = score.iloc[index].dropna()
        eligible = row[(row > 0) & (row > row.median())]
        picks = eligible.nlargest(top_n).index
        weights.loc[close.index[index]] = 0.0
        if len(picks):
            weights.loc[close.index[index], picks] = 1.0 / len(picks)
    return weights.ffill().fillna(0.0)
