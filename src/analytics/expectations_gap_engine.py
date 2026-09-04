"""
Pillar 4: The Expectations Gap Engine.

Implements Michael Mauboussin's *Expectations Investing* and Bruce Greenwald's
*Earnings Power Value & Sustainable Compounding* frameworks for Indian equities.

Key Concept:
Stocks don't outperform merely because the business is high quality; they outperform
when the business's intrinsic compounding rate outpaces the market's implied expectations.

Formula:
Expectations Gap = Intrinsic Compounding Rate (%) - Reverse-DCF Implied 5Y Growth (%)

Where:
Intrinsic Compounding Rate = (Economic ROIC * Reinvestment Rate) * (1 + Operating Leverage Multiplier)
"""

from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ExpectationsGapEngine:
    """
    Computes the mathematical gap between fundamental compounding power
    and market-implied growth hurdles.
    """

    @staticmethod
    def calculate_sustainable_compounding_rate(
        economic_roic_pct: Optional[float],
        reinvestment_rate_pct: Optional[float],
        operating_leverage_multiplier: float = 0.0
    ) -> Optional[float]:
        """
        Computes intrinsic compounding velocity:
        Compounding Rate = (ROIC * Reinvestment Rate) * (1 + Operating Leverage Multiplier)

        E.g., ROIC = 30.0%, Reinvestment Rate = 60.0% -> Base = 18.0%.
        With 15% operating leverage kick -> 18.0% * 1.15 = 20.7%.
        """
        if economic_roic_pct is None or reinvestment_rate_pct is None:
            return None

        # Clamp inputs to economically sensible bounds
        clamped_roic = max(0.0, min(100.0, economic_roic_pct))
        clamped_reinv = max(0.0, min(100.0, reinvestment_rate_pct))
        clamped_op_lev = max(-0.5, min(0.5, operating_leverage_multiplier))

        base_compounding_rate = (clamped_roic * clamped_reinv) / 100.0
        adjusted_rate = base_compounding_rate * (1.0 + clamped_op_lev)

        return round(adjusted_rate, 2)

    @staticmethod
    def calculate_expectations_gap(
        intrinsic_compounding_rate_pct: Optional[float],
        market_implied_growth_5y_pct: Optional[float]
    ) -> Tuple[Optional[float], str, str, str]:
        """
        Calculates the delta between fundamental compounding and market price hurdle.

        Returns:
            (gap_pct, classification, badge_class, verdict_summary)
        """
        if intrinsic_compounding_rate_pct is None or market_implied_growth_5y_pct is None:
            return None, "GAP_UNKNOWN", "badge-zinc", "Insufficient data to solve expectations gap."

        gap_pct = round(intrinsic_compounding_rate_pct - market_implied_growth_5y_pct, 2)

        if gap_pct >= 8.0:
            regime = "HIGH_ASYMMETRY_UNDERVALUATION"
            badge = "badge-emerald"
            summary = f"Exceptional asymmetry (+{gap_pct:.1f}%): Fundamental compounding ({intrinsic_compounding_rate_pct:.1f}%) far exceeds market expectations ({market_implied_growth_5y_pct:.1f}%)."
        elif gap_pct >= 2.0:
            regime = "MODERATE_POSITIVE_GAP"
            badge = "badge-teal"
            summary = f"Positive expectations buffer (+{gap_pct:.1f}%): Business capable of outpacing priced-in growth."
        elif gap_pct >= -3.0:
            regime = "EFFICIENTLY_PRICED"
            badge = "badge-blue"
            summary = f"Efficiently valued ({gap_pct:.1f}%): Market price accurately reflects intrinsic compounding rate."
        elif gap_pct >= -10.0:
            regime = "ELEVATED_EXPECTATIONS"
            badge = "badge-amber"
            summary = f"Demanding expectations ({gap_pct:.1f}%): Market requires {market_implied_growth_5y_pct:.1f}% growth vs fundamental run-rate {intrinsic_compounding_rate_pct:.1f}%."
        else:
            regime = "PRICED_FOR_PERFECTION_ASYMMETRIC_RISK"
            badge = "badge-rose"
            summary = f"Priced for perfection ({gap_pct:.1f}%): Severe vulnerability to valuation de-rating upon growth normalization."

        return gap_pct, regime, badge, summary

    @classmethod
    def evaluate_expectations(
        cls,
        economic_roic_pct: Optional[float],
        reinvestment_rate_pct: Optional[float],
        market_implied_growth_5y_pct: Optional[float],
        operating_leverage_multiplier: float = 0.0
    ) -> Dict[str, Any]:
        """
        Full evaluation pipeline for Pillar 4.
        """
        intrinsic_rate = cls.calculate_sustainable_compounding_rate(
            economic_roic_pct=economic_roic_pct,
            reinvestment_rate_pct=reinvestment_rate_pct,
            operating_leverage_multiplier=operating_leverage_multiplier
        )

        gap_pct, regime, badge, summary = cls.calculate_expectations_gap(
            intrinsic_compounding_rate_pct=intrinsic_rate,
            market_implied_growth_5y_pct=market_implied_growth_5y_pct
        )

        return {
            "intrinsic_compounding_rate_pct": intrinsic_rate,
            "market_implied_growth_5y_pct": market_implied_growth_5y_pct,
            "expectations_gap_pct": gap_pct,
            "status": regime,
            "badge_class": badge,
            "summary": summary
        }
