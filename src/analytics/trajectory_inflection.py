"""
Pillar 1 & Synthesis: Trajectory Inflection Engine & Institutional Multibagger Discovery Hub.

Combines the 5 quantitative pillars:
1. Pillar 1: Nonlinear Inflection & 2nd-Derivative Acceleration (Δ² EBITDA > 0, Compounding Multiplier)
2. Pillar 2: Capacity-Constrained TAM/SAM/SOM Runway
3. Pillar 3: Working Capital Forensic Sentinel (Debtor Drift & CFO Conversion)
4. Pillar 4: The Expectations Gap (Mauboussin Model)
5. Pillar 5: Quantitative Price Structure, Mansfield RS vs NIFTY 50, & VCP Absorption

Implements Strict Hard Circuit Breakers to reject value traps, accounting frauds, and declining trends.
"""

from typing import Dict, Any, Optional, List, Tuple
import logging

from src.analytics.working_capital_sentinel import WorkingCapitalSentinel
from src.analytics.expectations_gap_engine import ExpectationsGapEngine
from src.analytics.price_structure_engine import PriceStructureEngine
from src.analytics.granular_tam_engine import GranularTAMEngine
from src.analytics.valuation_engine import ValuationEngine

logger = logging.getLogger(__name__)


class TrajectoryInflectionEngine:
    """
    Core synthesis engine computing nonlinear compounding power, second-derivative inflection,
    and institutional multibagger classification across all 5 pillars.
    """

    @staticmethod
    def detect_second_derivative_acceleration(
        ebitda_history: List[float],
        margin_history: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        Calculates first and second derivatives of EBITDA and Profit Margins.
        Acceleration is confirmed when Δ² EBITDA > 0.
        """
        if not ebitda_history or len(ebitda_history) < 3:
            return {
                "is_accelerating": False,
                "delta_ebitda": None,
                "delta2_ebitda": None,
                "delta_margin": None,
                "summary": "Insufficient quarterly history to evaluate 2nd derivative acceleration."
            }

        # EBITDA 1st & 2nd derivatives
        d1_current = ebitda_history[-1] - ebitda_history[-2]
        d1_prev = ebitda_history[-2] - ebitda_history[-3]
        d2 = round(d1_current - d1_prev, 2)

        is_accelerating = bool(d2 > 0 and d1_current > 0)

        # Margin expansion check
        delta_margin = None
        if margin_history and len(margin_history) >= 2:
            delta_margin = round(margin_history[-1] - margin_history[-2], 2)

        if is_accelerating and delta_margin and delta_margin > 0:
            summary = f"Confirmed Inflection: EBITDA accelerating (+₹{d2:.1f} Cr 2nd derivative) with expanding margins (+{delta_margin:.1f}%)."
        elif is_accelerating:
            summary = f"EBITDA acceleration positive (+₹{d2:.1f} Cr Δ² EBITDA)."
        else:
            summary = "EBITDA growth linear or decelerating."

        return {
            "is_accelerating": is_accelerating,
            "delta_ebitda": round(d1_current, 2),
            "delta2_ebitda": d2,
            "delta_margin": delta_margin,
            "summary": summary
        }

    @staticmethod
    def calculate_multiplicative_compounding_score(
        roic_pct: Optional[float],
        reinvestment_rate_pct: Optional[float],
        op_leverage_multiplier: float = 0.0
    ) -> float:
        """
        Calculates non-linear compounding score (0 to 100) based on multiplicative product:
        Compounding = (ROIC * Reinvestment Rate) * (1 + Op Leverage)
        """
        if roic_pct is None or reinvestment_rate_pct is None:
            return 20.0  # Baseline neutral

        roic_eff = max(0.0, min(80.0, roic_pct))
        reinv_eff = max(0.0, min(90.0, reinvestment_rate_pct))
        op_eff = max(-0.5, min(0.5, op_leverage_multiplier))

        raw_compounding_rate = (roic_eff * reinv_eff) / 100.0
        adjusted_rate = raw_compounding_rate * (1.0 + op_eff)

        # Scale to 0 - 100 score (e.g. 25% compounding rate -> score ~ 85)
        score = min(100.0, (adjusted_rate / 30.0) * 100.0)
        return round(score, 1)

    @classmethod
    def synthesize_5pillar_multibagger_matrix(
        cls,
        symbol: str,
        sector: str,
        current_revenue_cr: Optional[float],
        gross_block_cr: Optional[float],
        cwip_cr: Optional[float],
        asset_turnover: Optional[float],
        ebitda_history: List[float],
        margin_history: Optional[List[float]],
        current_receivables_cr: Optional[float],
        current_inventories_cr: Optional[float],
        current_payables_cr: Optional[float],
        current_cfo_cr: Optional[float],
        current_ebitda_cr: Optional[float],
        revenue_growth_yoy_pct: Optional[float],
        receivables_growth_yoy_pct: Optional[float],
        dso_history: Optional[List[float]],
        economic_roic_pct: Optional[float],
        reinvestment_rate_pct: Optional[float],
        market_implied_growth_5y_pct: Optional[float],
        daily_closes: List[float],
        benchmark_closes: Optional[List[float]] = None,
        daily_highs: Optional[List[float]] = None,
        daily_lows: Optional[List[float]] = None,
        daily_volumes: Optional[List[float]] = None,
        current_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes all 5 pillars into a single institutional discovery verdict.
        """
        # 1. Pillar 1: Nonlinear Inflection
        inflection_res = cls.detect_second_derivative_acceleration(ebitda_history, margin_history)
        compounding_score = cls.calculate_multiplicative_compounding_score(
            economic_roic_pct, reinvestment_rate_pct
        )

        # 2. Pillar 2: Granular TAM & Capacity
        tam_res = GranularTAMEngine.evaluate_tam_capacity_funnel(
            symbol=symbol,
            sector=sector,
            current_revenue_cr=current_revenue_cr,
            gross_block_cr=gross_block_cr,
            cwip_cr=cwip_cr,
            asset_turnover=asset_turnover,
            revenue_growth_cagr_pct=revenue_growth_yoy_pct or 20.0
        )

        # 3. Pillar 3: Working Capital Sentinel
        wc_res = WorkingCapitalSentinel.audit_forensic_risk(
            current_receivables_cr=current_receivables_cr,
            current_revenue_cr=current_revenue_cr,
            current_inventories_cr=current_inventories_cr,
            current_payables_cr=current_payables_cr,
            current_cfo_cr=current_cfo_cr,
            current_ebitda_cr=current_ebitda_cr,
            revenue_growth_yoy_pct=revenue_growth_yoy_pct,
            receivables_growth_yoy_pct=receivables_growth_yoy_pct,
            dso_history=dso_history
        )

        # 4. Pillar 4: Expectations Gap
        exp_res = ExpectationsGapEngine.evaluate_expectations(
            economic_roic_pct=economic_roic_pct,
            reinvestment_rate_pct=reinvestment_rate_pct,
            market_implied_growth_5y_pct=market_implied_growth_5y_pct
        )

        # 5. Pillar 5: Price Structure & Mansfield RS
        price_res = PriceStructureEngine.audit_price_structure(
            daily_closes=daily_closes,
            benchmark_closes=benchmark_closes,
            daily_highs=daily_highs,
            daily_lows=daily_lows,
            daily_volumes=daily_volumes,
            current_price=current_price
        )

        # ──────────────────────────────────────────────────────────────
        # Circuit Breakers & Composite Scoring
        # ──────────────────────────────────────────────────────────────
        is_wc_trap = wc_res.get("is_circuit_breaker_triggered", False)
        is_stage4_decline = price_res.get("is_stage4_circuit_breaker", False)

        circuit_breaker_flags = []
        if is_wc_trap:
            circuit_breaker_flags.append("Working Capital Trap: Severe uncollected receivables or CFO deficit.")
        if is_stage4_decline:
            circuit_breaker_flags.append("Stage 4 Downtrend: Severe institutional distribution below 200DMA.")

        # Composite Score Calculation (0 - 100)
        # Weighting: Inflection (25%), TAM Runway (20%), WC Health (20%), Expectations Gap (20%), Price Structure (15%)
        wc_health_score = max(0, 100 - wc_res.get("risk_score", 0))

        gap_score = 50  # baseline
        gap_pct = exp_res.get("expectations_gap_pct")
        if gap_pct is not None:
            if gap_pct >= 8.0:
                gap_score = 100
            elif gap_pct >= 2.0:
                gap_score = 80
            elif gap_pct >= -3.0:
                gap_score = 60
            elif gap_pct >= -10.0:
                gap_score = 30
            else:
                gap_score = 10

        tam_runway_score = 50
        runway_yrs = tam_res.get("growth_runway_years")
        if runway_yrs is not None:
            if runway_yrs >= 7.0:
                tam_runway_score = 100
            elif runway_yrs >= 4.0:
                tam_runway_score = 75
            elif runway_yrs >= 2.0:
                tam_runway_score = 50
            else:
                tam_runway_score = 25

        tech_score = price_res.get("technical_score", 50)

        composite_score = round(
            (compounding_score * 0.25)
            + (tam_runway_score * 0.20)
            + (wc_health_score * 0.20)
            + (gap_score * 0.20)
            + (tech_score * 0.15),
            1
        )

        # Classification Hierarchy
        if circuit_breaker_flags:
            tier = "DISQUALIFIED_BY_CIRCUIT_BREAKER"
            badge = "badge-rose"
            verdict = f"DISQUALIFIED: {' '.join(circuit_breaker_flags)}"
        elif composite_score >= 80.0 and exp_res.get("status") in ("HIGH_ASYMMETRY_UNDERVALUATION", "MODERATE_POSITIVE_GAP"):
            tier = "TIER_1_ASYMMETRIC_INFLECTION"
            badge = "badge-emerald"
            verdict = "High-conviction asymmetric multibagger inflection: Pristine balance sheet, positive expectations gap, and accelerating compounding."
        elif composite_score >= 65.0:
            tier = "TIER_2_HIGH_QUALITY_COMPOUNDER"
            badge = "badge-teal"
            verdict = "Solid compounder with durable economic moat and healthy capital allocation runway."
        elif price_res.get("stage_analysis", {}).get("is_stage2") and tech_score >= 70:
            tier = "TACTICAL_MOMENTUM_RUNNER"
            badge = "badge-blue"
            verdict = "Stage 2 momentum tailwind with acceptable fundamentals."
        elif composite_score >= 45.0:
            tier = "WATCHLIST_INCUBATING"
            badge = "badge-yellow"
            verdict = "Incubating candidate: Awaiting clearer 2nd derivative inflection or valuation pullback."
        else:
            tier = "AVOID_OR_DISTRIBUTION"
            badge = "badge-zinc"
            verdict = "Sub-par fundamentals or demanding expectations; low risk-reward asymmetry."

        return {
            "symbol": symbol,
            "tier": tier,
            "badge_class": badge,
            "composite_5pillar_score": composite_score,
            "circuit_breaker_triggered": bool(circuit_breaker_flags),
            "circuit_breaker_reasons": circuit_breaker_flags,
            "verdict_summary": verdict,
            "pillar_1_inflection": {
                "compounding_score": compounding_score,
                "acceleration": inflection_res
            },
            "pillar_2_tam_capacity": tam_res,
            "pillar_3_working_capital": wc_res,
            "pillar_4_expectations_gap": exp_res,
            "pillar_5_price_structure": price_res
        }
