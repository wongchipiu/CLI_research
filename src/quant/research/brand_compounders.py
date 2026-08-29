"""Semi-quantitative scoring for emerging consumer brands."""

from __future__ import annotations

from typing import Any


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def component_scores(candidate: dict[str, Any]) -> dict[str, float]:
    return {
        "brand_evidence": clamp(float(candidate["brand_evidence"])),
        "revenue_growth": clamp(
            (float(candidate["revenue_growth_pct"]) + 10.0) / 40.0 * 100.0
        ),
        "demand_kpi": clamp(
            (float(candidate["demand_kpi_pct"]) + 5.0) / 20.0 * 100.0
        ),
        "runway_kpi": clamp(float(candidate["runway_kpi_pct"]) / 30.0 * 100.0),
        "economics_margin": clamp(
            (float(candidate["economics_margin_pct"]) + 5.0) / 30.0 * 100.0
        ),
        "valuation": clamp(
            (6.0 - float(candidate["sales_multiple"])) / 5.0 * 100.0
        ),
    }


def score_candidate(
    candidate: dict[str, Any], weights: dict[str, float]
) -> dict[str, Any]:
    components = component_scores(candidate)
    gross_score = sum(components[key] * float(weights[key]) for key in weights)
    score = clamp(gross_score - float(candidate.get("risk_penalty", 0.0)))
    return {
        "symbol": candidate["symbol"],
        "name": candidate["name"],
        "market_stage": candidate["market_stage"],
        "score": round(score, 1),
        "gross_score": round(gross_score, 1),
        "risk_penalty": candidate.get("risk_penalty", 0),
        "components": {key: round(value, 1) for key, value in components.items()},
        "snapshot": {
            "market_cap_usd_bn": candidate["market_cap_usd_bn"],
            "sales_multiple": candidate["sales_multiple"],
            "revenue_growth_pct": candidate["revenue_growth_pct"],
            "demand_kpi_pct": candidate["demand_kpi_pct"],
            "runway_kpi_pct": candidate["runway_kpi_pct"],
            "economics_margin_pct": candidate["economics_margin_pct"],
        },
        "evidence": candidate["evidence"],
    }


def rank(payload: dict[str, Any]) -> dict[str, Any]:
    weights = payload["method"]["weights"]
    if round(sum(float(value) for value in weights.values()), 10) != 1.0:
        raise ValueError("weights must sum to 1.0")
    records = [
        score_candidate(candidate, weights) for candidate in payload["candidates"]
    ]
    records.sort(key=lambda record: record["score"], reverse=True)
    for position, record in enumerate(records, start=1):
        record["rank"] = position
    return {
        "as_of": payload["as_of"],
        "model": "brand_compounder_screen_v1",
        "weights": weights,
        "caveat": (
            "Cross-sector semi-quantitative screen; market stage and brand "
            "evidence require human verification."
        ),
        "ranked": records,
    }

__all__ = ["clamp", "component_scores", "score_candidate", "rank"]
