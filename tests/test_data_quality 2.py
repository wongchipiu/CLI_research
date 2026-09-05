import pandas as pd

from quant.data.quality import analyze_daily


def make_frame():
    return pd.DataFrame(
        {
            "date": pd.bdate_range("2026-01-01", periods=5),
            "open": [10.0] * 5,
            "high": [10.5] * 5,
            "low": [9.5] * 5,
            "close": [10.0] * 5,
            "volume": [1000] * 5,
            "source": ["test"] * 5,
            "adjustment": ["qfq"] * 5,
            "volume_unit": ["share"] * 5,
        }
    )


def test_quality_report_exposes_required_agent_fields():
    report = analyze_daily("us", "TEST", make_frame())
    payload = report.to_dict()
    assert payload["missing_rate"] == 0
    assert payload["suspension_days"] == 0
    assert payload["return_outliers"] == 0
    assert payload["volume_normalized"] is True


def test_quality_report_rejects_unknown_volume_unit():
    frame = make_frame().drop(columns=["volume_unit"])
    report = analyze_daily("us", "TEST", frame)
    assert report.status == "ERROR"
    assert any("成交量单位未统一" in issue for issue in report.issues)
