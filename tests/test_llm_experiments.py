import pytest

from quant.llm_experiments import ExperimentSeries, build_experiment_report, compare_series, negative_control


def test_compare_series_is_deterministic_and_blocks_small_or_uncertain_samples():
    baseline = ExperimentSeries("B2", tuple([0.01] * 40))
    challenger = ExperimentSeries("B3", tuple([0.02] * 40), model_cost=0.01)
    first = compare_series(baseline, challenger, bootstrap_samples=100, seed=7)
    second = compare_series(baseline, challenger, bootstrap_samples=100, seed=7)
    assert first == second
    assert first.status == "PASS"
    assert compare_series(ExperimentSeries("B2", (0.0,)), ExperimentSeries("B3", (0.1,))).status == "INCONCLUSIVE"


def test_negative_control_preserves_values_but_changes_order():
    source = ExperimentSeries("B3", (0.01, 0.02, 0.03, 0.04))
    shuffled = negative_control(source, seed=3)
    assert shuffled.name == "N1"
    assert sorted(shuffled.net_returns) == list(source.net_returns)
    assert shuffled.net_returns != source.net_returns


def test_compare_rejects_mismatched_samples():
    with pytest.raises(ValueError, match="same event sample"):
        compare_series(ExperimentSeries("B2", (0.1,)), ExperimentSeries("B3", (0.1, 0.2)))


def test_build_report_requires_all_baselines_and_is_inconclusive_on_small_samples():
    series = {name: ExperimentSeries(name, tuple([0.01] * 3)) for name in ("B0", "B1", "B2", "B3")}
    report = build_experiment_report("exp-1", series, bootstrap_samples=20)
    assert report.status == "INCONCLUSIVE"
    assert len(report.comparisons) == 3
    assert report.to_dict()["artifact_type"] == "llm_experiment_report"
