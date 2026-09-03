"""
Second-Derivative Earnings Acceleration Vector Engine.
Computes true mathematical acceleration (second derivative) across Revenue, EBIT, PAT, OPM, and EPS,
using Year-over-Year (YoY) trajectory differences to eliminate quarterly festive/cyclical seasonality.
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class EarningsAccelerationEngine:
    """
    Evaluates the rate of change of growth (Second Derivative: ΔGrowth):
    Acceleration = (YoY Growth Rate Q0) - (YoY Growth Rate Q-1)
    """

    @staticmethod
    def calculate_acceleration_vector(
        quarterly_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Takes quarterly chronological income statements (minimum 6 quarters for 2 YoY points).
        
        Quarter Layout:
        Q[i]   = Current quarter (Q0)
        Q[i-4] = Same quarter last year (Q-4) -> Gives YoY Growth Q0
        Q[i-1] = Previous quarter (Q-1)
        Q[i-5] = Previous quarter last year (Q-5) -> Gives YoY Growth Q-1
        """
        if not quarterly_results or len(quarterly_results) < 6:
            return {
                "acceleration_status": "INSUFFICIENT_HISTORY",
                "revenue_acceleration_pct_points": 0.0,
                "ebit_acceleration_pct_points": 0.0,
                "pat_acceleration_pct_points": 0.0,
                "opm_delta_pct_points": 0.0,
                "latest_revenue_yoy_pct": 0.0,
                "previous_revenue_yoy_pct": 0.0,
                "latest_pat_yoy_pct": 0.0,
                "previous_pat_yoy_pct": 0.0,
                "is_earnings_accelerating": False,
            }

        q = sorted(quarterly_results, key=lambda x: x.get("period_end_date", ""))
        q0 = q[-1]
        q_minus_1 = q[-2]
        q_minus_4 = q[-5] if len(q) >= 5 else None
        q_minus_5 = q[-6] if len(q) >= 6 else None

        if not q_minus_4 or not q_minus_5:
            return {
                "acceleration_status": "INSUFFICIENT_HISTORY",
                "revenue_acceleration_pct_points": 0.0,
                "ebit_acceleration_pct_points": 0.0,
                "pat_acceleration_pct_points": 0.0,
                "opm_delta_pct_points": 0.0,
                "is_earnings_accelerating": False,
            }

        # Helper to compute safe YoY growth
        def yoy_growth(curr: float, base: float) -> float:
            if not base or abs(base) < 0.1:
                return 0.0
            return round(((curr - base) / abs(base)) * 100.0, 2)

        # 1. Revenue Acceleration
        rev_q0 = q0.get("revenue_cr", 0.0) or q0.get("sales_cr", 0.0)
        rev_q4 = q_minus_4.get("revenue_cr", 0.0) or q_minus_4.get("sales_cr", 0.0)
        rev_q1 = q_minus_1.get("revenue_cr", 0.0) or q_minus_1.get("sales_cr", 0.0)
        rev_q5 = q_minus_5.get("revenue_cr", 0.0) or q_minus_5.get("sales_cr", 0.0)

        rev_yoy_q0 = yoy_growth(rev_q0, rev_q4)
        rev_yoy_q1 = yoy_growth(rev_q1, rev_q5)
        rev_accel = round(rev_yoy_q0 - rev_yoy_q1, 2)

        # 2. Operating Profit / EBIT Acceleration
        ebit_q0 = q0.get("ebit_cr", 0.0) or q0.get("operating_profit_cr", 0.0)
        ebit_q4 = q_minus_4.get("ebit_cr", 0.0) or q_minus_4.get("operating_profit_cr", 0.0)
        ebit_q1 = q_minus_1.get("ebit_cr", 0.0) or q_minus_1.get("operating_profit_cr", 0.0)
        ebit_q5 = q_minus_5.get("ebit_cr", 0.0) or q_minus_5.get("operating_profit_cr", 0.0)

        ebit_yoy_q0 = yoy_growth(ebit_q0, ebit_q4)
        ebit_yoy_q1 = yoy_growth(ebit_q1, ebit_q5)
        ebit_accel = round(ebit_yoy_q0 - ebit_yoy_q1, 2)

        # 3. PAT Acceleration
        pat_q0 = q0.get("net_profit_cr", 0.0) or q0.get("pat_cr", 0.0)
        pat_q4 = q_minus_4.get("net_profit_cr", 0.0) or q_minus_4.get("pat_cr", 0.0)
        pat_q1 = q_minus_1.get("net_profit_cr", 0.0) or q_minus_1.get("pat_cr", 0.0)
        pat_q5 = q_minus_5.get("net_profit_cr", 0.0) or q_minus_5.get("pat_cr", 0.0)

        pat_yoy_q0 = yoy_growth(pat_q0, pat_q4)
        pat_yoy_q1 = yoy_growth(pat_q1, pat_q5)
        pat_accel = round(pat_yoy_q0 - pat_yoy_q1, 2)

        # 4. Operating Margin Expansion (OPM Delta YoY)
        opm_q0 = round((ebit_q0 / max(0.1, rev_q0)) * 100.0, 2) if rev_q0 else 0.0
        opm_q4 = round((ebit_q4 / max(0.1, rev_q4)) * 100.0, 2) if rev_q4 else 0.0
        opm_delta = round(opm_q0 - opm_q4, 2)

        # Synthesis Classification
        is_accelerating = (pat_accel > 5.0 and rev_accel > 0.0) or (ebit_accel > 8.0 and opm_delta > 1.0)

        if pat_accel >= 15.0 and rev_accel >= 10.0 and opm_delta > 1.5:
            status = "ACCELERATING_EARNINGS_EXPLOSION"
        elif pat_accel > 5.0 and rev_accel > 0.0:
            status = "STEADY_ACCELERATION"
        elif pat_accel >= -5.0 and pat_yoy_q0 >= 20.0:
            status = "HIGH_PLATEAU_COMPOUNDING"
        elif pat_accel < -10.0:
            status = "DECELERATING_SLOWDOWN"
        else:
            status = "NORMAL_FLUCTUATION"

        return {
            "acceleration_status": status,
            "is_earnings_accelerating": is_accelerating,
            "revenue_acceleration_pct_points": rev_accel,
            "ebit_acceleration_pct_points": ebit_accel,
            "pat_acceleration_pct_points": pat_accel,
            "opm_delta_pct_points": opm_delta,
            "latest_quarter_period": q0.get("period_label", "Q0"),
            "latest_revenue_yoy_pct": rev_yoy_q0,
            "previous_revenue_yoy_pct": rev_yoy_q1,
            "latest_pat_yoy_pct": pat_yoy_q0,
            "previous_pat_yoy_pct": pat_yoy_q1,
            "current_opm_pct": opm_q0,
        }
