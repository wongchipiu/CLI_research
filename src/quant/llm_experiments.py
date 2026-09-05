"""Deterministic B0-B3 comparison and negative-control reporting."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import random
from statistics import mean
from pathlib import Path
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ExperimentSeries:
    name: str
    net_returns: tuple[float, ...]
    model_cost: float = 0.0

    def __post_init__(self) -> None:
        if self.name not in {"B0", "B1", "B2", "B3", "N1", "N2"}:
            raise ValueError("unknown experiment series")
        if not self.net_returns or any(not isinstance(x, (int, float)) or isinstance(x, bool) for x in self.net_returns):
            raise ValueError("series must contain finite numeric returns")
        if any(x != x or abs(x) == float("inf") for x in self.net_returns):
            raise ValueError("series contains non-finite returns")
        if self.model_cost < 0:
            raise ValueError("model cost cannot be negative")


@dataclass(frozen=True)
class ComparisonReport:
    challenger: str
    baseline: str
    sample_count: int
    mean_increment: float
    lower_95: float
    upper_95: float
    cost_adjusted_increment: float
    status: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "challenger": self.challenger, "baseline": self.baseline, "sample_count": self.sample_count,
            "mean_increment": self.mean_increment, "lower_95": self.lower_95, "upper_95": self.upper_95,
            "cost_adjusted_increment": self.cost_adjusted_increment, "status": self.status, "reason": self.reason,
        }


@dataclass(frozen=True)
class ExperimentReport:
    experiment_id: str
    comparisons: tuple[ComparisonReport, ...]
    status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "artifact_type": "llm_experiment_report",
            "experiment_id": self.experiment_id,
            "status": self.status,
            "comparisons": [item.to_dict() for item in self.comparisons],
        }

    def to_markdown(self) -> str:
        lines = [f"# LLM experiment {self.experiment_id}", "", f"Status: **{self.status}**", "", "| Compare | N | Increment | 95% interval | Cost-adjusted | Status |", "|---|---:|---:|---:|---:|---|"]
        for item in self.comparisons:
            lines.append(f"| {item.challenger} - {item.baseline} | {item.sample_count} | {item.mean_increment:.6f} | [{item.lower_95:.6f}, {item.upper_95:.6f}] | {item.cost_adjusted_increment:.6f} | {item.status} |")
        return "\n".join(lines) + "\n"


def build_experiment_report(
    experiment_id: str,
    series: Mapping[str, ExperimentSeries],
    *,
    min_samples: int = 30,
    bootstrap_samples: int = 2000,
    seed: int = 0,
) -> ExperimentReport:
    required = ("B0", "B1", "B2", "B3")
    if any(name not in series for name in required):
        raise ValueError("B0, B1, B2 and B3 are required")
    comparisons = (
        compare_series(series["B0"], series["B1"], min_samples=min_samples, bootstrap_samples=bootstrap_samples, seed=seed),
        compare_series(series["B1"], series["B2"], min_samples=min_samples, bootstrap_samples=bootstrap_samples, seed=seed),
        compare_series(series["B2"], series["B3"], min_samples=min_samples, bootstrap_samples=bootstrap_samples, seed=seed),
    )
    status = "PASS" if all(item.status == "PASS" for item in comparisons) else "INCONCLUSIVE"
    return ExperimentReport(experiment_id, comparisons, status)


def write_experiment_report(report: ExperimentReport, output: str | Path) -> tuple[Path, Path]:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    json_path = destination.with_suffix(".json")
    markdown_path = destination.with_suffix(".md")
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(report.to_markdown(), encoding="utf-8")
    return json_path, markdown_path


def compare_series(
    baseline: ExperimentSeries,
    challenger: ExperimentSeries,
    *,
    min_samples: int = 30,
    bootstrap_samples: int = 2000,
    seed: int = 0,
) -> ComparisonReport:
    if baseline.name not in {"B0", "B1", "B2", "N1", "N2"} or challenger.name not in {"B1", "B2", "B3", "N1", "N2"}:
        raise ValueError("series pair is not a supported comparison")
    if len(baseline.net_returns) != len(challenger.net_returns):
        raise ValueError("series must use the same event sample")
    differences = tuple(c - b for b, c in zip(baseline.net_returns, challenger.net_returns))
    point = mean(differences)
    samples = _bootstrap_means(differences, bootstrap_samples, seed)
    lower, upper = _percentile(samples, .025), _percentile(samples, .975)
    cost_adjusted = point - challenger.model_cost / max(len(differences), 1)
    if len(differences) < min_samples:
        status, reason = "INCONCLUSIVE", "independent event sample is below the frozen minimum"
    elif lower <= 0:
        status, reason = "INCONCLUSIVE", "the 95% increment interval includes zero"
    else:
        status, reason = "PASS", "increment remains positive after model cost"
    if cost_adjusted <= 0 and status == "PASS":
        status, reason = "INCONCLUSIVE", "model cost removes the positive increment"
    return ComparisonReport(challenger.name, baseline.name, len(differences), point, lower, upper, cost_adjusted, status, reason)


def negative_control(series: ExperimentSeries, *, seed: int = 0) -> ExperimentSeries:
    """Return a deterministic date/event permutation without changing values."""
    values = list(series.net_returns)
    random.Random(seed).shuffle(values)
    name = "N1" if series.name != "N1" else "N2"
    return ExperimentSeries(name, tuple(values), series.model_cost)


def _bootstrap_means(values: Sequence[float], count: int, seed: int) -> tuple[float, ...]:
    if count <= 0:
        raise ValueError("bootstrap_samples must be positive")
    rng = random.Random(seed)
    return tuple(mean(rng.choices(values, k=len(values))) for _ in range(count))


def _percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)
