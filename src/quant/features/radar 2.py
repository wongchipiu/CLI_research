"""Point-in-time daily features for the US watchlist radar."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import pandas as pd


class FeatureUnavailable(ValueError):
    """Raised with a stable reason when a symbol cannot be evaluated."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class DailyRadarFeatures:
    signal_date: str
    close: float
    ret_1d: float
    ret_5d: float
    ret_20d: float
    volume_ratio_20: float
    average_dollar_volume_20: float
    breakout_20: bool
    breakout_60: bool
    breakout_margin_20: float
    breakout_margin_60: float
    adjustment: str
    history_rows: int

    def to_dict(self) -> dict:
        return asdict(self)


def compute_daily_radar_features(
    frame: pd.DataFrame,
    signal_date: str | pd.Timestamp,
    *,
    min_history: int = 61,
) -> DailyRadarFeatures:
    """Calculate features using only bars on or before ``signal_date``.

    Breakouts compare the current close with the highest close in the prior
    20/60 valid sessions. The volume-ratio denominator excludes the current
    session. Missing rows are not filled or inferred.
    """
    if frame is None or frame.empty:
        raise FeatureUnavailable("no_data")
    required = {"date", "close", "volume", "volume_unit", "adjustment"}
    missing = required - set(frame.columns)
    if missing:
        raise FeatureUnavailable(f"missing_columns:{','.join(sorted(missing))}")

    target = pd.Timestamp(signal_date).tz_localize(None).normalize()
    work = frame.copy()
    try:
        work["date"] = pd.to_datetime(work["date"]).map(
            lambda value: pd.Timestamp(value).tz_localize(None).normalize()
        )
    except (TypeError, ValueError):
        raise FeatureUnavailable("invalid_dates") from None
    work = work.loc[work["date"] <= target].sort_values("date")
    work = work.drop_duplicates(subset="date", keep="last")
    if work.empty or work.iloc[-1]["date"] != target:
        raise FeatureUnavailable("missing_bar_on_signal_date")

    work["close"] = pd.to_numeric(work["close"], errors="coerce")
    work["volume"] = pd.to_numeric(work["volume"], errors="coerce")
    work = work.loc[
        work["close"].map(lambda value: math.isfinite(value) and value > 0)
        & work["volume"].map(lambda value: math.isfinite(value) and value >= 0)
    ]
    if work.empty or work.iloc[-1]["date"] != target:
        raise FeatureUnavailable("invalid_signal_bar")
    if len(work) < max(min_history, 61):
        raise FeatureUnavailable("insufficient_history")

    recent = work.iloc[-max(min_history, 61):]
    units = {str(value).lower() for value in recent["volume_unit"].dropna().unique()}
    if units != {"share"}:
        raise FeatureUnavailable("volume_unit_not_share")
    adjustments = {str(value) for value in recent["adjustment"].dropna().unique()}
    if len(adjustments) != 1:
        raise FeatureUnavailable("adjustment_missing_or_mixed")
    adjustment = next(iter(adjustments))

    close = work["close"].astype(float)
    volume = work["volume"].astype(float)
    if volume.iloc[-1] <= 0:
        raise FeatureUnavailable("zero_current_volume")
    previous_volume = volume.iloc[-21:-1]
    mean_volume = float(previous_volume.mean())
    if not math.isfinite(mean_volume) or mean_volume <= 0:
        raise FeatureUnavailable("invalid_volume_baseline")

    previous_close_20 = close.iloc[-21:-1]
    previous_close_60 = close.iloc[-61:-1]
    high_20 = float(previous_close_20.max())
    high_60 = float(previous_close_60.max())
    current_close = float(close.iloc[-1])
    average_dollar_volume = float(
        (close.iloc[-21:-1] * volume.iloc[-21:-1]).mean()
    )

    return DailyRadarFeatures(
        signal_date=str(target.date()),
        close=current_close,
        ret_1d=_return(close, 1),
        ret_5d=_return(close, 5),
        ret_20d=_return(close, 20),
        volume_ratio_20=float(volume.iloc[-1] / mean_volume),
        average_dollar_volume_20=average_dollar_volume,
        breakout_20=current_close > high_20,
        breakout_60=current_close > high_60,
        breakout_margin_20=current_close / high_20 - 1.0,
        breakout_margin_60=current_close / high_60 - 1.0,
        adjustment=adjustment,
        history_rows=len(work),
    )


def _return(close: pd.Series, periods: int) -> float:
    return float(close.iloc[-1] / close.iloc[-(periods + 1)] - 1.0)
