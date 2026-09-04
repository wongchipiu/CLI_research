"""绩效指标计算。所有年化按 252 个交易日。"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def max_drawdown(nav: pd.Series, initial_nav: float | None = None) -> float:
    peak = nav.cummax()
    if initial_nav is not None:
        peak = peak.clip(lower=initial_nav)
    return float((nav / peak - 1.0).min())


def cagr(nav: pd.Series, initial_nav: float | None = None, periods: int | None = None) -> float:
    n = periods if periods is not None else len(nav) - 1
    initial = float(nav.iloc[0]) if initial_nav is None else initial_nav
    if n < 1 or initial <= 0:
        return 0.0
    return float((nav.iloc[-1] / initial) ** (TRADING_DAYS / n) - 1.0)


def sharpe(returns: pd.Series, rf: float = 0.0) -> float:
    ex = returns - rf / TRADING_DAYS
    sd = ex.std()
    if sd == 0 or np.isnan(sd):
        return 0.0
    return float(ex.mean() / sd * np.sqrt(TRADING_DAYS))


def completed_positions(weights: pd.DataFrame, tolerance: float = 1e-8) -> int:
    """Count symbol-level held-to-flat transitions as completed trades."""
    held = weights.fillna(0.0).abs() > tolerance
    exits = held.shift(1, fill_value=False) & ~held
    return int(exits.to_numpy().sum())


def summarize(
    nav: pd.Series,
    returns: pd.Series,
    turnover: pd.Series,
    benchmark_nav: pd.Series | None = None,
    weights: pd.DataFrame | None = None,
    *,
    initial_nav: float = 1.0,
    benchmark_initial: float | None = None,
) -> dict:
    if nav.empty or not np.isfinite(initial_nav) or initial_nav <= 0:
        raise ValueError("nonempty NAV and positive initial_nav are required")
    mdd = max_drawdown(nav, initial_nav)
    g = cagr(nav, initial_nav, len(nav))
    m = {
        "start": str(nav.index[0].date()),
        "end": str(nav.index[-1].date()),
        "n_days": int(len(nav)),
        "initial_nav": initial_nav,
        "annualization_periods": len(nav),
        "total_return": round(float(nav.iloc[-1] / initial_nav - 1.0), 4),
        "cagr": round(g, 4),
        "ann_vol": round(float(returns.std() * np.sqrt(TRADING_DAYS)), 4),
        "sharpe": round(sharpe(returns), 3),
        "max_drawdown": round(mdd, 4),
        "calmar": round(g / abs(mdd), 3) if mdd < 0 else None,
        "daily_win_rate": round(float((returns > 0).sum() / max((returns != 0).sum(), 1)), 4),
        "ann_turnover": round(float(turnover.mean() * TRADING_DAYS), 2),
        "trade_days": int((turnover > 1e-8).sum()),
        "completed_trades": completed_positions(weights) if weights is not None else 0,
    }
    m["benchmark_status"] = "unavailable"
    if benchmark_nav is not None and len(benchmark_nav) > 1:
        b = benchmark_nav.reindex(nav.index).ffill()
        initial = b.iloc[0] if benchmark_initial is None else benchmark_initial
        if b.isna().any() or not np.isfinite(initial) or initial <= 0:
            m["benchmark_status"] = "missing_initial_or_aligned_quote"
            return m
        b = b / initial
        b_ret = b / b.shift(1, fill_value=1.0) - 1.0
        m["benchmark_status"] = "available"
        m["benchmark"] = {
            "total_return": round(float(b.iloc[-1] - 1.0), 4),
            "cagr": round(cagr(b, 1.0, len(b)), 4),
            "max_drawdown": round(max_drawdown(b, 1.0), 4),
            "sharpe": round(sharpe(b_ret.fillna(0.0)), 3),
        }
        m["excess_cagr"] = round(m["cagr"] - m["benchmark"]["cagr"], 4)
    return m
