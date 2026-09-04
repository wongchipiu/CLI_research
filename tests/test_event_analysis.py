import pandas as pd

from quant.research.event_analysis import analyze_event


def _frame(values: list[float]) -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-02", periods=len(values))
    return pd.DataFrame(
        {
            "date": dates,
            "open": values,
            "high": values,
            "low": values,
            "close": values,
            "volume": 1,
        }
    )


def test_event_reaction_uses_next_session_for_after_close_report():
    asset = _frame([100.0, 101.0, 110.0, 108.0, 112.0])
    benchmark = _frame([100.0, 100.0, 101.0, 101.0, 102.0])
    event_date = str(asset.loc[1, "date"].date())

    result = analyze_event(
        asset,
        benchmark,
        symbol="TEST",
        benchmark_symbol="SPY",
        event_date=event_date,
    )

    assert result["event"]["reaction_date"] == str(asset.loc[2, "date"].date())
    assert result["event"]["reaction_close_return"] == round(110 / 101 - 1, 4)
    assert result["performance"]["1d"] == round(112 / 108 - 1, 4)


def test_metrics_are_bounded_or_finite():
    asset = _frame([100 + index for index in range(260)])
    benchmark = _frame([100 + index * 0.5 for index in range(260)])
    event_date = str(asset.loc[250, "date"].date())

    result = analyze_event(
        asset,
        benchmark,
        symbol="TEST",
        benchmark_symbol="SPY",
        event_date=event_date,
    )

    assert 0 <= result["trend"]["position_in_52w_range"] <= 1
    assert result["risk"]["max_drawdown_252d"] == 0.0
