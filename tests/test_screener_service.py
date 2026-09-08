"""
Unit & Integration Tests for the Quantamental Multistage Screener Service.
"""

import unittest
from src.screener.screener_models import ScreenerFilterRequest
from src.screener.screener_service import ScreenerService
from src.screener.live_query_adapter import LiveQueryAdapter
from src.screener.multi_horizon_feed_router import MultiHorizonFeedRouter


class TestScreenerService(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Skip LOCAL_DB tests when the database has no real market company data (e.g. after a DB wipe for LIVE_CLOUD testing)."""
        from src.db.base import SessionLocal
        from src.db.models import Company
        db = SessionLocal()
        try:
            # Exclude all known test fixture company_id prefixes
            real_companies = (
                db.query(Company)
                .filter(
                    Company.listing_status == "ACTIVE",
                    ~Company.company_id.startswith("comp_test"),
                    ~Company.company_id.startswith("comp_audit"),
                    ~Company.company_id.startswith("test_")
                )
                .limit(3)
                .all()
            )
            if not real_companies:
                raise unittest.SkipTest(
                    "LOCAL_DB screener tests skipped: database has no real market stock data. "
                    "Populate the DB via Trendlyne/Screener.in or use LIVE_CLOUD mode."
                )
        finally:
            db.close()

    def test_preset_screens_execution(self):
        """Verify all 4 institutional presets execute and return valid response models."""
        presets = [
            "MULTIBAGGER_INFLECTION_PRESET",
            "SWING_VCP_BREAKOUT_PRESET",
            "MICROCAP_COMPOUNDER_PRESET",
            "INTRADAY_MOMENTUM_SCALP_PRESET"
        ]

        for preset in presets:
            res = ScreenerService.run_preset_screen(preset, mode="LOCAL_DB")
            self.assertTrue(res.success, f"Preset {preset} failed: {res.error_message}")
            self.assertIsNotNone(res.funnel_stats)
            self.assertGreaterEqual(res.funnel_stats.total_universe_screened, 0)
            self.assertIsInstance(res.candidates, list)
            self.assertGreater(len(res.candidates), 0, f"Preset {preset} returned zero candidates")

    def test_custom_filter_screen(self):
        """Verify custom filter parameters execute and enforce bounds."""
        req = ScreenerFilterRequest(
            mode="LOCAL_DB",
            min_roce_pct=16.0,
            min_sales_growth_3y_pct=15.0,
            max_debt_to_equity=0.8,
            limit=10
        )
        res = ScreenerService.run_screen(req)
        self.assertTrue(res.success)
        self.assertLessEqual(len(res.candidates), 10)

        # Check candidate structure
        for cand in res.candidates:
            self.assertGreater(cand.cmp, 0.0)
            self.assertGreater(cand.multibagger_conviction_score, 0.0)
            self.assertGreater(cand.economic_inflection_p1, 0.0)
            self.assertGreater(cand.expectations_gap_p4, 0.0)
            self.assertIn(cand.failure_risk_rating, ["LOW", "MEDIUM", "HIGH"])
            self.assertEqual(len(cand.invalidation_triggers), 3)

    def test_decoupled_4_vectors_and_strategic_watchlist(self):
        """Verify the 4 orthogonal vectors and strategic watchlist feed are computed correctly."""
        res = ScreenerService.run_preset_screen("MULTIBAGGER_INFLECTION_PRESET", mode="LOCAL_DB")
        self.assertTrue(res.success)
        self.assertGreater(len(res.candidates), 0)

        for cand in res.candidates:
            # Check 4 decoupled orthogonal vectors
            self.assertGreaterEqual(cand.business_potential_score, 0.0)
            self.assertLessEqual(cand.business_potential_score, 100.0)
            self.assertIsInstance(cand.expectations_asymmetry_gap_pct, float)
            self.assertGreaterEqual(cand.tape_confirmation_score, 0.0)
            self.assertLessEqual(cand.tape_confirmation_score, 100.0)
            self.assertGreaterEqual(cand.entry_quality_score, 0.0)
            self.assertLessEqual(cand.entry_quality_score, 100.0)
            self.assertIn(cand.thesis_category, ["CONVICTION_BUY", "STRATEGIC_WATCHLIST", "SWING_SETUP", "INTRADAY_SCALP"])
            
            # Check honest likelihood metrics
            self.assertGreaterEqual(cand.m7_asymmetry_index, 0.0)
            self.assertIn(cand.multibagger_likelihood_rank, ["CONVICTION", "HIGH", "MEDIUM", "EMERGING"])

        # Check Funnel Attrition stats
        stats = res.funnel_stats
        self.assertGreaterEqual(stats.stage1_attrition_pct, 0.0)
        self.assertGreaterEqual(stats.stage2_attrition_pct, 0.0)
        self.assertGreaterEqual(stats.stage3_attrition_pct, 0.0)
        self.assertGreaterEqual(stats.stage4_attrition_pct, 0.0)

        # Check strategic watchlist feed
        self.assertIsInstance(res.strategic_watchlist_feed, list)

    def test_macro_regime_and_provenance_integration(self):
        """Verify macro regime summary, lifecycle stage, and data quality provenance are populated."""
        res = ScreenerService.run_preset_screen("MULTIBAGGER_INFLECTION_PRESET", mode="LOCAL_DB")
        self.assertTrue(res.success)
        self.assertIsNotNone(res.macro_regime_summary)
        self.assertIn("macro_regime", res.macro_regime_summary)
        self.assertIn("risk_stance", res.macro_regime_summary)

        for cand in res.candidates:
            self.assertIn(cand.setup_data_quality, [0.50, 0.75, 1.00])
            self.assertIn(cand.setup_quality_rating, ["AUDITED_PIT_DB", "CLOUD_PROXY", "FALLBACK_QUARANTINE"])
            self.assertIsNotNone(cand.lifecycle_stage)
            self.assertIsNotNone(cand.lifecycle_trigger)
            self.assertGreaterEqual(cand.swing_setup.atr_contraction_ratio, 0.0)

    def test_expectations_gap_uses_sustainable_growth(self):
        """
        Verify Expectations Gap is mathematically derived from Sustainable Compounding
        Capacity (ROIC * Reinvestment Rate), NEVER naive (ROCE - Implied Growth).
        """
        res = ScreenerService.run_preset_screen("MULTIBAGGER_INFLECTION_PRESET", mode="LOCAL_DB")
        self.assertTrue(res.success)
        for cand in res.candidates:
            if cand.market_implied_growth_pct is not None and cand.sustainable_compounding_ceiling_pct is not None:
                expected_gap = round(cand.sustainable_compounding_ceiling_pct - cand.market_implied_growth_pct, 1)
                self.assertAlmostEqual(
                    cand.expectations_asymmetry_gap_pct,
                    expected_gap,
                    delta=0.15,
                    msg=f"Expectations gap {cand.expectations_asymmetry_gap_pct} must equal Sustainable Compounding ({cand.sustainable_compounding_ceiling_pct}) - Implied Growth ({cand.market_implied_growth_pct})"
                )


if __name__ == "__main__":
    unittest.main()
