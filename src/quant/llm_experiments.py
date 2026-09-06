"""Deterministic B0-B3 comparison and negative-control reporting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import math
import random
from statistics import mean
from pathlib import Path
from typing import Mapping, Sequence


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class ExperimentSeries:
    name: str
    net_returns: tuple[float, ...]
    model_cost: float = 0.0
    coverage: float = 1.0
    abstention_rate: float = 0.0
    max_drawdown: float = 0.0
    turnover: float = 0.0
    capacity_notional: float = 0.0

    def __post_init__(self) -> None:
        if self.name not in {"B0", "B1", "B2", "B3", "N1", "N2"}:
            raise ValueError("unknown experiment series")
        if not self.net_returns or any(not isinstance(x, (int, float)) or isinstance(x, bool) for x in self.net_returns):
            raise ValueError("series must contain finite numeric returns")
        if any(x != x or abs(x) == float("inf") for x in self.net_returns):
            raise ValueError("series contains non-finite returns")
        if not math.isfinite(self.model_cost) or self.model_cost < 0:
            raise ValueError("model cost cannot be negative")
        for name, value in (
            ("coverage", self.coverage),
            ("abstention_rate", self.abstention_rate),
            ("max_drawdown", self.max_drawdown),
            ("turnover", self.turnover),
            ("capacity_notional", self.capacity_notional),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        if not 0 <= self.coverage <= 1:
            raise ValueError("coverage must be in [0, 1]")
        if not 0 <= self.abstention_rate <= 1:
            raise ValueError("abstention_rate must be in [0, 1]")
        if self.max_drawdown < 0 or self.turnover < 0 or self.capacity_notional < 0:
            raise ValueError("risk and capacity metrics cannot be negative")


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
    cost_adjusted = point - (challenger.model_cost - baseline.model_cost) / max(len(differences), 1)
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


@dataclass(frozen=True)
class LLMExperimentManifest:
    """Frozen, provider-neutral protocol for the SEC/Radar experiment."""

    hypothesis: str
    universe_sha256: str
    data_snapshot_sha256: str
    feature_version: str
    final_test_start: str
    final_test_end: str
    baseline: str = "B2"
    primary_challenger: str = "B3"
    primary_horizon_days: int = 5
    max_trials: int = 20
    min_samples: int = 30
    min_coverage: float = 0.8
    max_abstention_rate: float = 0.2
    max_drawdown: float = 0.2
    max_turnover: float = 100.0
    min_capacity_notional: float = 0.0
    cost_stress_bps: tuple[float, ...] = (0.0, 10.0, 25.0)

    @property
    def experiment_id(self) -> str:
        payload = {
            key: value
            for key, value in self.__dict__.items()
            if key not in {"status"}
        }
        return canonical_hash(payload)

    def __post_init__(self) -> None:
        for name in ("universe_sha256", "data_snapshot_sha256"):
            value = getattr(self, name)
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")
        if not self.hypothesis or not self.feature_version:
            raise ValueError("hypothesis and feature_version are required")
        if self.baseline != "B2" or self.primary_challenger != "B3":
            raise ValueError("the frozen MVP comparison must be B3 against B2")
        if not self.final_test_start or not self.final_test_end or self.final_test_start >= self.final_test_end:
            raise ValueError("final test dates are invalid")
        if self.primary_horizon_days <= 0 or self.max_trials <= 0 or self.min_samples <= 0:
            raise ValueError("horizon, trial budget and minimum samples must be positive")
        for name, value in (
            ("min_coverage", self.min_coverage),
            ("max_abstention_rate", self.max_abstention_rate),
        ):
            if isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be in [0, 1]")
        for name, value in (
            ("max_drawdown", self.max_drawdown),
            ("max_turnover", self.max_turnover),
            ("min_capacity_notional", self.min_capacity_notional),
        ):
            if isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be a nonnegative finite number")
        if (
            not self.cost_stress_bps
            or any(isinstance(value, bool) or not math.isfinite(value) or value < 0 for value in self.cost_stress_bps)
            or tuple(sorted(set(self.cost_stress_bps))) != self.cost_stress_bps
        ):
            raise ValueError("cost_stress_bps must be sorted, unique and nonnegative")

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "LLMExperimentManifest":
        if payload.get("schema_version") != 1 or payload.get("artifact_type") != "llm_experiment_manifest":
            raise ValueError("expected llm_experiment_manifest schema_version 1")
        required = {
            "hypothesis", "universe_sha256", "data_snapshot_sha256", "feature_version",
            "final_test_start", "final_test_end",
        }
        missing = sorted(required - payload.keys())
        if missing:
            raise ValueError(f"manifest is missing fields: {missing}")
        fields = {
            name: payload[name]
            for name in (
                "hypothesis", "universe_sha256", "data_snapshot_sha256", "feature_version",
                "final_test_start", "final_test_end", "baseline", "primary_challenger",
                "primary_horizon_days", "max_trials", "min_samples", "min_coverage",
                "max_abstention_rate", "max_drawdown", "max_turnover", "min_capacity_notional",
                "cost_stress_bps",
            )
            if name in payload
        }
        if "cost_stress_bps" in fields:
            fields["cost_stress_bps"] = tuple(fields["cost_stress_bps"])
        return cls(**fields)


class ExperimentLedger:
    """Append-only ledger that makes a frozen final test single-use."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.manifest: LLMExperimentManifest | None = None
        self.trials: set[str] = set()
        self.final_test_consumed = False
        self._load()

    def register(self, manifest: LLMExperimentManifest) -> str:
        if self.manifest is not None and self.manifest.experiment_id != manifest.experiment_id:
            raise ValueError("ledger already contains a different manifest")
        if self.manifest is None:
            self.manifest = manifest
            self._append({"kind": "manifest", "manifest": _manifest_payload(manifest)})
        return manifest.experiment_id

    def record_trial(self, trial_id: str) -> None:
        if self.manifest is None:
            raise ValueError("manifest is required")
        if not trial_id:
            raise ValueError("trial_id is required")
        if trial_id in self.trials:
            return
        if len(self.trials) >= self.manifest.max_trials:
            raise ValueError("manifest trial budget exceeded")
        self.trials.add(trial_id)
        self._append({"kind": "trial", "trial_id": trial_id})

    def freeze(self) -> None:
        if self.manifest is None:
            raise ValueError("manifest is required")
        if self.final_test_consumed:
            raise ValueError("final test has already been consumed")
        self._append({"kind": "freeze"})

    @property
    def frozen(self) -> bool:
        return any(self._events_kind("freeze"))

    def consume_final_test(self, report: Mapping[str, object]) -> str:
        if self.final_test_consumed:
            raise ValueError("final test has already been consumed")
        if self.manifest is None or not self.frozen:
            raise ValueError("final test requires a frozen manifest")
        if not report:
            raise ValueError("final test report is required")
        digest = canonical_hash(report)
        self.final_test_consumed = True
        self._append({"kind": "final_test", "report_sha256": digest})
        return digest

    def _events_kind(self, kind: str):
        if not self.path.exists():
            return ()
        with self.path.open(encoding="utf-8") as handle:
            return tuple(json.loads(line).get("kind") == kind for line in handle if line.strip())

    def _append(self, payload: Mapping[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"created_at": datetime.now(UTC).isoformat(), **payload}, sort_keys=True) + "\n")

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("kind") == "manifest":
                    self.manifest = LLMExperimentManifest.from_payload({"schema_version": 1, "artifact_type": "llm_experiment_manifest", **row["manifest"]})
                elif row.get("kind") == "trial":
                    self.trials.add(row["trial_id"])
                elif row.get("kind") == "final_test":
                    self.final_test_consumed = True


@dataclass(frozen=True)
class EvaluationPolicy:
    min_samples: int
    min_coverage: float
    max_abstention_rate: float
    max_drawdown: float
    max_turnover: float
    min_capacity_notional: float


@dataclass(frozen=True)
class ExperimentEvaluation:
    experiment_id: str
    manifest: dict[str, object]
    phase: str
    status: str
    primary: ComparisonReport
    secondary: ComparisonReport
    stress: tuple[ComparisonReport, ...]
    negative_controls: tuple[dict[str, object], ...]
    quality: dict[str, dict[str, object]]
    final_test_sha256: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 2,
            "artifact_type": "llm_experiment_evaluation",
            "experiment_id": self.experiment_id,
            "manifest": self.manifest,
            "phase": self.phase,
            "status": self.status,
            "primary": self.primary.to_dict(),
            "secondary": self.secondary.to_dict(),
            "stress": [item.to_dict() for item in self.stress],
            "negative_controls": list(self.negative_controls),
            "quality": self.quality,
            "final_test_sha256": self.final_test_sha256,
        }

    def to_markdown(self) -> str:
        return "\n".join(
            [
                f"# LLM experiment evaluation {self.experiment_id}",
                "",
                f"- Phase: `{self.phase}`",
                f"- Status: **{self.status}**",
                f"- Primary B3 − B2: `{self.primary.status}`; 95% [{self.primary.lower_95:.6f}, {self.primary.upper_95:.6f}]",
                f"- Secondary B3 − B1: `{self.secondary.status}`",
                f"- Stress scenarios passing: `{sum(item.status == 'PASS' for item in self.stress)}/{len(self.stress)}`",
                f"- Negative-control alerts: `{sum(item.get('status') == 'LEAKAGE_RISK' for item in self.negative_controls)}`",
            ]
        ) + "\n"


def evaluate_experiment(
    manifest: LLMExperimentManifest,
    series: Mapping[str, ExperimentSeries],
    *,
    phase: str = "development",
    ledger: ExperimentLedger | None = None,
) -> ExperimentEvaluation:
    if phase not in {"development", "final_test"}:
        raise ValueError("phase must be development or final_test")
    required = {"B0", "B1", "B2", "B3", "N1", "N2"}
    if set(series) != required:
        raise ValueError("B0, B1, B2, B3, N1 and N2 are required")
    policy = EvaluationPolicy(
        manifest.min_samples, manifest.min_coverage, manifest.max_abstention_rate,
        manifest.max_drawdown, manifest.max_turnover, manifest.min_capacity_notional,
    )
    quality: dict[str, dict[str, object]] = {}
    quality_ok = True
    for name in ("B0", "B1", "B2", "B3"):
        item = series[name]
        checks = {
            "coverage": item.coverage >= policy.min_coverage,
            "abstention_rate": item.abstention_rate <= policy.max_abstention_rate,
            "max_drawdown": item.max_drawdown <= policy.max_drawdown,
            "turnover": item.turnover <= policy.max_turnover,
            "capacity_notional": item.capacity_notional >= policy.min_capacity_notional,
        }
        quality[name] = {
            "passed": all(checks.values()),
            "checks": checks,
            "coverage": item.coverage,
            "abstention_rate": item.abstention_rate,
            "max_drawdown": item.max_drawdown,
            "turnover": item.turnover,
            "capacity_notional": item.capacity_notional,
        }
        quality_ok = quality_ok and bool(quality[name]["passed"])

    primary = compare_series(series["B2"], series["B3"], min_samples=policy.min_samples)
    secondary = compare_series(series["B1"], series["B3"], min_samples=policy.min_samples)
    stress = tuple(
        compare_series(
            _apply_cost_stress(series["B2"], bps),
            _apply_cost_stress(series["B3"], bps),
            min_samples=policy.min_samples,
        )
        for bps in manifest.cost_stress_bps
    )
    negative_controls = []
    for name in ("N1", "N2"):
        comparison = compare_series(series["B2"], series[name], min_samples=policy.min_samples)
        if comparison.sample_count < policy.min_samples:
            control_status = "INCONCLUSIVE"
        elif comparison.lower_95 > 0:
            control_status = "LEAKAGE_RISK"
        else:
            control_status = "PASS"
        negative_controls.append({**comparison.to_dict(), "status": control_status})
    status = "PASS" if (
        quality_ok
        and primary.status == "PASS"
        and secondary.status == "PASS"
        and all(item.status == "PASS" for item in stress)
        and not any(item["status"] == "LEAKAGE_RISK" for item in negative_controls)
    ) else "INCONCLUSIVE"
    evaluation = ExperimentEvaluation(
        manifest.experiment_id, _manifest_payload(manifest), phase, status,
        primary, secondary, stress, tuple(negative_controls), quality,
    )
    if phase == "final_test":
        if ledger is None:
            raise ValueError("final_test requires an experiment ledger")
        if ledger.manifest is None:
            ledger.register(manifest)
        if ledger.manifest.experiment_id != manifest.experiment_id:
            raise ValueError("ledger manifest does not match experiment")
        if not ledger.frozen:
            raise ValueError("final_test requires a frozen experiment ledger")
        digest = ledger.consume_final_test(evaluation.to_dict())
        evaluation = ExperimentEvaluation(**{**evaluation.__dict__, "final_test_sha256": digest})
    return evaluation


def _apply_cost_stress(series: ExperimentSeries, bps: float) -> ExperimentSeries:
    deduction = bps * series.turnover / 10_000
    return ExperimentSeries(
        series.name, tuple(value - deduction for value in series.net_returns),
        series.model_cost, series.coverage, series.abstention_rate,
        series.max_drawdown, series.turnover, series.capacity_notional,
    )


def _manifest_payload(manifest: LLMExperimentManifest) -> dict[str, object]:
    return {"schema_version": 1, "artifact_type": "llm_experiment_manifest", **manifest.__dict__}
