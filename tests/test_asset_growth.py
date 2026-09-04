import pandas as pd
import pytest

from quant.asset_growth import analyze_asset_growth


def test_growth_separates_contributions_from_investment_gain():
    frame = pd.DataFrame({
        "date": ["2026-01-01", "2026-06-30", "2026-12-31"],
        "total_assets": [100_000, 115_000, 130_000],
        "net_contribution": [0, 10_000, 10_000],
        "core_assets": [70_000, 80_000, 90_000],
        "strategy_assets": [10_000, 12_000, 15_000],
        "cash": [20_000, 23_000, 25_000],
    })
    report = analyze_asset_growth(frame)
    assert report.net_worth_growth == pytest.approx(0.30)
    assert report.net_contributions == 20_000
    assert report.investment_gain == 10_000
    assert report.investment_return_on_start == pytest.approx(0.10)


def test_component_mismatch_is_rejected():
    frame = pd.DataFrame({
        "date": ["2026-01-01", "2026-02-01"],
        "total_assets": [100, 110],
        "net_contribution": [0, 0],
        "core_assets": [50, 50],
        "strategy_assets": [20, 20],
        "cash": [20, 20],
    })
    with pytest.raises(ValueError):
        analyze_asset_growth(frame)
