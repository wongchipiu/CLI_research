"""绩效指标计算。所有年化按 252 个交易日。"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def max_drawdown(nav: pd.Series) -> float:
    peak = nav.cummax()
    return float((nav / peak - 1.0).min())


def cagr(nav: pd.Series) -> float:
    n = len(nav)
    if n < 2 or nav.iloc[0] <= 0:
        return 0.0
    return float((nav.iloc[-1] / nav.iloc[0]) ** (TRADING_DAYS / (n - 1)) - 1.0)


def sharpe(returns: pd.Series, rf: float = 0.0) -> float:
    ex = returns - rf / TRADING_DAYS
    sd = ex.std()
    if sd == 0 or np.isnan(sd):
        return 0.0
    return float(ex.mean() / sd * np.sqrt(TRADING_DAYS))


def summarize(
    nav: pd.Series,
    returns: pd.Series,
    turnover: pd.Series,
    benchmark_nav: pd.Series | None = None,
) -> dict:
    mdd = max_drawdown(nav)
    g = cagr(nav)
    m = {
        "start": str(nav.index[0].date()),
        "end": str(nav.index[-1].date()),
        "n_days": int(len(nav)),
        "total_return": round(float(nav.iloc[-1] / nav.iloc[0] - 1.0), 4),
        "cagr": round(g, 4),
        "ann_vol": round(float(returns.std() * np.sqrt(TRADING_DAYS)), 4),
        "sharpe": round(sharpe(returns), 3),
        "max_drawdown": round(mdd, 4),
        "calmar": round(g / abs(mdd), 3) if mdd < 0 else None,
        "daily_win_rate": round(float((returns > 0).sum() / max((returns != 0).sum(), 1)), 4),
        "ann_turnover": round(float(turnover.mean() * TRADING_DAYS), 2),
    }
    if benchmark_nav is not None and len(benchmark_nav) > 1:
        b = benchmark_nav.reindex(nav.index).ffill()
        b = b / b.iloc[0]
        b_ret = b / b.shift(1) - 1.0
        m["benchmark"] = {
            "total_return": round(float(b.iloc[-1] - 1.0), 4),
            "cagr": round(cagr(b), 4),
            "max_drawdown": round(max_drawdown(b), 4),
            "sharpe": round(sharpe(b_ret.fillna(0.0)), 3),
        }
        m["excess_cagr"] = round(m["cagr"] - m["benchmark"]["cagr"], 4)
    return m
