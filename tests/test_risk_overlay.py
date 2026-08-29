import numpy as np
import pandas as pd

from quant.backtest.risk_overlay import RiskOverlayConfig, apply_risk_overlay


def test_overlay_caps_positions_and_gross_exposure():
    index = pd.bdate_range("2024-01-01", periods=30)
    close = pd.DataFrame({"A": np.linspace(10, 12, 30), "B": np.linspace(10, 11, 30)}, index=index)
    decision = pd.DataFrame(0.8, index=index, columns=close.columns)
    result = apply_risk_overlay(
        close,
        decision,
        RiskOverlayConfig(max_position_weight=0.3, max_gross_exposure=0.5),
    )
    assert (result.max(axis=1) <= 0.3 + 1e-12).all()
    assert (result.sum(axis=1) <= 0.5 + 1e-12).all()


def test_target_volatility_uses_cash_during_warmup():
    index = pd.bdate_range("2024-01-01", periods=40)
    close = pd.DataFrame({"A": 100 * np.cumprod(np.repeat(1.01, 40))}, index=index)
    decision = pd.DataFrame(1.0, index=index, columns=["A"])
    result = apply_risk_overlay(
        close,
        decision,
        RiskOverlayConfig(target_volatility=0.1, volatility_window=10),
    )
    assert (result.iloc[:10] == 0).all().all()


def test_regime_filter_moves_to_cash_in_downtrend():
    index = pd.bdate_range("2024-01-01", periods=50)
    close = pd.DataFrame({"A": np.linspace(100, 50, 50)}, index=index)
    decision = pd.DataFrame(1.0, index=index, columns=["A"])
    result = apply_risk_overlay(
        close,
        decision,
        RiskOverlayConfig(regime_window=10),
    )
    assert result.iloc[-1, 0] == 0.0
