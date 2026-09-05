import json
import unittest
from pathlib import Path

from quant.research.brand_compounders import component_scores, rank, score_candidate


PROJECT_DIR = Path(__file__).resolve().parents[1]


class BrandCompounderTest(unittest.TestCase):
    def test_component_scores_are_bounded(self):
        scores = component_scores(
            {
                "brand_evidence": 120,
                "revenue_growth_pct": 100,
                "demand_kpi_pct": -100,
                "runway_kpi_pct": 100,
                "economics_margin_pct": -100,
                "sales_multiple": 20,
            }
        )
        self.assertTrue(all(0 <= value <= 100 for value in scores.values()))

    def test_penalty_reduces_score(self):
        candidate = {
            "symbol": "TEST",
            "name": "Test",
            "market_stage": "underfollowed",
            "market_cap_usd_bn": 1,
            "sales_multiple": 2,
            "revenue_growth_pct": 20,
            "demand_kpi_pct": 10,
            "runway_kpi_pct": 20,
            "economics_margin_pct": 15,
            "brand_evidence": 80,
            "risk_penalty": 10,
            "evidence": "test",
        }
        weights = {
            "brand_evidence": 0.30,
            "revenue_growth": 0.15,
            "demand_kpi": 0.15,
            "runway_kpi": 0.15,
            "economics_margin": 0.10,
            "valuation": 0.15,
        }
        result = score_candidate(candidate, weights)
        self.assertEqual(result["score"], round(result["gross_score"] - 10, 1))

    def test_snapshot_ranks_every_candidate(self):
        payload = json.loads(
            (PROJECT_DIR / "config" / "brand_compounders.json").read_text(encoding="utf-8")
        )
        result = rank(payload)
        self.assertEqual(len(result["ranked"]), len(payload["candidates"]))
        self.assertEqual(result["ranked"][0]["rank"], 1)


if __name__ == "__main__":
    unittest.main()
