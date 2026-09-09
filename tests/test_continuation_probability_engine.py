"""
Unit Tests for Continuation Probability Engine.
Validates mathematical calculations (CLV, Upper Wick, FSAR, IER),
logistic probability calibration, institutional invariant clamping,
9:15 AM ORB-15 Playbook generation, and Devil's Advocate safeguards.
"""

import pytest
from src.analytics.continuation_probability_engine import ContinuationProbabilityEngine
from src.analytics.dvm_scorer import DVMScorer


class TestContinuationProbabilityEngine:
    """Test suite for ContinuationProbabilityEngine."""

    def test_clv_calculation(self):
        """Tests Close Location Value boundary conditions."""
        # Closed at exact high -> CLV = 1.0
        assert ContinuationProbabilityEngine.calculate_clv(high=100.0, low=90.0, close_px=100.0) == 1.0
        # Closed at exact low -> CLV = 0.0
        assert ContinuationProbabilityEngine.calculate_clv(high=100.0, low=90.0, close_px=90.0) == 0.0
        # Closed at midpoint -> CLV = 0.5
        assert ContinuationProbabilityEngine.calculate_clv(high=100.0, low=90.0, close_px=95.0) == 0.5
        # High equals Low (zero spread) -> Graceful 0.5
        assert ContinuationProbabilityEngine.calculate_clv(high=100.0, low=100.0, close_px=100.0) == 0.5

    def test_upper_wick_calculation(self):
        """Tests overhead supply rejection ratio."""
        # Candle with big upper shadow: Open=100, Close=102, High=110, Low=99
        # Body top = 102. Wick = 110 - 102 = 8. Spread = 11. Ratio = 8 / 11 = 0.7273
        ratio = ContinuationProbabilityEngine.calculate_upper_wick_ratio(
            open_px=100.0, high=110.0, low=99.0, close_px=102.0
        )
        assert round(ratio, 2) == 0.73

        # Marubozu candle (no upper wick): Open=100, Close=110, High=110, Low=100
        assert ContinuationProbabilityEngine.calculate_upper_wick_ratio(
            open_px=100.0, high=110.0, low=100.0, close_px=110.0
        ) == 0.0

    def test_fsar_float_absorption(self):
        """Tests Floating Supply Absorption Ratio."""
        # 1,000,000 shares delivered out of 50,000,000 float -> 2.0%
        fsar = ContinuationProbabilityEngine.calculate_fsar(
            delivery_qty=1000000, float_shares=50000000.0
        )
        assert fsar == 2.0

        # Missing float -> None
        assert ContinuationProbabilityEngine.calculate_fsar(delivery_qty=1000000, float_shares=None) is None

    def test_institutional_breakout_gap_and_go(self):
        """Tests high-delivery, high-CLV institutional setup achieving GAP_AND_GO."""
        stock = {
            "symbol": "LEADER",
            "close": 1000.0,
            "open": 920.0,
            "high": 1005.0,
            "low": 915.0,
            "change": 8.5,
            "relative_volume_10d_calc": 3.2,
            "RSI": 68.0,
            "VWAP": 975.0,
            "ATR": 25.0,
            "price_52_week_high": 1010.0,
            "float_shares_outstanding": 40000000.0,
            "market_cap_basic": 100000000000,
            "debt_to_equity_fq": 0.2
        }
        deliv = {
            "has_data": True,
            "latest_delivery_pct": 56.0,
            "latest_delivery_qty": 800000,
            "delivery_velocity": 10.0,
            "trajectory_label": "STAIRCASE_ACCUMULATION"
        }
        dvm = DVMScorer.calculate_scores(stock)
        res = ContinuationProbabilityEngine.evaluate_candidate(stock, deliv, dvm, horizon="TODAY")

        assert res["continuation_probability_pct"] >= 75.0
        assert res["verdict"] == "GAP_AND_GO_CANDIDATE"
        assert res["clv"] >= 0.90
        assert res["delivery_pct"] == 56.0
        assert "gap_up_rule" in res["orb15_playbook"]
        assert res["trade_brackets"]["recommended_entry"] >= 1000.0
        assert res["trade_brackets"]["stop_loss"] < 1000.0
        assert res["trade_brackets"]["target_1_2r"] > res["trade_brackets"]["recommended_entry"]

    def test_retail_churn_trap_firewall(self):
        """Tests that low delivery (<18%) is strictly clamped to TRAP status."""
        stock = {
            "symbol": "CHURN_TRAP",
            "close": 500.0,
            "open": 460.0,
            "high": 505.0,
            "low": 455.0,
            "change": 9.5,
            "relative_volume_10d_calc": 12.0,  # High volume!
            "RSI": 75.0,
            "VWAP": 480.0,
            "ATR": 15.0,
            "price_52_week_high": 550.0,
            "float_shares_outstanding": 50000000.0,
            "market_cap_basic": 25000000000,
            "debt_to_equity_fq": 1.5
        }
        deliv = {
            "has_data": True,
            "latest_delivery_pct": 9.5,  # ONLY 9.5% delivery!
            "latest_delivery_qty": 500000,
            "delivery_velocity": -8.0,
            "trajectory_label": "DISTRIBUTION_CHURN"
        }
        dvm = DVMScorer.calculate_scores(stock)
        res = ContinuationProbabilityEngine.evaluate_candidate(stock, deliv, dvm, horizon="TODAY")

        # Invariant: Low delivery MUST NOT exceed 42.0% probability
        assert res["continuation_probability_pct"] <= 42.0
        assert res["verdict"] == "RETAIL_TRAP_FADE_RISK"
        assert "Retail Churn" in res["verdict_badge"]

    def test_upper_wick_trap_firewall(self):
        """Tests that massive overhead wick rejection (>35%) is clamped to TRAP status."""
        stock = {
            "symbol": "WICK_TRAP",
            "close": 200.0,
            "open": 180.0,
            "high": 250.0,  # Extreme upper wick: closed at 200 after hitting 250!
            "low": 178.0,
            "change": 11.0,
            "relative_volume_10d_calc": 4.0,
            "RSI": 72.0,
            "VWAP": 215.0,
            "ATR": 12.0,
            "price_52_week_high": 250.0,
            "float_shares_outstanding": 20000000.0,
            "market_cap_basic": 10000000000,
            "debt_to_equity_fq": 0.4
        }
        deliv = {
            "has_data": True,
            "latest_delivery_pct": 42.0,  # Delivery is OK, but wick is devastating!
            "latest_delivery_qty": 300000,
            "delivery_velocity": 0.0,
            "trajectory_label": "STABLE_DELIVERY"
        }
        dvm = DVMScorer.calculate_scores(stock)
        res = ContinuationProbabilityEngine.evaluate_candidate(stock, deliv, dvm, horizon="TODAY")

        assert res["upper_wick_ratio"] > 0.35
        # Invariant: Severe upper wick MUST NOT exceed 42.0% probability
        assert res["continuation_probability_pct"] <= 42.0
        assert res["verdict"] == "RETAIL_TRAP_FADE_RISK"
        assert "Supply Rejection" in res["verdict_badge"]

    def test_circuit_freeze_sentinel(self):
        """Tests that stocks locked in Upper Circuit are flagged as CIRCUIT_LOCKED_ILLIQUID."""
        stock = {
            "symbol": "CIRCUIT_KING",
            "close": 500.0,
            "open": 498.0,
            "high": 500.0,  # Closed at peak
            "low": 498.0,
            "change": 10.0,  # Exactly 10.0% circuit limit!
            "relative_volume_10d_calc": 1.5,
            "RSI": 75.0,
            "VWAP": 499.5,
            "ATR": 10.0,
            "price_52_week_high": 500.0,
            "float_shares_outstanding": 10000000.0,
            "market_cap_basic": 5000000000,
            "debt_to_equity_fq": 0.2
        }
        deliv = {
            "has_data": True,
            "latest_delivery_pct": 65.0,
            "latest_delivery_qty": 200000,
            "delivery_velocity": 5.0,
            "trajectory_label": "STAIRCASE_ACCUMULATION"
        }
        dvm = DVMScorer.calculate_scores(stock)
        res = ContinuationProbabilityEngine.evaluate_candidate(stock, deliv, dvm, horizon="TODAY")

        assert res["is_circuit_locked"] is True
        assert res["verdict"] == "CIRCUIT_LOCKED_ILLIQUID"
        assert "Upper Circuit Locked" in res["verdict_badge"]
        assert "UPPER CIRCUIT FREEZE" in res["orb15_playbook"]["gap_up_rule"]

    def test_macro_drag_multiplier(self):
        """Tests that broad market gap-downs discount high-beta stock probabilities."""
        stock = {
            "symbol": "HIGH_BETA_RUNNER",
            "close": 1000.0,
            "open": 960.0,
            "high": 1005.0,
            "low": 955.0,
            "change": 4.5,
            "relative_volume_10d_calc": 3.0,
            "RSI": 65.0,
            "VWAP": 985.0,
            "ATR": 20.0,
            "price_52_week_high": 1010.0,
            "float_shares_outstanding": 20000000.0,
            "market_cap_basic": 20000000000,
            "beta_1_year": 1.8,  # High beta!
            "debt_to_equity_fq": 0.3
        }
        deliv = {
            "has_data": True,
            "latest_delivery_pct": 52.0,
            "latest_delivery_qty": 300000,
            "delivery_velocity": 4.0,
            "trajectory_label": "STAIRCASE_ACCUMULATION"
        }
        dvm = DVMScorer.calculate_scores(stock)

        # Baseline (No macro drag)
        res_base = ContinuationProbabilityEngine.evaluate_candidate(stock, deliv, dvm, horizon="TODAY")

        # Heavy Macro Drag: Nifty -2.0%, CMMI 20 (Severe Bearish)
        bear_macro = {
            "cmmi_score": 20.0,
            "nifty_change_pct": -2.0,
            "overall_regime": "CAPITAL_PRESERVATION"
        }
        res_dragged = ContinuationProbabilityEngine.evaluate_candidate(
            stock, deliv, dvm, horizon="TODAY", macro_context=bear_macro
        )

        assert res_dragged["macro_multiplier"] < 0.90
        assert res_dragged["continuation_probability_pct"] < res_base["continuation_probability_pct"]
        # Verify factor was recorded
        assert any("Macro Risk-Off Drag" in f["name"] for f in res_dragged["factor_breakdown"])
