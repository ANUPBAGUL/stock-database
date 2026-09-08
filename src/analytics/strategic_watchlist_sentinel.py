"""
Strategic Watchlist Graduation Sentinel & Dynamic Acceleration Engine.

Monitors high-potential compounders residing in the STRATEGIC_WATCHLIST and evaluates
their mathematical transition readiness toward CONVICTION_BUY or SWING_SETUP.

Graduation Triggers:
1. VCP_TIGHTNESS_GRADUATION:
   - Entry Quality rises from < 70 to >= 75
   - ATR Contraction ratio <= 0.80 or micro-handle detected
2. 50EMA_ACCUMULATION_GRADUATION:
   - Price pulls back cleanly into the 50-day EMA support zone (+/- 1.5%)
   - Volume dries up to <= 75% of average, indicating supply exhaustion
3. EXPECTATIONS_ASYMMETRY_EXPANSION:
   - Price pullback or earnings growth widens the expectations asymmetry gap to >= +8.0%
"""

from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class StrategicWatchlistSentinel:
    """
    Evaluates graduation readiness for companies on the Strategic Watchlist.
    """

    @classmethod
    def evaluate_candidate_graduation(
        cls,
        candidate_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluates a single strategic candidate for graduation readiness (0-100%).
        """
        cmp = float(candidate_data.get("cmp") or 0.0)
        potential = float(candidate_data.get("business_potential_score") or 75.0)
        asym_gap = float(candidate_data.get("expectations_asymmetry_gap_pct") or 0.0)
        tape = float(candidate_data.get("tape_confirmation_score") or 50.0)
        entry_q = float(candidate_data.get("entry_quality_score") or 50.0)
        
        ema50 = candidate_data.get("ema50") or candidate_data.get("support_price_50d")
        h1m = candidate_data.get("high_1m") or candidate_data.get("high_52w")
        atr_raw = candidate_data.get("atr_20d") or candidate_data.get("atr_live")
        atr = float(atr_raw) if (atr_raw is not None and float(atr_raw) > 0) else (cmp * 0.02)
        
        # Calculate distance to 50 EMA and 1M pivot
        dist_ema50_pct = round(((cmp - ema50) / ema50) * 100.0, 2) if (ema50 and ema50 > 0) else 0.0
        dist_pivot_pct = round(((cmp - h1m) / h1m) * 100.0, 2) if (h1m and h1m > 0) else -5.0

        # Graduation Vector 1: Entry Quality & Tightness Readiness (40 pts)
        # Entry Q of 75+ gets full 40 pts, scaling down linearly
        entry_readiness = min(40.0, max(10.0, (entry_q / 75.0) * 40.0))

        # Graduation Vector 2: Support Zone Proximity (30 pts)
        # Proximity to 50-EMA support (-1.5% to +1.5% is prime accumulation zone)
        if -1.5 <= dist_ema50_pct <= 2.0:
            support_readiness = 30.0
        elif 2.0 < dist_ema50_pct <= 5.0:
            support_readiness = 20.0
        elif dist_ema50_pct > 5.0:
            # Extended above 50-EMA; needs to base or pull back
            support_readiness = max(5.0, 25.0 - (dist_ema50_pct * 1.5))
        else:
            # Below 50-EMA; caution
            support_readiness = 10.0

        # Graduation Vector 3: Expectations Asymmetry Gap (30 pts)
        # Asym Gap of +8.0% or higher gets full 30 pts
        if asym_gap >= 12.0:
            asym_readiness = 30.0
        elif asym_gap >= 8.0:
            asym_readiness = 25.0
        elif asym_gap > 0.0:
            asym_readiness = 15.0 + (asym_gap * 1.0)
        else:
            # Stretched valuation gap
            asym_readiness = max(5.0, 15.0 + asym_gap) # penalizes negative gap

        total_readiness = round(entry_readiness + support_readiness + asym_readiness, 1)
        total_readiness = min(99.0, max(15.0, total_readiness))

        # Determine Graduation Category & Next Immediate Trigger
        target_pivot = round(h1m + max(0.12 * atr, cmp * 0.0015), 2) if h1m else round(cmp * 1.02, 2)
        target_support = round(ema50, 2) if ema50 else round(cmp * 0.96, 2)

        if total_readiness >= 85.0:
            status = "GRADUATION_IMMIGRATION_READY"
            if entry_q >= 75.0 and asym_gap >= 8.0:
                trigger = "VCP_TIGHTNESS_GRADUATION"
                note = f"Elite Quality ({potential:.0f}/100) + Favorable Asym Gap (+{asym_gap:.1f}%). Ready to deploy on pivot breakout above Rs.{target_pivot}."
            elif -1.5 <= dist_ema50_pct <= 1.5:
                trigger = "50EMA_ACCUMULATION_GRADUATION"
                note = f"Prime Pullback Zone at 50-EMA support (Rs.{target_support}). Accumulation on dips supported."
            else:
                trigger = "VCP_TIGHTNESS_GRADUATION"
                note = f"High readiness ({total_readiness:.0f}%). Awaiting final VCP contraction handle."
        elif total_readiness >= 70.0:
            status = "ADVANCING_BASE_BUILDER"
            if asym_gap < 8.0:
                trigger = "AWAITING_VALUATION_COOLOFF"
                note = f"High potential business ({potential:.0f}/100), but expectations gap ({asym_gap:+.1f}%) requires consolidation or earnings catch-up."
            else:
                trigger = "AWAITING_BASE_COMPLETION"
                note = f"Consolidating in base ({dist_pivot_pct:+.1f}% from pivot Rs.{target_pivot}). Track for volatility dry-up."
        else:
            status = "EARLY_STAGE_INCUBATION"
            trigger = "EARLY_BASE_CONSTRUCTION"
            note = f"Developing profile. Needs time to build institutional support baseline."

        return {
            "graduation_status": status,
            "graduation_readiness_pct": total_readiness,
            "graduation_trigger": trigger,
            "graduation_note": note,
            "target_pivot_price": target_pivot,
            "target_support_price": target_support,
            "distance_to_pivot_pct": dist_pivot_pct,
            "distance_to_support_pct": dist_ema50_pct
        }

    @classmethod
    def evaluate_strategic_cohort(
        cls,
        candidates: List[Any]
    ) -> List[Any]:
        """
        Enriches a cohort of strategic watchlist candidates with graduation telemetry.
        """
        for c in candidates:
            # Extract candidate data dict regardless of Pydantic model or dict
            c_dict = c if isinstance(c, dict) else c.__dict__
            grad = cls.evaluate_candidate_graduation(c_dict)
            
            if hasattr(c, "graduation_status"):
                c.graduation_status = grad["graduation_status"]
                c.graduation_readiness_pct = grad["graduation_readiness_pct"]
                c.graduation_trigger = grad["graduation_trigger"]
                c.graduation_target_pivot = grad["target_pivot_price"]
            elif isinstance(c, dict):
                c.update(grad)

        return candidates
