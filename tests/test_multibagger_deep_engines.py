"""
Unit and Integration Test Suite for the 7 Multibagger Analytical Upgrades:
1. Economic ROIC & 3-Year Rolling Incremental ROIIC (Mauboussin / Counterpoint Global)
2. Growth vs Maintenance CapEx & Growth Reinvestment (Bruce Greenwald Model)
3. Reverse-Engineered 10x TAM Mathematical Hurdle (Expectations Investing)
4. Seasonality-Immune Earnings Acceleration Vector (Second Derivative ΔGrowth)
5. Institutional Ownership Velocity & Dilution Registry
6. Continuous 6D Lifecycle Coordinates & State Transition Tracker
7. Latent Upside Map ("Distance to Excellence" Operational Leverage Model)
"""
import unittest
from datetime import date, datetime

from src.analytics.roic_engine import EconomicROICEngine
from src.analytics.reinvestment_calculator import ReinvestmentCalculator
from src.analytics.tam_engine import ReverseTAMHurdleEngine
from src.analytics.earnings_acceleration import EarningsAccelerationEngine
from src.analytics.ownership_velocity import OwnershipVelocityEngine
from src.analytics.lifecycle_classifier import LifecycleClassifier
from src.analytics.latent_upside_engine import LatentUpsideEngine

class TestMultibaggerDeepEngines(unittest.TestCase):

    # ──────────────────────────────────────────────────────────────
    # 1. Economic ROIC & Incremental ROIIC Tests
    # ──────────────────────────────────────────────────────────────

    def test_economic_roic_calculation(self):
        """Test Economic ROIC and NOPAT calculation."""
        res = EconomicROICEngine.calculate_economic_roic(
            ebit_cr=200.0,
            tax_rate_pct=25.0,
            net_worth_cr=600.0,
            borrowings_cr=300.0,
            cash_and_equivalents_cr=100.0
        )
        self.assertEqual(res["nopat_cr"], 150.0) # 200 * (1 - 0.25)
        self.assertEqual(res["invested_capital_cr"], 800.0) # (600 + 300) - 100
        self.assertEqual(res["economic_roic_pct"], 18.75) # (150 / 800) * 100

    def test_incremental_roiic_rolling_window_and_safeguards(self):
        """Test 3-Year rolling incremental ROIIC and small-denominator safeguard."""
        periods = [
            {"period_end_date": "2023-03-31", "nopat_cr": 100.0, "invested_capital_cr": 500.0, "economic_roic_pct": 20.0},
            {"period_end_date": "2024-03-31", "nopat_cr": 140.0, "invested_capital_cr": 600.0, "economic_roic_pct": 23.3},
            {"period_end_date": "2025-03-31", "nopat_cr": 190.0, "invested_capital_cr": 720.0, "economic_roic_pct": 26.4},
            {"period_end_date": "2026-03-31", "nopat_cr": 260.0, "invested_capital_cr": 850.0, "economic_roic_pct": 30.6},
        ]
        roiic = EconomicROICEngine.calculate_rolling_incremental_roiic(periods, lookback_quarters=3)
        self.assertEqual(roiic["delta_nopat_cr"], 160.0) # 260 - 100
        self.assertEqual(roiic["delta_ic_cr"], 350.0) # 850 - 500
        self.assertEqual(roiic["rolling_roiic_pct"], 45.71) # (160 / 350) * 100
        self.assertEqual(roiic["roiic_status"], "ACCELERATING_CAPITAL_EFFICIENCY")

        # Test small denominator safeguard (capital unchanged)
        flat_periods = [
            {"period_end_date": "2025-03-31", "nopat_cr": 100.0, "invested_capital_cr": 500.0},
            {"period_end_date": "2026-03-31", "nopat_cr": 110.0, "invested_capital_cr": 502.0},
        ]
        flat_res = EconomicROICEngine.calculate_rolling_incremental_roiic(flat_periods, lookback_quarters=1)
        self.assertEqual(flat_res["roiic_status"], "CAPITAL_UNCHANGED_ASSET_LIGHT")
        self.assertIsNone(flat_res["rolling_roiic_pct"])

    # ──────────────────────────────────────────────────────────────
    # 2. Growth vs Maintenance CapEx Tests (Greenwald Model)
    # ──────────────────────────────────────────────────────────────

    def test_growth_vs_maintenance_capex_clamping(self):
        """Test Greenwald CapEx breakdown with depreciation clamping."""
        res = ReinvestmentCalculator.calculate_growth_vs_maintenance_capex(
            total_capex_cr=120.0,
            depreciation_cr=40.0,
            sales_current_cr=800.0,
            sales_previous_cr=600.0,
            inflation_rate_pct=6.0
        )
        self.assertEqual(res["total_capex_cr"], 120.0)
        self.assertGreaterEqual(res["maintenance_capex_cr"], 28.0) # >= 0.70 * Depr
        self.assertLessEqual(res["maintenance_capex_cr"], 52.0) # <= 1.30 * Depr
        self.assertEqual(res["growth_capex_cr"], round(120.0 - res["maintenance_capex_cr"], 2))
        self.assertGreater(res["growth_capex_share_pct"], 50.0)

    def test_growth_reinvestment_rate_and_compounding_ceiling(self):
        """Test true growth reinvestment rate and compounding ceiling."""
        res = ReinvestmentCalculator.calculate_growth_reinvestment_rate(
            growth_capex_cr=75.0,
            delta_working_capital_cr=25.0,
            nopat_cr=150.0,
            incremental_roic_pct=30.0
        )
        self.assertEqual(res["growth_reinvestment_rate_pct"], 66.67) # (100 / 150) * 100
        self.assertEqual(res["organic_compounding_ceiling_pct"], 20.0) # 0.6667 * 30.0
        self.assertEqual(res["reinvestment_posture"], "BALANCED_COMPOUNDER")

    # ──────────────────────────────────────────────────────────────
    # 3. Reverse-Engineered 10x TAM Hurdle Tests
    # ──────────────────────────────────────────────────────────────

    def test_reverse_10x_tam_plausible_vs_absurd(self):
        """Test 10x TAM reverse engineering math and feasibility classification."""
        # Plausible smallcap with massive TAM (e.g. Manorama in CBE)
        tam = ReverseTAMHurdleEngine.resolve_industry_tam("MANORAMA")
        hurdle_plausible = ReverseTAMHurdleEngine.evaluate_10x_reverse_hurdle(
            current_market_cap_cr=2000.0,
            current_revenue_cr=400.0,
            current_pat_cr=60.0,
            industry_niche_tam_cr=tam["niche_tam_cr"],
            industry_macro_tam_cr=tam["macro_tam_cr"],
            terminal_pe_multiple=25.0,
            terminal_net_margin_pct=15.0
        )
        self.assertEqual(hurdle_plausible["target_10x_market_cap_cr"], 20000.0)
        self.assertEqual(hurdle_plausible["required_10x_pat_cr"], 800.0) # 20,000 / 25
        self.assertTrue(hurdle_plausible["is_10x_plausible"])

        # Absurd case: Mega-cap claiming 10x
        hurdle_absurd = ReverseTAMHurdleEngine.evaluate_10x_reverse_hurdle(
            current_market_cap_cr=100000.0,
            current_revenue_cr=30000.0,
            current_pat_cr=4000.0,
            industry_niche_tam_cr=50000.0,
            industry_macro_tam_cr=200000.0,
            terminal_pe_multiple=25.0,
            terminal_net_margin_pct=10.0
        )
        self.assertEqual(hurdle_absurd["feasibility"], "MATHEMATICALLY_ABSURD")
        self.assertFalse(hurdle_absurd["is_10x_plausible"])

    # ──────────────────────────────────────────────────────────────
    # 4. Earnings Acceleration Vector Tests
    # ──────────────────────────────────────────────────────────────

    def test_earnings_acceleration_second_derivative(self):
        """Test YoY earnings acceleration second-derivative engine."""
        quarterly_data = [
            {"period_end_date": "2025-03-31", "revenue_cr": 100.0, "ebit_cr": 15.0, "net_profit_cr": 10.0},
            {"period_end_date": "2025-06-30", "revenue_cr": 110.0, "ebit_cr": 17.0, "net_profit_cr": 11.0},
            {"period_end_date": "2025-09-30", "revenue_cr": 120.0, "ebit_cr": 19.0, "net_profit_cr": 13.0},
            {"period_end_date": "2025-12-31", "revenue_cr": 130.0, "ebit_cr": 21.0, "net_profit_cr": 15.0},
            {"period_end_date": "2026-03-31", "revenue_cr": 130.0, "ebit_cr": 23.0, "net_profit_cr": 17.0}, # Q-1 YoY Rev = 30%, PAT = 70%
            {"period_end_date": "2026-06-30", "revenue_cr": 165.0, "ebit_cr": 34.0, "net_profit_cr": 25.0}, # Q0 YoY Rev = 50%, PAT = 127%
        ]
        accel = EarningsAccelerationEngine.calculate_acceleration_vector(quarterly_data)
        self.assertTrue(accel["is_earnings_accelerating"])
        self.assertGreater(accel["revenue_acceleration_pct_points"], 0.0)
        self.assertGreater(accel["pat_acceleration_pct_points"], 0.0)
        self.assertEqual(accel["acceleration_status"], "ACCELERATING_EARNINGS_EXPLOSION")

    # ──────────────────────────────────────────────────────────────
    # 5. Institutional Ownership Velocity Tests
    # ──────────────────────────────────────────────────────────────

    def test_ownership_velocity_and_dilution_registry(self):
        """Test institutional accumulation velocity and dilution detection."""
        sh_hist = [
            {"period_end_date": "2025-06-30", "promoter_holding_pct": 54.0, "fii_holding_pct": 2.0, "dii_holding_pct": 2.0},
            {"period_end_date": "2025-09-30", "promoter_holding_pct": 54.0, "fii_holding_pct": 2.5, "dii_holding_pct": 2.5},
            {"period_end_date": "2025-12-31", "promoter_holding_pct": 54.0, "fii_holding_pct": 3.0, "dii_holding_pct": 3.0},
            {"period_end_date": "2026-03-31", "promoter_holding_pct": 54.0, "fii_holding_pct": 3.8, "dii_holding_pct": 3.2},
            {"period_end_date": "2026-06-30", "promoter_holding_pct": 54.0, "fii_holding_pct": 5.0, "dii_holding_pct": 4.0},
        ]
        vel = OwnershipVelocityEngine.calculate_ownership_velocity(sh_hist)
        self.assertEqual(vel["current_institutional_pct"], 9.0) # 5.0 + 4.0
        self.assertEqual(vel["inst_1y_delta_pct"], 5.0) # 9.0 - 4.0
        self.assertTrue(vel["is_institutional_accumulating"])
        self.assertEqual(vel["institutional_velocity_trend"], "AGGRESSIVE_INSTITUTIONAL_ACCUMULATION")

        # Test Dilution Audit
        dil = OwnershipVelocityEngine.audit_dilution_mechanisms(
            current_share_count=10500000,
            previous_year_share_count=10000000,
            disclosures_list=[{"headline": "Allotment of equity shares pursuant to QIP"}]
        )
        self.assertTrue(dil["is_dilution_detected"])
        self.assertEqual(dil["primary_dilution_event"], "QIP_PLACEMENT")

    # ──────────────────────────────────────────────────────────────
    # 6. Continuous 6D Lifecycle Coordinates Tests
    # ──────────────────────────────────────────────────────────────

    def test_continuous_lifecycle_coordinates(self):
        """Test continuous 6D lifecycle coordinates space."""
        coords = LifecycleClassifier.calculate_continuous_lifecycle_coordinates(
            market_cap_cr=12000.0,
            revenue_growth_yoy_pct=45.0,
            pat_growth_yoy_pct=85.0,
            roce_pct=35.0,
            institutional_stake_pct=15.0,
            pe_ratio=45.0
        )
        vec = coords["coordinate_vector"]
        self.assertEqual(len(vec), 6)
        for val in vec:
            self.assertGreaterEqual(val, 0.0)
            self.assertLessEqual(val, 1.0)
        self.assertEqual(coords["transition_signature"], "EARLY_TO_OPERATING_LEVERAGE_INFLECTION")

    # ──────────────────────────────────────────────────────────────
    # 7. Latent Upside Map ("Distance to Excellence") Tests
    # ──────────────────────────────────────────────────────────────

    def test_latent_upside_map_operational_leverage(self):
        """Test Latent Upside Map and operational leverage multiplier."""
        map_res = LatentUpsideEngine.calculate_latent_upside_map(
            current_revenue_cr=1000.0,
            current_ebit_cr=100.0,
            current_pat_cr=75.0,
            current_market_cap_cr=2500.0,
            current_roce_pct=16.0,
            current_capacity_utilization_pct=60.0,
            sector_top_quartile_opm_pct=16.0,
            sector_top_quartile_roce_pct=28.0,
            benchmark_target_utilization_pct=85.0
        )
        self.assertGreaterEqual(map_res["operational_leverage_multiplier"], 2.0)
        self.assertGreaterEqual(map_res["potential_pat_at_excellence_cr"], 150.0)
        self.assertEqual(map_res["latent_profile"], "EXPLOSIVE_LATENT_OPERATIONAL_LEVERAGE")

if __name__ == "__main__":
    unittest.main()
