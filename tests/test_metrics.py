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
