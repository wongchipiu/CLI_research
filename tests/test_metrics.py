import numpy as np
import pandas as pd
import pytest

from quant.backtest import metrics


def test_max_drawdown_known():
    nav = pd.Series([1.0, 1.2, 0.9, 1.1, 0.8],
                    index=pd.bdate_range("2024-01-01", periods=5))
    # 峰值 1.2 → 最低 0.8：-1/3
    assert metrics.max_drawdown(nav) == pytest.approx(-1 / 3)


def test_cagr_doubling():
    n = metrics.TRADING_DAYS + 1
    nav = pd.Series(np.linspace(1, 2, n), index=pd.bdate_range("2024-01-01", periods=n))
    assert metrics.cagr(nav) == pytest.approx(1.0)  # 一年翻倍 = 100%


def test_sharpe_zero_vol():
    r = pd.Series(0.0, index=pd.bdate_range("2024-01-01", periods=10))
    assert metrics.sharpe(r) == 0.0


def test_summarize_with_benchmark():
    idx = pd.bdate_range("2024-01-01", periods=100)
    nav = pd.Series(np.linspace(1, 1.5, 100), index=idx)
    ret = nav / nav.shift(1) - 1
    bench = pd.Series(np.linspace(1, 1.2, 100), index=idx)
    m = metrics.summarize(nav, ret.fillna(0), pd.Series(0.01, index=idx), bench)
    assert m["total_return"] == pytest.approx(0.5)
    assert m["benchmark"]["total_return"] == pytest.approx(0.2)
    assert m["excess_cagr"] > 0
    assert m["ann_turnover"] == pytest.approx(0.01 * 252)


def test_completed_positions_counts_only_held_to_flat_transitions():
    weights = pd.DataFrame(
        {"A": [0.0, 1.0, 1.0, 0.0, 0.0], "B": [0.0, 0.5, 0.0, 0.5, 0.0]},
        index=pd.bdate_range("2024-01-01", periods=5),
    )
    assert metrics.completed_positions(weights) == 3


def test_summary_includes_initial_fee_and_initial_equity_peak():
    index = pd.bdate_range("2026-01-05", periods=2)
    nav = pd.Series([1 / 1.01, .99 / 1.01], index=index)
    returns = nav / nav.shift(1, fill_value=1) - 1
    result = metrics.summarize(nav, returns, pd.Series(0.5, index=index))
    assert result["total_return"] == pytest.approx(-.0198)
    assert result["max_drawdown"] == pytest.approx(-.0198)
    assert result["annualization_periods"] == 2


def test_missing_starting_benchmark_is_not_filled_from_future():
    index = pd.bdate_range("2026-01-05", periods=3)
    nav = pd.Series([1., 1., 1.], index=index)
    benchmark = pd.Series([np.nan, 100., 110.], index=index)
    result = metrics.summarize(nav, nav - 1, nav - 1, benchmark)
    assert "benchmark" not in result
    assert result["benchmark_status"] == "missing_initial_or_aligned_quote"
