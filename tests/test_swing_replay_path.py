"""
Unit tests for Conditional Path Distributions, Pre-Stop Realizations, and Confidence Decomposition.
Validates zero look-ahead bias and mathematical invariance.
"""

import unittest
from typing import Dict, Any, List

from src.analytics.historical_swing_replay_engine import (
    HistoricalSwingReplayEngine, SwingTradeRealization,
    compute_wilson_confidence_interval, evaluate_sample_evidence_tier
)
from src.screener.multi_horizon_feed_router import MultiHorizonFeedRouter
from src.screener.screener_models import ScreenerCandidateResult


class TestSwingReplayPath(unittest.TestCase):

    def test_path_dependent_stopping_prevents_lookahead(self):
        """
        Critical Anti-Leakage Invariant:
        If a trade touches stop loss on Day 2, and subsequently explodes by +50% on Day 15,
        hit_1r_before_stop must be strictly False, and mfe_pre_stop must reflect only pre-stop excursions.
        """
        entry_price = 100.0
        stop_loss = 95.0
        target_t1 = 110.0
        target_t2 = 120.0

        # Construct candle series:
        # Day 0: Entry session
        # Day 1: Moderate adverse excursion (Low: 96.0)
        # Day 2: Stop loss breached (Low: 94.0, High: 97.0, Close: 94.5)
        # Day 3-15: Massive rally to 160.0 (+60%)
        candles = [
            {"date": "2026-01-01", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000},
            {"date": "2026-01-02", "open": 100.0, "high": 100.5, "low": 96.0, "close": 96.5, "volume": 1000},
            {"date": "2026-01-05", "open": 96.0, "high": 97.0, "low": 94.0, "close": 94.5, "volume": 1200},  # STOP HIT
            {"date": "2026-01-06", "open": 95.0, "high": 115.0, "low": 95.0, "close": 114.0, "volume": 2000},
            {"date": "2026-01-07", "open": 115.0, "high": 130.0, "low": 114.0, "close": 128.0, "volume": 2500},
            {"date": "2026-01-08", "open": 128.0, "high": 160.0, "low": 127.0, "close": 158.0, "volume": 3000},
        ]

        sim = HistoricalSwingReplayEngine._simulate_forward_trade(
            candles=candles,
            entry_idx=0,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_t1=target_t1,
            target_t2=target_t2,
            forward_horizon=10,
            execution_mode="CONSERVATIVE"
        )

        # Invariants
        self.assertEqual(sim["outcome"], "STOPPED_OUT")
        self.assertFalse(sim["hit_t1"])
        self.assertFalse(sim["hit_1r"])
        self.assertFalse(sim["hit_2r"])
        self.assertFalse(sim["hit_3r"])
        self.assertEqual(sim["days_to_stop"], 2)
        self.assertIsNone(sim["days_to_1r"])

        # Pre-stop MFE should be at most Day 1-2 high (100.5 -> +0.5%), NOT Day 8 high (160 -> +60%)
        self.assertLessEqual(sim["mfe_pre_stop"], 1.0)
        # Full horizon MFE should record the full post-exit move
        self.assertGreaterEqual(sim["mfe_45d_full"], 50.0)

    def test_path_dependent_milestones_reached_in_sequence(self):
        """
        Validates that a winning trade progressively registers +1R and +2R before eventual trailing exit.
        """
        entry_price = 100.0
        stop_loss = 95.0  # R-unit = 5.0 -> 1R = 105.0, 2R = 110.0, 3R = 115.0
        target_t1 = 110.0
        target_t2 = 125.0

        candles = [
            {"date": "2026-02-01", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000},
            {"date": "2026-02-02", "open": 100.0, "high": 103.0, "low": 99.0, "close": 102.0, "volume": 1000},
            {"date": "2026-02-03", "open": 102.0, "high": 106.0, "low": 101.0, "close": 105.5, "volume": 1500}, # Reaches 1R (105.0)
            {"date": "2026-02-04", "open": 105.5, "high": 111.0, "low": 104.0, "close": 110.5, "volume": 2000}, # Reaches 2R & T1 (110.0)
            {"date": "2026-02-05", "open": 110.0, "high": 112.0, "low": 107.0, "close": 108.0, "volume": 1200},
        ]

        sim = HistoricalSwingReplayEngine._simulate_forward_trade(
            candles=candles,
            entry_idx=0,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_t1=target_t1,
            target_t2=target_t2,
            forward_horizon=10,
            execution_mode="CONSERVATIVE"
        )

        self.assertTrue(sim["hit_1r"])
        self.assertTrue(sim["hit_2r"])
        self.assertFalse(sim["hit_3r"])
        self.assertEqual(sim["days_to_1r"], 2)
        self.assertEqual(sim["days_to_2r"], 3)
        self.assertTrue(sim["hit_t1"])

    def test_wilson_confidence_interval_bounds(self):
        """
        Validates Wilson Score 95% Confidence Interval behavior.
        """
        # Zero trials
        low, high = compute_wilson_confidence_interval(0, 0)
        self.assertEqual(low, 0.0)
        self.assertEqual(high, 100.0)

        # Small sample with 3 of 7 wins (VCP sample size)
        low, high = compute_wilson_confidence_interval(3, 7)
        self.assertGreater(low, 10.0)
        self.assertLess(high, 80.0)
        self.assertTrue(low < 42.9 < high)

        # 100% win rate on 5 of 5
        low_5, high_5 = compute_wilson_confidence_interval(5, 5)
        self.assertEqual(high_5, 100.0)
        self.assertGreaterEqual(low_5, 50.0)
        self.assertLess(low_5, 100.0)

    def test_candidate_confidence_decomposition(self):
        """
        Validates candidate routing confidence decomposition:
        - Pure signal_score (0-100)
        - historical_evidence_tier (LIMITED / PRELIMINARY / MODERATE / ADEQUATE)
        - setup_grade (A_PRIME / B_SELECTIVE / C_DEVELOPING / DISQUALIFIED)
        - conditional_p_1r_pct
        """
        candidate_data = {
            "symbol": "TRENT",
            "company_name": "Trent Ltd",
            "cmp": 7250.0,
            "market_cap_cr": 250000.0,
            "pe_ratio": 95.0,
            "roce_pct": 28.5,
            "business_potential_score": 90.0,
            "expectations_asymmetry_gap_pct": 12.0,
            "tape_confirmation_score": 85.0,
            "entry_quality_score": 82.0,
            "multibagger_conviction_score": 88.0,
            "economic_inflection_p1": 90.0,
            "reinvestment_runway_p2": 92.0,
            "working_capital_p3": 85.0,
            "expectations_gap_p4": 82.0,
            "price_structure_p5": 88.0,
            "market_implied_growth_pct": 18.0,
            "sustainable_compounding_ceiling_pct": 30.0,
            "expectations_asymmetry_pct": 12.0,
            "atr_20d": 120.0,
            "atr_weekly": 160.0,  # ATR contraction ratio: 120/160 = 0.75 (TIGHT)
            "support_price_50d": 6900.0,
            "high_1m": 7300.0,
            "high_52w": 7500.0,
            "turnover_10d_cr": 250.0,
            "rvol": 1.5,
            "range_expansion_pct": 10.0,
            "vwap_proximity_pct": 0.5,
            "macro_regime": "BULL_MOMENTUM"
        }

        result: ScreenerCandidateResult = MultiHorizonFeedRouter.route_candidate(candidate_data)

        # Check decomposed fields
        self.assertIsInstance(result.signal_score, float)
        self.assertGreater(result.signal_score, 70.0)
        self.assertIn(result.historical_evidence_tier, ["LIMITED", "PRELIMINARY", "MODERATE", "ADEQUATE"])
        self.assertIn(result.setup_grade, ["A_PRIME", "B_SELECTIVE", "C_DEVELOPING", "DISQUALIFIED"])
        self.assertIsInstance(result.conditional_p_1r_pct, float)
        self.assertGreater(result.conditional_p_1r_pct, 0.0)

        # Swing card must mirror the grade and path metrics
        self.assertEqual(result.swing_setup.setup_grade, result.setup_grade)
        self.assertEqual(result.swing_setup.conditional_p_1r_pct, result.conditional_p_1r_pct)
        self.assertGreater(result.swing_setup.conditional_p_2r_pct, 0.0)

    def test_excessive_risk_disqualification(self):
        """
        Validates that a setup with structural risk > 8.5% is DISQUALIFIED.
        """
        candidate_data = {
            "symbol": "RISKY",
            "cmp": 100.0,
            "atr_20d": 10.0,
            "support_price_50d": 80.0,  # Risk > 10%
            "high_1m": 105.0,
            "turnover_10d_cr": 50.0,
            "business_potential_score": 60.0,
            "tape_confirmation_score": 50.0,
            "entry_quality_score": 40.0
        }

        result = MultiHorizonFeedRouter.route_candidate(candidate_data)
        self.assertEqual(result.setup_grade, "DISQUALIFIED")
        self.assertEqual(result.swing_setup.suggested_position_size_pct, 0.0)


if __name__ == "__main__":
    unittest.main()
