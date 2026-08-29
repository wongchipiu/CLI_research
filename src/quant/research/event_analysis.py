"""Deterministic price analysis around a corporate event."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


TRADING_DAYS = 252


def _indexed(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"]).dt.tz_localize(None)
        out = out.set_index("date")
    out.index = pd.to_datetime(out.index).tz_localize(None)
    return out.sort_index()


def _period_return(close: pd.Series, days: int) -> float | None:
    if len(close) <= days:
        return None
    return float(close.iloc[-1] / close.iloc[-days - 1] - 1.0)


def _rounded(value: float | None, digits: int = 4) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return round(float(value), digits)


def _max_drawdown(close: pd.Series) -> float:
    nav = close / close.iloc[0]
    return float((nav / nav.cummax() - 1.0).min())


def _rsi(close: pd.Series, window: int = 14) -> float | None:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = -delta.clip(upper=0).rolling(window).mean()
    relative_strength = gain / loss.replace(0.0, np.nan)
    result = 100.0 - 100.0 / (1.0 + relative_strength)
    if result.empty or pd.isna(result.iloc[-1]):
        return None
    return float(result.iloc[-1])


def _event_reaction(frame: pd.DataFrame, event_date: str) -> dict[str, Any]:
    event = pd.Timestamp(event_date)
    before = frame.loc[frame.index <= event]
    after = frame.loc[frame.index > event]
    if before.empty or after.empty:
        return {"event_date": event_date, "reaction_date": None}
    report_session = before.index[-1]
    reaction_session = after.index[0]
    report_close = float(before.iloc[-1]["close"])
    reaction = after.iloc[0]
    reaction_open = float(reaction["open"])
    reaction_close = float(reaction["close"])
    latest_close = float(frame.iloc[-1]["close"])
    return {
        "event_date": event_date,
        "report_session": str(report_session.date()),
        "reaction_date": str(reaction_session.date()),
        "open_gap": _rounded(reaction_open / report_close - 1.0),
        "reaction_close_return": _rounded(reaction_close / report_close - 1.0),
        "reaction_intraday_return": _rounded(reaction_close / reaction_open - 1.0),
        "return_since_report_close": _rounded(latest_close / report_close - 1.0),
    }


def analyze_event(
    frame: pd.DataFrame,
    benchmark_frame: pd.DataFrame,
    *,
    symbol: str,
    benchmark_symbol: str,
    event_date: str,
) -> dict[str, Any]:
    price = _indexed(frame)
    benchmark = _indexed(benchmark_frame)
    close = price["close"].dropna()
    benchmark_close = benchmark["close"].reindex(close.index).ffill().dropna()
    close = close.reindex(benchmark_close.index)
    returns = close.pct_change(fill_method=None).dropna()
    benchmark_returns = benchmark_close.pct_change(fill_method=None).dropna()

    windows = (1, 5, 20, 60, 120, 252)
    performance = {f"{days}d": _rounded(_period_return(close, days)) for days in windows}
    benchmark_performance = {
        f"{days}d": _rounded(_period_return(benchmark_close, days)) for days in windows
    }
    excess = {
        key: _rounded(performance[key] - benchmark_performance[key])
        if performance[key] is not None and benchmark_performance[key] is not None
        else None
        for key in performance
    }

    trend: dict[str, Any] = {}
    for window in (20, 50, 200):
        average = close.rolling(window).mean().iloc[-1]
        trend[f"vs_ma{window}"] = _rounded(close.iloc[-1] / average - 1.0)
    trailing_year = close.iloc[-min(len(close), TRADING_DAYS) :]
    year_low = float(trailing_year.min())
    year_high = float(trailing_year.max())
    trend.update(
        {
            "rsi14": _rounded(_rsi(close), 1),
            "from_52w_high": _rounded(close.iloc[-1] / year_high - 1.0),
            "position_in_52w_range": _rounded(
                (close.iloc[-1] - year_low) / (year_high - year_low)
                if year_high > year_low
                else 1.0
            ),
        }
    )

    common = pd.concat([returns, benchmark_returns], axis=1, join="inner").dropna()
    common.columns = ["asset", "benchmark"]
    lookback = common.iloc[-min(len(common), 60) :]
    benchmark_variance = lookback["benchmark"].var()
    beta = (
        lookback["asset"].cov(lookback["benchmark"]) / benchmark_variance
        if benchmark_variance > 0
        else None
    )
    risk = {
        "ann_vol_20d": _rounded(returns.iloc[-20:].std() * np.sqrt(TRADING_DAYS)),
        "ann_vol_60d": _rounded(returns.iloc[-60:].std() * np.sqrt(TRADING_DAYS)),
        "beta_60d": _rounded(beta, 2),
        "correlation_60d": _rounded(lookback["asset"].corr(lookback["benchmark"]), 2),
        "max_drawdown_252d": _rounded(_max_drawdown(trailing_year)),
    }

    return {
        "symbol": symbol.upper(),
        "benchmark": benchmark_symbol.upper(),
        "as_of": str(close.index[-1].date()),
        "latest_close": round(float(close.iloc[-1]), 4),
        "performance": performance,
        "benchmark_performance": benchmark_performance,
        "excess_performance": excess,
        "trend": trend,
        "risk": risk,
        "event": _event_reaction(price, event_date),
    }


def peer_snapshot(frame: pd.DataFrame, symbol: str) -> dict[str, Any]:
    close = _indexed(frame)["close"].dropna()
    return {
        "symbol": symbol.upper(),
        "as_of": str(close.index[-1].date()),
        "latest_close": round(float(close.iloc[-1]), 4),
        "return_5d": _rounded(_period_return(close, 5)),
        "return_20d": _rounded(_period_return(close, 20)),
        "return_60d": _rounded(_period_return(close, 60)),
        "return_252d": _rounded(_period_return(close, 252)),
    }


__all__ = ["analyze_event", "peer_snapshot"]
