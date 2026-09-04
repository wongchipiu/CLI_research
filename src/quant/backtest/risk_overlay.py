"""Deterministic portfolio constraints applied after strategy signal generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RiskOverlayConfig:
    max_position_weight: float = 0.25
    max_gross_exposure: float = 1.0
    target_volatility: float | None = None
    volatility_window: int = 20
    regime_window: int | None = None
    risk_off_exposure: float = 0.0

    def __post_init__(self) -> None:
        if not 0 < self.max_position_weight <= 1:
            raise ValueError("max_position_weight must be in (0, 1]")
        if not 0 < self.max_gross_exposure <= 1:
            raise ValueError("max_gross_exposure must be in (0, 1]")
        if self.target_volatility is not None and self.target_volatility <= 0:
            raise ValueError("target_volatility must be positive")
        if self.volatility_window < 2:
            raise ValueError("volatility_window must be at least 2")
        if self.regime_window is not None and self.regime_window < 2:
            raise ValueError("regime_window must be at least 2")
        if not 0 <= self.risk_off_exposure <= 1:
            raise ValueError("risk_off_exposure must be in [0, 1]")

    def to_dict(self) -> dict:
        return asdict(self)


def apply_risk_overlay(
    close: pd.DataFrame,
    decision: pd.DataFrame,
    config: RiskOverlayConfig,
) -> pd.DataFrame:
    weights = decision.reindex(index=close.index, columns=close.columns).fillna(0.0)
    weights = weights.clip(lower=0.0, upper=config.max_position_weight)
    weights = _cap_gross(weights, config.max_gross_exposure)

    if config.target_volatility is not None:
        asset_returns = close.pct_change(fill_method=None).fillna(0.0)
        # t 日调仓只使用截至 t-1 的已实现组合收益估算波动。
        portfolio_returns = (weights.shift(1).fillna(0.0) * asset_returns).sum(axis=1)
        realized = (
            portfolio_returns.rolling(
                config.volatility_window,
                min_periods=config.volatility_window,
            ).std().shift(1) * np.sqrt(252)
        )
        scale = (config.target_volatility / realized.replace(0.0, np.nan)).clip(upper=1.0)
        weights = weights.mul(scale.fillna(0.0), axis=0)

    if config.regime_window is not None:
        first_valid = close.apply(lambda series: series.dropna().iloc[0] if series.notna().any() else np.nan)
        normalized = close.div(first_valid).mean(axis=1, skipna=True)
        trend = normalized.rolling(
            config.regime_window, min_periods=config.regime_window
        ).mean()
        exposure = pd.Series(
            np.where(normalized >= trend, 1.0, config.risk_off_exposure),
            index=close.index,
        )
        exposure[trend.isna()] = 0.0
        weights = weights.mul(exposure, axis=0)

    return _cap_gross(weights, config.max_gross_exposure)


def _cap_gross(weights: pd.DataFrame, limit: float) -> pd.DataFrame:
    gross = weights.sum(axis=1)
    scale = (limit / gross.replace(0.0, np.nan)).clip(upper=1.0).fillna(1.0)
    return weights.mul(scale, axis=0)
