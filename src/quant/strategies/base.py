"""策略统一接口与注册表。

策略 = 函数: (close: DataFrame[date × symbol], **params) -> decision 权重 DataFrame。
约定：
- decision.loc[t] 只能使用 t 日及以前的数据（引擎在 t 收盘执行、赚 t+1 收益）。
- 权重取值 [0,1]，行和 <= 1，剩余为现金。
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

StrategyFn = Callable[..., pd.DataFrame]

_REGISTRY: dict[str, StrategyFn] = {}


def register(name: str):
    def deco(fn: StrategyFn) -> StrategyFn:
        _REGISTRY[name] = fn
        return fn
    return deco


def get_strategy(name: str) -> StrategyFn:
    if name not in _REGISTRY:
        raise KeyError(f"未知策略 {name!r}，可选: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def list_strategies() -> list[str]:
    return sorted(_REGISTRY)
