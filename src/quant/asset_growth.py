"""Net-worth growth decomposition with external cash-flow separation."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


REQUIRED_COLUMNS = ["date", "total_assets", "net_contribution"]


@dataclass(frozen=True)
class AssetGrowthReport:
    start: str
    end: str
    start_assets: float
    end_assets: float
    net_contributions: float
    investment_gain: float
    net_worth_growth: float
    contribution_rate: float
    investment_return_on_start: float
    time_weighted_return: float
    target_growth: float
    target_gap: float

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def analyze_asset_growth(frame: pd.DataFrame, target_growth: float = 0.25) -> AssetGrowthReport:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"asset ledger missing columns: {missing}")
    if len(frame) < 2:
        raise ValueError("asset ledger requires at least two snapshots")
    ledger = frame.copy()
    ledger["date"] = pd.to_datetime(ledger["date"])
    ledger = ledger.sort_values("date")
    if ledger["date"].duplicated().any():
        raise ValueError("asset ledger dates must be unique")
    if (ledger["total_assets"] <= 0).any():
        raise ValueError("total_assets must be positive")
    component_columns = ["core_assets", "strategy_assets", "cash"]
    if all(column in ledger.columns for column in component_columns):
        component_total = ledger[component_columns].sum(axis=1)
        if not ((component_total - ledger["total_assets"]).abs() <= 0.01).all():
            raise ValueError("core_assets + strategy_assets + cash must equal total_assets")

    start_assets = float(ledger.iloc[0]["total_assets"])
    end_assets = float(ledger.iloc[-1]["total_assets"])
    contributions = float(ledger.iloc[1:]["net_contribution"].sum())
    investment_gain = end_assets - start_assets - contributions
    net_worth_growth = end_assets / start_assets - 1.0
    period_returns = []
    for index in range(1, len(ledger)):
        previous = float(ledger.iloc[index - 1]["total_assets"])
        current = float(ledger.iloc[index]["total_assets"])
        contribution = float(ledger.iloc[index]["net_contribution"])
        period_returns.append((current - contribution) / previous - 1.0)
    time_weighted = float(pd.Series([1.0 + value for value in period_returns]).prod() - 1.0)
    return AssetGrowthReport(
        start=str(ledger.iloc[0]["date"].date()),
        end=str(ledger.iloc[-1]["date"].date()),
        start_assets=round(start_assets, 2),
        end_assets=round(end_assets, 2),
        net_contributions=round(contributions, 2),
        investment_gain=round(investment_gain, 2),
        net_worth_growth=round(net_worth_growth, 6),
        contribution_rate=round(contributions / start_assets, 6),
        investment_return_on_start=round(investment_gain / start_assets, 6),
        time_weighted_return=round(time_weighted, 6),
        target_growth=target_growth,
        target_gap=round(net_worth_growth - target_growth, 6),
    )
