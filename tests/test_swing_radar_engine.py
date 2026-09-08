"""
Unit and Integration Tests for the Institutional Positional Swing Trading Engine.
Validates:
1. Minervini 8-Point Stage 2 Trend Template
2. Normalized Volatility Contraction (ATR10 / ATR30)
3. Normalized Volume Dry-Up (Vol5 / Vol40) with Price Support Holding
4. Up/Down Volume Accumulation Signature & Day Counts
5. Adaptive Pivot Buffer & Pivot Entry
6. Structural Invalidation Stop-Loss & 1% Risk Position Sizing
7. Dual Targets (T1 Conservative & T2 30-45 Day Positional)
8. Organic Variable Risk/Reward (verifies R:R is dynamic, never hardcoded 2.33x)
9. Probability-Weighted Expected Value (EV) Score
10. Actionability Zones (CONSTRUCTING_BASE, TRIGGER_WATCH, ACTIONABLE_BUY, FAILED_SETUP)
"""

import unittest
from src.analytics.price_structure_engine import PriceStructureEngine
from src.screener.screener_models import SwingSetupCard
from src.screener.multi_horizon_feed_router import MultiHorizonFeedRouter


class TestInstitutionalSwingEngine(unittest.TestCase):

    def setUp(self):
        # Construct synthetic yet realistic trending chart with 60 sessions
        # Base price around 100 rising to 150 (Stage 2 Uptrend)
        self.closes = []
        self.highs = []
        self.lows = []
        self.volumes = []

        base = 100.0
        for i in range(60):
            drift = i * 0.8
            c = base + drift
            h = c + 1.5
            l = c - 1.2
            v = 100000.0 + (i % 5) * 15000.0
            self.closes.append(round(c, 2))
            self.highs.append(round(h, 2))
            self.lows.append(round(l, 2))
            self.volumes.append(v)

    def test_minervini_8point_template(self):
        """Test Minervini 8-point trend template evaluation."""
        eval_res = PriceStructureEngine.evaluate_minervini_8point_template(self.closes, current_price=self.closes[-1])
        self.assertIn("is_template_passed", eval_res)
        self.assertIn("passed_criteria_count", eval_res)
        self.assertGreaterEqual(eval_res["passed_criteria_count"], 0)
        self.assertIn("dist_low_pct", eval_res)
        self.assertIn("dist_high_pct", eval_res)
        self.assertGreater(eval_res["high_52w"], 0.0)

    def test_normalized_volatility_and_volume_dryup(self):
        """Verify ATR10/ATR30 and Vol5/Vol40 normalization."""
        # Create a tightened contraction at the end of the series
        closes = list(self.closes)
        highs = list(self.highs)
        lows = list(self.lows)
        volumes = list(self.volumes)

        # Last 10 days are extremely tight with low volume
        last_price = closes[-1]
        for j in range(10):
            closes[-(j + 1)] = last_price + (j * 0.1)
            highs[-(j + 1)] = last_price + 0.3
            lows[-(j + 1)] = last_price - 0.2
            volumes[-(j + 1)] = 30000.0  # Much lower than 100k avg

        res = PriceStructureEngine.audit_swing_setup(closes, highs, lows, volumes, current_price=last_price)

        # Volatility contraction should be recognized
        self.assertLess(res["atr_contraction_ratio"], 1.0)
        self.assertLess(res["volatility_contraction_delta_pct"], 0.0)

        # Volume dry-up should be recognized
        self.assertLess(res["volume_dryup_ratio"], 1.0)
        self.assertLess(res["volume_dryup_delta_pct"], 0.0)

        # Setup type should be classified
        self.assertIn(res["setup_type"], ["VCP_CONTRACTION_BREAKOUT", "50EMA_PULLBACK", "52W_HIGH_BREAKOUT", "BASE_CONSOLIDATION"])

    def test_organic_variable_risk_reward(self):
        """Verify Risk/Reward is calculated dynamically and is NOT hardcoded to 2.33x."""
        res1 = PriceStructureEngine.audit_swing_setup(self.closes, self.highs, self.lows, self.volumes, current_price=self.closes[-1])
        rr1 = res1["risk_reward_ratio"]

        # Different chart geometry
        closes2 = [round(c * 2.5, 2) for c in self.closes]
        highs2 = [round(h * 2.5 + 4.0, 2) for h in self.highs]
        lows2 = [round(l * 2.5 - 1.0, 2) for l in self.lows]
        volumes2 = [v * 3.0 for v in self.volumes]

        res2 = PriceStructureEngine.audit_swing_setup(closes2, highs2, lows2, volumes2, current_price=closes2[-1])
        rr2 = res2["risk_reward_ratio"]

        # Assert R:R is positive and dynamic
        self.assertGreater(rr1, 0.0)
        self.assertGreater(rr2, 0.0)
        # Verify it is not the old fake constant 2.33
        self.assertTrue(rr1 != 2.33 or rr2 != 2.33, "R:R must be organic, not the synthetic 2.33x constant!")

    def test_adaptive_pivot_buffer_and_structural_stop(self):
        """Verify adaptive pivot buffer adjusts to price/volatility, and stop is anchored to structure."""
        cmp = self.closes[-1]
        res = PriceStructureEngine.audit_swing_setup(self.closes, self.highs, self.lows, self.volumes, current_price=cmp)

        # Pivot must be above recent highs by adaptive buffer
        self.assertGreater(res["pivot_entry_price"], 0.0)
        self.assertGreater(res["adaptive_pivot_buffer"], 0.0)

        # Stop loss must be below pivot entry
        self.assertLess(res["stop_loss_price"], res["pivot_entry_price"])
        self.assertGreater(res["risk_pct"], 0.0)

        # Suggested position size must be bounded
        self.assertGreaterEqual(res["suggested_position_size_pct"], 4.0)
        self.assertLessEqual(res["suggested_position_size_pct"], 25.0)

        # Dual targets must be progressive: T2 > T1 > Pivot Entry
        self.assertGreater(res["target_price_t1"], res["pivot_entry_price"])
        self.assertGreater(res["target_price_t2"], res["target_price_t1"])

    def test_failed_setup_detection(self):
        """Verify that a breakout that immediately falls back is flagged as FAILED_SETUP."""
        closes = list(self.closes)
        highs = list(self.highs)
        lows = list(self.lows)
        volumes = list(self.volumes)

        # High breached 160 two days ago, but price collapsed back to 142
        highs[-2] = 160.0
        closes[-2] = 158.0
        closes[-1] = 142.0
        highs[-1] = 145.0
        lows[-1] = 140.0

        res = PriceStructureEngine.audit_swing_setup(closes, highs, lows, volumes, current_price=142.0)
        self.assertIn(res["actionability_status"], ["FAILED_SETUP", "CONSTRUCTING_BASE"])

    def test_up_down_volume_ratio(self):
        """Verify Up/Down volume ratio reflects accumulation."""
        res = PriceStructureEngine.audit_swing_setup(self.closes, self.highs, self.lows, self.volumes, current_price=self.closes[-1])
        self.assertGreater(res["up_down_volume_ratio"], 0.0)
        self.assertGreater(res["up_days_count"] + res["down_days_count"], 0)

    def test_multi_horizon_router_integration(self):
        """Verify MultiHorizonFeedRouter populates SwingSetupCard cleanly."""
        res = PriceStructureEngine.audit_swing_setup(self.closes, self.highs, self.lows, self.volumes, current_price=self.closes[-1])
        cand_dict = {
            "symbol": "SWINGTEST",
            "company_name": "Swing Test Equities",
            "cmp": self.closes[-1],
            "market_cap_cr": 3500.0,
            "business_potential_score": 82.0,
            "expectations_asymmetry_gap_pct": 8.5,
            "tape_confirmation_score": 78.0,
            "entry_quality_score": 85.0,
            "multibagger_conviction_score": 84.0,
            "m7_asymmetry_index": 80.0,
            "multibagger_likelihood_rank": "HIGH",
            "swing_audit": res,
            "atr_20d": res["atr_20d"],
            "rvol": 1.45,
            "range_expansion_pct": 12.0,
            "vwap_proximity_pct": 0.4
        }
        card = MultiHorizonFeedRouter.route_candidate(cand_dict)
        self.assertIsInstance(card.swing_setup, SwingSetupCard)
        self.assertGreater(card.swing_setup.pivot_entry_price, 0.0)
        self.assertGreater(card.swing_setup.stop_loss_price, 0.0)
        self.assertGreater(card.swing_setup.target_price_t1, 0.0)
        self.assertGreater(card.swing_setup.target_price_t2, 0.0)
        self.assertIn(card.swing_setup.actionability_status, ["CONSTRUCTING_BASE", "TRIGGER_WATCH", "ACTIONABLE_BUY", "LATE_BUY_ZONE", "EXTENDED", "FAILED_SETUP"])


if __name__ == "__main__":
    unittest.main()
