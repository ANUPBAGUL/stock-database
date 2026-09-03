"""
Unit & Integration Test Suite for the 200IQ Institutional Multibagger Discovery Architecture:
1. Competitive Position Engine (HHI, Pricing Power Resilience, Displacement Dynamics)
2. Raw Component Persistence across ROIIC, CapEx, TAM, and Acceleration
3. Point-in-Time ResearchFeatureSnapshot Database Persistence
4. Post-Experiment Model M7 Supervised Discovery Harness
"""
import unittest
from datetime import date, datetime
import uuid

from src.db.base import SessionLocal, Base, engine
from src.db.models.company import Company, Sector
from src.db.models.research_feature_snapshot import ResearchFeatureSnapshot
from src.analytics.competitive_engine import CompetitivePositionEngine
from src.analytics.roic_engine import EconomicROICEngine
from src.analytics.earnings_acceleration import EarningsAccelerationEngine
from src.analytics.tam_engine import ReverseTAMHurdleEngine
from scripts.train_m7_discovery_model import run_m7_discovery_harness

class Test200IQResearchPipeline(unittest.TestCase):

    def setUp(self):
        Base.metadata.create_all(engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    # ──────────────────────────────────────────────────────────────
    # 1. Competitive Position & Moat Engine Tests
    # ──────────────────────────────────────────────────────────────

    def test_competitive_engine_hhi_and_pricing_power(self):
        """Test HHI market concentration and gross margin volatility pricing power."""
        # Concentrated Oligopoly (e.g., Top 3 players hold 45%, 30%, 15%)
        shares = [45.0, 30.0, 15.0, 5.0, 5.0]
        hhi_res = CompetitivePositionEngine.calculate_hhi(shares)
        self.assertGreaterEqual(hhi_res["hhi_score"], 2500) # 2025 + 900 + 225 = 3150
        self.assertEqual(hhi_res["concentration_regime"], "CONCENTRATED_OLIGOPOLY")
        self.assertEqual(hhi_res["cr3_pct"], 90.0)

        # Pricing Power Test: Resilient Gross Margins across 5 years
        margins_stable = [42.5, 41.8, 43.1, 42.0, 42.9]
        pp_res = CompetitivePositionEngine.calculate_pricing_power_index(margins_stable)
        self.assertEqual(pp_res["pricing_power_rating"], "IRONCLAD_PRICING_POWER")
        self.assertGreaterEqual(pp_res["pricing_power_score"], 85.0)
        self.assertLessEqual(pp_res["gross_margin_std_dev"], 1.0)

    def test_competitive_engine_displacement_dynamics(self):
        """Test 'Who loses when this company wins?' classification."""
        disp = CompetitivePositionEngine.evaluate_displacement_dynamics(
            symbol="MANORAMA",
            sector="Specialty Chemicals",
            company_revenue_growth_yoy_pct=68.0,
            industry_growth_yoy_pct=14.0
        )
        self.assertEqual(disp["displacement_mode"], "SECULAR_IMPORT_SUBSTITUTION_AND_EXPORT")
        self.assertEqual(disp["economic_moat_rating"], "WIDE_MOAT_SCALE_AND_EFFICIENCY")

    # ──────────────────────────────────────────────────────────────
    # 2. Raw Component Persistence Tests
    # ──────────────────────────────────────────────────────────────

    def test_multi_horizon_roiic_component_persistence(self):
        """Test that ROIIC engine returns 1Y, 2Y, 3Y and preserves all raw delta components."""
        periods = [
            {"period_end_date": "2023-03-31", "nopat_cr": 100.0, "invested_capital_cr": 500.0, "revenue_cr": 800.0, "ebit_cr": 133.3},
            {"period_end_date": "2024-03-31", "nopat_cr": 140.0, "invested_capital_cr": 600.0, "revenue_cr": 1050.0, "ebit_cr": 186.7},
            {"period_end_date": "2025-03-31", "nopat_cr": 190.0, "invested_capital_cr": 720.0, "revenue_cr": 1400.0, "ebit_cr": 253.3},
            {"period_end_date": "2026-03-31", "nopat_cr": 260.0, "invested_capital_cr": 850.0, "revenue_cr": 1900.0, "ebit_cr": 346.7},
        ]
        roiic = EconomicROICEngine.calculate_rolling_incremental_roiic(periods, lookback_quarters=3)
        self.assertIsNotNone(roiic["rolling_roiic_pct"])
        self.assertEqual(roiic["delta_nopat_cr"], 160.0)
        self.assertEqual(roiic["delta_ic_cr"], 350.0)
        self.assertEqual(roiic["delta_revenue_cr"], 1100.0)
        self.assertEqual(roiic["roiic_validity_flag"], "VALID_CAPITAL_DEPLOYMENT")
        self.assertEqual(roiic["roiic_confidence"], "MEDIUM_LIMITED_HISTORY")

    def test_earnings_acceleration_persistence_tracking(self):
        """Test multi-quarter persistence tracking for earnings acceleration."""
        q_data = [
            {"period_end_date": "2024-12-31", "revenue_cr": 90.0, "ebit_cr": 12.0, "net_profit_cr": 8.0},
            {"period_end_date": "2025-03-31", "revenue_cr": 100.0, "ebit_cr": 15.0, "net_profit_cr": 10.0},
            {"period_end_date": "2025-06-30", "revenue_cr": 110.0, "ebit_cr": 17.0, "net_profit_cr": 11.0},
            {"period_end_date": "2025-09-30", "revenue_cr": 120.0, "ebit_cr": 19.0, "net_profit_cr": 13.0},
            {"period_end_date": "2025-12-31", "revenue_cr": 130.0, "ebit_cr": 21.0, "net_profit_cr": 15.0},
            {"period_end_date": "2026-03-31", "revenue_cr": 140.0, "ebit_cr": 24.0, "net_profit_cr": 18.0},
            {"period_end_date": "2026-06-30", "revenue_cr": 170.0, "ebit_cr": 35.0, "net_profit_cr": 27.0},
        ]
        accel = EarningsAccelerationEngine.calculate_acceleration_vector(q_data)
        self.assertTrue(accel["is_earnings_accelerating"])
        self.assertGreaterEqual(accel["acceleration_persistence_quarters"], 1)
        self.assertIn("pat_acceleration_1q_pct", accel)

    # ──────────────────────────────────────────────────────────────
    # 3. Dedicated Research Feature Snapshot DB Persistence Test
    # ──────────────────────────────────────────────────────────────

    def test_research_feature_snapshot_storage(self):
        """Test that ResearchFeatureSnapshot rows can be persisted and queried."""
        snap_id = f"test_snap_{uuid.uuid4().hex[:8]}"
        snap = ResearchFeatureSnapshot(
            snapshot_id=snap_id,
            company_id="comp_test_200iq",
            observation_date=date(2026, 9, 3),
            t0_timestamp=datetime.utcnow(),
            economic_roic_pct=28.5,
            roiic_3y_pct=42.0,
            delta_nopat_cr=120.0,
            delta_ic_cr=280.0,
            growth_reinvestment_rate_pct=65.0,
            niche_tam_cr=25000.0,
            macro_tam_cr=120000.0,
            required_10x_niche_share_pct=14.2,
            tam_feasibility="HIGH_FEASIBILITY_RUNWAY",
            is_10x_plausible=True,
            hhi_score=3200.0,
            pricing_power_score=88.0,
            moat_rating="WIDE_MOAT_SCALE_AND_EFFICIENCY",
            operational_leverage_multiplier=2.1,
            distance_to_excellence_score=45.0
        )
        self.db.add(snap)
        self.db.commit()

        # Query back
        retrieved = self.db.query(ResearchFeatureSnapshot).filter_by(snapshot_id=snap_id).first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.economic_roic_pct, 28.5)
        self.assertEqual(retrieved.roiic_3y_pct, 42.0)
        self.assertTrue(retrieved.is_10x_plausible)
        self.assertEqual(retrieved.moat_rating, "WIDE_MOAT_SCALE_AND_EFFICIENCY")

        # Cleanup
        self.db.delete(retrieved)
        self.db.commit()

    # ──────────────────────────────────────────────────────────────
    # 4. M7 Supervised Discovery Harness Test
    # ──────────────────────────────────────────────────────────────

    def test_m7_discovery_harness_execution(self):
        """Test the post-experiment M7 discovery harness execution."""
        report = run_m7_discovery_harness(min_samples=100)
        self.assertIsNotNone(report)
        self.assertIn("status", report)
        self.assertIn("generated_at", report)

if __name__ == "__main__":
    unittest.main()
