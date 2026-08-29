"""Structured daily-bar quality checks used by scripts and research agents."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from quant.data import storage


@dataclass(frozen=True)
class QualityReport:
    market: str
    symbol: str
    status: str
    rows: int
    start: str | None
    end: str | None
    missing_rate: float
    missing_business_days: int
    suspension_days: int
    return_outliers: int
    stale_days: int
    duplicate_dates: int
    invalid_prices: int
    sources: tuple[str, ...]
    adjustments: tuple[str, ...]
    volume_units: tuple[str, ...]
    volume_normalized: bool
    issues: tuple[str, ...]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["sources"] = list(self.sources)
        payload["adjustments"] = list(self.adjustments)
        payload["volume_units"] = list(self.volume_units)
        payload["issues"] = list(self.issues)
        return payload

    def to_text(self) -> str:
        coverage = f"{self.start} ~ {self.end}" if self.start else "empty"
        details = "; ".join(self.issues) if self.issues else "OK"
        return (
            f"{self.market}/{self.symbol}: {self.rows} 行, {coverage}, "
            f"缺失率={self.missing_rate:.2%}, 停牌={self.suspension_days}, "
            f"异常收益={self.return_outliers}, volume={','.join(self.volume_units) or 'unknown'} "
            f"[{self.status}: {details}]"
        )


def analyze_daily(market: str, symbol: str, frame: pd.DataFrame | None) -> QualityReport:
    if frame is None or frame.empty:
        return QualityReport(
            market, symbol, "ERROR", 0, None, None, 1.0, 0, 0, 0, 0, 0, 0,
            (), (), (), False, ("无数据",),
        )

    df = frame.copy()
    dates = pd.to_datetime(df["date"])
    duplicate_dates = int(dates.duplicated().sum())
    missing_cells = int(df[storage.REQUIRED_COLS].isna().sum().sum())
    missing_rate = missing_cells / (len(df) * len(storage.REQUIRED_COLS))
    prices = df[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    invalid_prices = int(
        ((prices <= 0).any(axis=1) | (prices["high"] < prices["low"])).sum()
    )
    expected = pd.bdate_range(dates.min().normalize(), dates.max().normalize())
    missing_business_days = len(expected.difference(pd.DatetimeIndex(dates.dt.normalize())))
    suspension_days = int((pd.to_numeric(df["volume"], errors="coerce") == 0).sum())
    returns = prices["close"].pct_change(fill_method=None)
    outlier_limit = 0.11 if market == "cn" else 0.20
    if market == "cn-index":
        outlier_limit = 0.15
    return_outliers = int((returns.abs() > outlier_limit).sum())
    stale_days = max(0, int((pd.Timestamp.today().normalize() - dates.max().normalize()).days))
    sources = _values(df, "source")
    adjustments = _values(df, "adjustment")
    volume_units = _values(df, "volume_unit")
    volume_normalized = volume_units == ("share",)

    errors = []
    warnings = []
    if duplicate_dates:
        errors.append(f"重复日期 {duplicate_dates}")
    if invalid_prices:
        errors.append(f"非法价格 {invalid_prices}")
    if missing_rate > 0:
        errors.append(f"必需字段缺失率 {missing_rate:.2%}")
    if not dates.is_monotonic_increasing:
        errors.append("日期未升序")
    if not volume_normalized:
        errors.append(f"成交量单位未统一: {volume_units or ('unknown',)}")
    if return_outliers:
        warnings.append(f"异常涨跌幅 {return_outliers}")
    if stale_days > 7:
        warnings.append(f"数据滞后 {stale_days} 天")
    if len(sources) > 1:
        warnings.append(f"混合数据源 {','.join(sources)}")
    status = "ERROR" if errors else "WARN" if warnings else "OK"
    return QualityReport(
        market=market,
        symbol=symbol,
        status=status,
        rows=len(df),
        start=str(dates.min().date()),
        end=str(dates.max().date()),
        missing_rate=round(missing_rate, 6),
        missing_business_days=missing_business_days,
        suspension_days=suspension_days,
        return_outliers=return_outliers,
        stale_days=stale_days,
        duplicate_dates=duplicate_dates,
        invalid_prices=invalid_prices,
        sources=sources,
        adjustments=adjustments,
        volume_units=volume_units,
        volume_normalized=volume_normalized,
        issues=tuple(errors + warnings),
    )


def _values(frame: pd.DataFrame, column: str) -> tuple[str, ...]:
    if column not in frame.columns:
        return ()
    return tuple(sorted({str(value) for value in frame[column].dropna().unique()}))
