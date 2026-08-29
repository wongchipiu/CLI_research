import pandas as pd
import pytest

from quant.data.membership import apply_membership, load_membership


def test_membership_masks_prices_outside_effective_interval(tmp_path):
    path = tmp_path / "history.csv"
    path.write_text(
        "market,symbol,effective_from,effective_to\n"
        "us,A,2026-01-02,2026-01-05\n",
        encoding="utf-8",
    )
    history = load_membership(path, "us")
    index = pd.date_range("2026-01-01", "2026-01-06")
    close = pd.DataFrame({"A": 10.0}, index=index)
    masked = apply_membership(close, history)
    assert pd.isna(masked.loc["2026-01-01", "A"])
    assert masked.loc["2026-01-03", "A"] == 10.0
    assert pd.isna(masked.loc["2026-01-06", "A"])


def test_overlapping_membership_intervals_are_rejected(tmp_path):
    path = tmp_path / "history.csv"
    path.write_text(
        "market,symbol,effective_from,effective_to\n"
        "us,A,2026-01-01,2026-02-01\n"
        "us,A,2026-01-15,2026-03-01\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_membership(path, "us")
