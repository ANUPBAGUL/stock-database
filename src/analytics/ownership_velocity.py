"""
Institutional Ownership Velocity & Dilution Event Registry Engine.
Measures the velocity and acceleration of institutional accumulation across quarterly filings,
and monitors share capital expansion from QIPs, Warrants, Preferential Allotments, and ESOP pools.
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class OwnershipVelocityEngine:
    """
    Evaluates institutional accumulation momentum (Velocity = ΔInst / ΔQuarter)
    and flags equity dilution events.
    """

    @staticmethod
    def calculate_ownership_velocity(
        shareholding_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Takes quarterly SEBI LODR shareholding patterns in chronological order.
        """
        if not shareholding_history or len(shareholding_history) < 2:
            return {
                "velocity_status": "INSUFFICIENT_HISTORY",
                "fii_1q_delta_pct": 0.0,
                "dii_1q_delta_pct": 0.0,
                "inst_1q_delta_pct": 0.0,
                "inst_1y_delta_pct": 0.0,
                "promoter_1y_delta_pct": 0.0,
                "institutional_velocity_trend": "FLAT",
            }

        sh = sorted(shareholding_history, key=lambda x: str(x.get("period_end_date", "")))
        curr = sh[-1]
        prev_1q = sh[-2]

        def _find_sh_1y():
            c_ped = curr.get("period_end_date")
            if not c_ped:
                return sh[-5] if len(sh) >= 5 else sh[0]
            if isinstance(c_ped, str):
                try:
                    from datetime import datetime as dt
                    c_dt = dt.strptime(c_ped[:10], "%Y-%m-%d").date()
                except Exception:
                    return sh[-5] if len(sh) >= 5 else sh[0]
            elif hasattr(c_ped, "year"):
                c_dt = c_ped
            else:
                return sh[-5] if len(sh) >= 5 else sh[0]

            t_year = c_dt.year - 1
            t_month = c_dt.month
            for cand in sh:
                cand_ped = cand.get("period_end_date")
                if not cand_ped: continue
                cand_dt = dt.strptime(cand_ped[:10], "%Y-%m-%d").date() if isinstance(cand_ped, str) else cand_ped
                if hasattr(cand_dt, "year") and cand_dt.year == t_year and cand_dt.month == t_month:
                    return cand
            return sh[-5] if len(sh) >= 5 else sh[0]

        prev_1y = _find_sh_1y()

        curr_fii = curr.get("fii_holding_pct", 0.0) or 0.0
        curr_dii = curr.get("dii_holding_pct", 0.0) or 0.0
        curr_inst = round(curr_fii + curr_dii, 2)
        curr_prom = curr.get("promoter_holding_pct", 0.0) or 0.0

        p1q_fii = prev_1q.get("fii_holding_pct", 0.0) or 0.0
        p1q_dii = prev_1q.get("dii_holding_pct", 0.0) or 0.0
        p1q_inst = round(p1q_fii + p1q_dii, 2)

        p1y_inst = round((prev_1y.get("fii_holding_pct", 0.0) or 0.0) + (prev_1y.get("dii_holding_pct", 0.0) or 0.0), 2)
        p1y_prom = prev_1y.get("promoter_holding_pct", 0.0) or 0.0

        delta_1q_fii = round(curr_fii - p1q_fii, 2)
        delta_1q_dii = round(curr_dii - p1q_dii, 2)
        delta_1q_inst = round(curr_inst - p1q_inst, 2)
        delta_1y_inst = round(curr_inst - p1y_inst, 2)
        delta_1y_prom = round(curr_prom - p1y_prom, 2)

        # Acceleration check (2 quarters vs 1 quarter)
        if len(sh) >= 3:
            prev_2q_inst = round((sh[-3].get("fii_holding_pct", 0.0) or 0.0) + (sh[-3].get("dii_holding_pct", 0.0) or 0.0), 2)
            prev_delta_inst = round(p1q_inst - prev_2q_inst, 2)
            accel_inst = round(delta_1q_inst - prev_delta_inst, 2)
        else:
            accel_inst = 0.0

        if delta_1y_inst >= 4.0 and delta_1q_inst > 0.5:
            trend = "AGGRESSIVE_INSTITUTIONAL_ACCUMULATION"
        elif delta_1y_inst > 1.0:
            trend = "STEADY_INSTITUTIONAL_INFLOW"
        elif delta_1y_inst <= -3.0:
            trend = "INSTITUTIONAL_DISTRIBUTION"
        else:
            trend = "NEUTRAL_HOLDING"

        return {
            "current_institutional_pct": curr_inst,
            "current_promoter_pct": curr_prom,
            "fii_1q_delta_pct": delta_1q_fii,
            "dii_1q_delta_pct": delta_1q_dii,
            "inst_1q_delta_pct": delta_1q_inst,
            "inst_1y_delta_pct": delta_1y_inst,
            "promoter_1y_delta_pct": delta_1y_prom,
            "inst_acceleration_pct": accel_inst,
            "institutional_velocity_trend": trend,
            "is_institutional_accumulating": (delta_1y_inst > 1.0 or delta_1q_inst > 0.8),
        }

    @staticmethod
    def audit_dilution_mechanisms(
        current_share_count: Optional[float],
        previous_year_share_count: Optional[float],
        disclosures_list: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Audits share capital dilution across QIPs, Warrants, Preferential Allotments, and ESOPs.
        """
        dilution_pct = 0.0
        is_diluted = False
        dilution_event_type = "NONE"

        if current_share_count and previous_year_share_count and previous_year_share_count > 0:
            dilution_pct = round(((current_share_count - previous_year_share_count) / previous_year_share_count) * 100.0, 2)
            if dilution_pct > 2.0:
                is_diluted = True
                dilution_event_type = "SHARE_CAPITAL_EXPANSION"

        # Check announcements text for explicit dilution triggers
        flagged_events = []
        if disclosures_list:
            for d in disclosures_list:
                hl = (d.get("headline", "") or "").upper()
                if "QIP" in hl or "QUALIFIED INSTITUTIONAL PLACEMENT" in hl:
                    flagged_events.append("QIP_PLACEMENT")
                elif "WARRANT" in hl:
                    flagged_events.append("WARRANTS_ALLOTMENT")
                elif "PREFERENTIAL" in hl:
                    flagged_events.append("PREFERENTIAL_ISSUE")
                elif "ESOP" in hl:
                    flagged_events.append("ESOP_ALLOTMENT")

        if flagged_events:
            dilution_event_type = flagged_events[0]
            is_diluted = True

        return {
            "is_dilution_detected": is_diluted,
            "trailing_1y_dilution_pct": dilution_pct,
            "primary_dilution_event": dilution_event_type,
            "flagged_dilution_mechanisms": list(set(flagged_events))
        }
