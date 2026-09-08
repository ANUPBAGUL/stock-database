"""
Tests for 10/10 Institutional Upgrades:
1. StrategicWatchlistSentinel (Graduation evaluation & triggers)
2. 1-Click Zerodha/Upstox Broker Order Tickets
3. Intraday Gap Characterization (Gap-and-Go vs Exhaustion Gap) & Session Windows
"""

import unittest
from src.analytics.strategic_watchlist_sentinel import StrategicWatchlistSentinel
from src.screener.multi_horizon_feed_router import MultiHorizonFeedRouter
from src.screener.screener_models import ScreenerFilterRequest
from src.screener.screener_service import ScreenerService


class Test10OutOf10Upgrades(unittest.TestCase):

    def test_strategic_watchlist_sentinel_graduation(self):
        # Candidate near 50-EMA support with good potential
        cand = {
            "symbol": "SACHEEROME",
            "cmp": 485.0,
            "business_potential_score": 93.4,
            "expectations_asymmetry_gap_pct": 10.5,
            "tape_confirmation_score": 75.0,
            "entry_quality_score": 78.0,
            "ema50": 480.0,
            "high_1m": 505.0,
            "atr_live": 12.0
        }
        grad = StrategicWatchlistSentinel.evaluate_candidate_graduation(cand)
        self.assertIn("graduation_status", grad)
        self.assertIn("graduation_readiness_pct", grad)
        self.assertGreaterEqual(grad["graduation_readiness_pct"], 75.0)
        self.assertEqual(grad["graduation_status"], "GRADUATION_IMMIGRATION_READY")
        self.assertIn("graduation_trigger", grad)
        self.assertGreater(grad["target_pivot_price"], 485.0)

    def test_broker_order_ticket_generation(self):
        ticket = MultiHorizonFeedRouter._build_broker_order_ticket(
            symbol="DIXON",
            cmp=14240.0,
            entry_price=14500.0,
            stop_loss_price=13900.0, # risk = 600
            target_price_1=15700.0,
            target_price_2=16500.0,
            horizon="SWING_POSITIONAL",
            reference_capital=100000.0,
            risk_budget_pct=1.0 # max risk = 1,000 INR
        )
        self.assertEqual(ticket["broker_target"], "ZERODHA_UPSTOX_COMPLIANT")
        self.assertEqual(ticket["exchange"], "NSE")
        self.assertEqual(ticket["tradingsymbol"], "DIXON-EQ")
        self.assertEqual(ticket["transaction_type"], "BUY")
        self.assertEqual(ticket["order_type"], "LIMIT")
        self.assertEqual(ticket["product"], "CNC")
        self.assertEqual(ticket["quantity"], 1) # 1000 / 600 = 1 share
        self.assertEqual(ticket["entry_limit_price"], 14500.0)
        self.assertEqual(ticket["stop_loss_trigger"], 13900.0)
        self.assertIn("BUY 1 DIXON", ticket["order_summary"])

    def test_intraday_gap_character_and_session_window(self):
        eval_data = {
            "symbol": "CRISIL",
            "cmp": 4800.0,
            "rvol": 2.5,
            "range_expansion_pct": 25.0,
            "vwap_proximity_pct": 0.5,
            "turnover_10d_cr": 80.0,
            "gap_live": 5.2, # Exhaustion gap
            "market_cap_cr": 35000.0
        }
        card = MultiHorizonFeedRouter.route_candidate(eval_data)
        self.assertEqual(card.intraday_radar.gap_character, "EXHAUSTION_GAP_WARNING")
        self.assertEqual(card.intraday_radar.gap_pct, 5.2)
        self.assertIn(card.intraday_radar.session_phase, ["OPENING_RANGE_WINDOW", "MIDDAY_CHOP_ZONE", "AFTERNOON_TREND_RUN"])
        self.assertIsNotNone(card.intraday_radar.broker_order_ticket)
        self.assertEqual(card.intraday_radar.broker_order_ticket["product"], "MIS")

    def test_strategic_cohort_telemetry_enrichment(self):
        cohort = [
            {"symbol": "AAA", "cmp": 100.0, "business_potential_score": 85.0, "entry_quality_score": 60.0},
            {"symbol": "BBB", "cmp": 200.0, "business_potential_score": 90.0, "entry_quality_score": 78.0}
        ]
        enriched = StrategicWatchlistSentinel.evaluate_strategic_cohort(cohort)
        self.assertEqual(len(enriched), 2)
        self.assertIn("graduation_status", enriched[0])
        self.assertIn("graduation_readiness_pct", enriched[0])


if __name__ == "__main__":
    unittest.main()
