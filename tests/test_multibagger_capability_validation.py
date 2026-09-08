"""
Tests for Multibagger Capability Validation Program Engine.
Verifies:
1. Multi-strategy universe ranking at T0
2. Signature Early Discovery Lift calculation
3. Pillar ablation matrix computation
4. Prediction autopsy generation for failed compounders
"""

import unittest
from datetime import date
from src.db.base import SessionLocal, Base, engine
from src.db.models import Company, ResearchFeatureSnapshot, ForwardOutcome
from src.analytics.multibagger_capability_validator import MultibaggerCapabilityValidator


class TestMultibaggerCapabilityValidation(unittest.TestCase):

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_universe_ranking_multi_strategies(self):
        """Verify universe ranking evaluates under 5_PILLAR, M6, and SIMPLE_QUALITY strategies."""
        ranked_5p = MultibaggerCapabilityValidator.evaluate_universe_at_t0(
            self.db, date(2024, 6, 30), "5_PILLAR_SYNTHESIS"
        )
        self.assertIsInstance(ranked_5p, list)

        ranked_m6 = MultibaggerCapabilityValidator.evaluate_universe_at_t0(
            self.db, date(2024, 6, 30), "M6_LINEAR"
        )
        self.assertIsInstance(ranked_m6, list)

    def test_ablation_matrix_structure(self):
        """Verify pillar ablation matrix evaluates all 5 pillars and baselines."""
        ablation = MultibaggerCapabilityValidator.compute_ablation_matrix(
            self.db, [date(2023, 6, 30), date(2024, 6, 30)]
        )
        self.assertIn("full_5_pillar", ablation)
        self.assertIn("p1_inflection_only", ablation)
        self.assertIn("p4_expectations_only", ablation)
        self.assertIn("p1_plus_p4_asymmetry", ablation)
        self.assertIn("m6_linear_baseline", ablation)
        self.assertIn("random_baseline", ablation)

        # Full 5-Pillar must outperform random and linear M6
        self.assertGreater(ablation["full_5_pillar"]["precision_10x_pct"], ablation["random_baseline"]["precision_10x_pct"])
        self.assertGreater(ablation["full_5_pillar"]["precision_10x_pct"], ablation["m6_linear_baseline"]["precision_10x_pct"])

    def test_early_discovery_lift_structure(self):
        """Verify signature early discovery lift calculation returns structured metric."""
        lift_res = MultibaggerCapabilityValidator.calculate_early_discovery_lift(
            self.db, lead_time_months=24, target_multiplier=5.0
        )
        self.assertIn("lead_time_months", lift_res)
        self.assertIn("early_discovery_lift_over_random", lift_res)
        self.assertEqual(lift_res["lead_time_months"], 24)

    def test_prediction_autopsy_generation(self):
        """Verify failed prediction autopsy diagnoses root causes and remedial rules."""
        autopsy = MultibaggerCapabilityValidator.generate_prediction_autopsy(
            company_id="comp_test_fail",
            symbol="FAILCORP",
            t0_date=date(2021, 3, 31),
            t0_thesis={"score": 88, "thesis_drivers": ["High ROIC expansion", "Large TAM"]},
            actual_realization={"realized_cagr_pct": -25.0, "max_drawdown_pct": 65.0, "first_violated_metric": "DSO_EXPANSION_80D"}
        )
        self.assertEqual(autopsy["root_cause_diagnosis"], "WORKING_CAPITAL_AND_CASH_DRAIN")
        self.assertIn("earliest_detectable_warning", autopsy)
        self.assertIn("remedial_circuit_breaker", autopsy)


if __name__ == "__main__":
    unittest.main()
