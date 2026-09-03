"""
Competitive Position & Industry Structure Engine (Michael Mauboussin "Measuring the Moat" Framework).
Evaluates Herfindahl-Hirschman Index (HHI) market concentration, pricing power resilience via gross margin volatility,
and classifies displacement dynamics ("Who loses when this company wins?").
"""
from typing import Dict, Any, List, Optional
import math
import statistics
import logging

logger = logging.getLogger(__name__)

# Sector-level concentration benchmarks (HHI and Top-3 Player Share in India)
INDUSTRY_CONCENTRATION_BENCHMARKS = {
    "SPECIALTY_FATS_CBE": {"hhi_benchmark": 3200, "cr3_pct": 78.0, "structure": "CONCENTRATED_OLIGOPOLY", "pricing_power_baseline": "HIGH"},
    "ELECTRONICS_MANUFACTURING_EMS": {"hhi_benchmark": 2200, "cr3_pct": 62.0, "structure": "MODERATELY_CONCENTRATED", "pricing_power_baseline": "MODERATE"},
    "IT_SERVICES_GLOBAL": {"hhi_benchmark": 1200, "cr3_pct": 45.0, "structure": "FRAGMENTED_TIERED", "pricing_power_baseline": "MODERATE"},
    "PHARMACEUTICALS_CRAMS_CDMO": {"hhi_benchmark": 2600, "cr3_pct": 68.0, "structure": "CONCENTRATED_NICHE", "pricing_power_baseline": "HIGH"},
    "DEFENSE_AEROSPACE_INDIGENOUS": {"hhi_benchmark": 4500, "cr3_pct": 90.0, "structure": "DUOPOLY_MONOPOLY", "pricing_power_baseline": "VERY_HIGH"},
    "GENERAL_MANUFACTURING": {"hhi_benchmark": 1500, "cr3_pct": 40.0, "structure": "COMPETITIVE_MODERATE", "pricing_power_baseline": "MODERATE"},
}

class CompetitivePositionEngine:
    """
    Evaluates market concentration, pricing power pass-through, and displacement dynamics.
    """

    @staticmethod
    def calculate_hhi(market_shares_pct: List[float]) -> Dict[str, Any]:
        """
        Computes the Herfindahl-Hirschman Index:
        HHI = Sum of squared market shares: sum(s_i^2)
        
        HHI > 2500 -> Concentrated Oligopoly
        1500 <= HHI <= 2500 -> Moderately Concentrated
        HHI < 1500 -> Fragmented / Competitive
        """
        if not market_shares_pct:
            return {
                "hhi_score": 1500,
                "concentration_regime": "COMPETITIVE_MODERATE",
                "cr3_pct": 0.0,
                "confidence": "ESTIMATED_DEFAULT"
            }

        shares = [max(0.0, min(100.0, s)) for s in market_shares_pct]
        hhi = round(sum(s ** 2 for s in shares), 1)

        # Top-3 Concentration Ratio (CR3)
        sorted_shares = sorted(shares, reverse=True)
        cr3 = round(sum(sorted_shares[:3]), 1)

        if hhi >= 2500 or cr3 >= 70.0:
            regime = "CONCENTRATED_OLIGOPOLY"
        elif hhi >= 1500 or cr3 >= 50.0:
            regime = "MODERATELY_CONCENTRATED"
        else:
            regime = "FRAGMENTED_COMMODITY"

        return {
            "hhi_score": hhi,
            "concentration_regime": regime,
            "cr3_pct": cr3,
            "top_player_share_pct": sorted_shares[0] if sorted_shares else 0.0,
            "confidence": "AUDITED_MARKET_SHARES"
        }

    @staticmethod
    def calculate_rigorous_hhi(
        identified_market_shares: Dict[str, float],
        n_unidentified_min: int = 1,
        n_unidentified_max: int = 10
    ) -> Dict[str, Any]:
        """
        Computes the Herfindahl-Hirschman Index with uncertainty bounds for residual unallocated shares:
        
        HHI_observed = sum_{i in identified} s_i^2 (on scale 0-10000, where s_i is in 0-100)
        Residual R = max(0, 100 - sum_{i in identified} s_i)
        HHI_min = HHI_observed + (R^2 / N_unidentified_max)
        HHI_max = HHI_observed + (R^2 / N_unidentified_min)
        """
        if not identified_market_shares:
            return {
                "hhi_observed": 1500.0,
                "hhi_min": 1500.0,
                "hhi_max": 1500.0,
                "identified_share_pct": 0.0,
                "residual_unidentified_share_pct": 100.0,
                "market_structure": "FRAGMENTED_COMMODITY"
            }

        shares = [max(0.0, min(100.0, float(v))) for v in identified_market_shares.values()]
        sum_identified = sum(shares)
        if sum_identified > 100.0:
            shares = [s * (100.0 / sum_identified) for s in shares]
            sum_identified = 100.0

        hhi_observed = round(sum(s ** 2 for s in shares), 2)
        residual = round(max(0.0, 100.0 - sum_identified), 2)

        n_min = max(1, n_unidentified_min)
        n_max = max(n_min, n_unidentified_max)

        hhi_min = round(hhi_observed + ((residual ** 2) / n_max), 2)
        hhi_max = round(hhi_observed + ((residual ** 2) / n_min), 2)

        # Structure classification on scale [0, 10000]
        if hhi_observed >= 2500.0 or (hhi_max >= 2500.0 and residual > 0):
            regime = "CONCENTRATED_OLIGOPOLY"
        elif hhi_observed >= 1500.0 or (hhi_max >= 1500.0 and residual > 0):
            regime = "MODERATELY_CONCENTRATED"
        else:
            regime = "FRAGMENTED_COMMODITY"

        return {
            "hhi_observed": hhi_observed,
            "hhi_min": hhi_min,
            "hhi_max": hhi_max,
            "identified_share_pct": round(sum_identified, 2),
            "residual_unidentified_share_pct": residual,
            "market_structure": regime
        }

    @staticmethod
    def calculate_pricing_power_index(
        historical_gross_margins_pct: List[float]
    ) -> Dict[str, Any]:
        """
        Evaluates Gross Margin stability across multi-year commodity cycles.
        
        Pricing Power = Ability to pass through input cost inflation without margin degradation.
        Low Standard Deviation (sigma_GM < 2.5%) = High Pricing Power.
        High Standard Deviation (sigma_GM > 6.0%) = Commodity Price Taker.
        """
        if not historical_gross_margins_pct or len(historical_gross_margins_pct) < 3:
            return {
                "pricing_power_score": 50.0,
                "pricing_power_rating": "MODERATE_OR_UNPROVEN",
                "gross_margin_mean_pct": 0.0,
                "gross_margin_std_dev": 0.0,
                "pricing_power_confidence": "LOW_INSUFFICIENT_HISTORY"
            }

        gm_list = [float(gm) for gm in historical_gross_margins_pct]
        mean_gm = round(statistics.mean(gm_list), 2)
        std_gm = round(statistics.stdev(gm_list), 2) if len(gm_list) > 1 else 0.0

        # Coefficient of variation in Gross Margin
        cv_gm = round((std_gm / max(1.0, mean_gm)) * 100.0, 2)

        # Pricing Power Score (0 to 100)
        # Bounded between 0% (high volatility) and 100% (ironclad stability)
        score = round(max(0.0, min(100.0, 100.0 - (cv_gm * 4.0))), 1)

        if std_gm <= 2.5 and mean_gm >= 25.0:
            rating = "IRONCLAD_PRICING_POWER"
            narrative = f"Superior pricing power: Gross Margin averaged {mean_gm}% with ultra-low volatility (+/-{std_gm}%), confirming seamless cost pass-through."
        elif std_gm <= 4.5:
            rating = "RESILIENT_PRICING_POWER"
            narrative = f"Resilient pricing power: Gross Margin averaged {mean_gm}% with moderate volatility (+/-{std_gm}%)."
        else:
            rating = "COMMODITY_PRICE_TAKER"
            narrative = f"Commodity price taker: High Gross Margin volatility (+/-{std_gm}%), vulnerable to input cost swings."

        return {
            "pricing_power_score": score,
            "pricing_power_rating": rating,
            "gross_margin_mean_pct": mean_gm,
            "gross_margin_std_dev": std_gm,
            "gross_margin_cv_pct": cv_gm,
            "pricing_power_narrative": narrative,
            "pricing_power_confidence": "HIGH_5Y_AUDITED" if len(gm_list) >= 5 else "MEDIUM_3Y_AUDITED"
        }

    @staticmethod
    def evaluate_displacement_dynamics(
        symbol: str,
        sector: str,
        company_revenue_growth_yoy_pct: float,
        industry_growth_yoy_pct: float = 12.0,
        unorganized_share_pct: float = 35.0
    ) -> Dict[str, Any]:
        """
        Classifies "Who loses when this company wins?"
        
        1. FORMALIZATION: Taking share from unorganized players (unorganized share > 25% and company growing > 2x industry).
        2. INCUMBENT_DISPLACEMENT: Taking share from established listed peers (growing faster in a mature market).
        3. SECULAR_NEW_MARKET: Creating an entirely new market / import substitution.
        """
        co_growth = max(0.0, company_revenue_growth_yoy_pct)
        ind_growth = max(1.0, industry_growth_yoy_pct)
        market_share_gain_velocity = round(co_growth - ind_growth, 2)

        sym = symbol.upper().strip()
        if sym in ("MANORAMA", "MANORAMA.NS"):
            displacement_mode = "SECULAR_IMPORT_SUBSTITUTION_AND_EXPORT"
            source_of_share = "Global cocoa butter replacement + domestic confectionery fats import substitution."
        elif sym in ("DIXON", "DIXON.NS", "KAYNES"):
            displacement_mode = "SECULAR_MAKE_IN_INDIA_PLI_SUBSTITUTION"
            source_of_share = "Displacing imported Chinese electronics modules via PLI scale economics."
        elif unorganized_share_pct >= 30.0 and market_share_gain_velocity > 10.0:
            displacement_mode = "UNORGANIZED_TO_ORGANIZED_FORMALIZATION"
            source_of_share = f"Capturing market share from the {unorganized_share_pct}% unorganized market segment."
        elif market_share_gain_velocity > 5.0:
            displacement_mode = "HIGH_COST_INCUMBENT_DISPLACEMENT"
            source_of_share = f"Outgrowing legacy incumbents by +{market_share_gain_velocity}% YoY through superior efficiency."
        else:
            displacement_mode = "INDUSTRY_BETA_EXPANSION"
            source_of_share = "Growing in-line with overall industry expansion."

        # Overall Economic Moat Rating
        if market_share_gain_velocity > 15.0:
            moat_rating = "WIDE_MOAT_SCALE_AND_EFFICIENCY"
        elif market_share_gain_velocity > 5.0:
            moat_rating = "NARROW_MOAT_NICHE_LEADERSHIP"
        else:
            moat_rating = "NO_DISCERNIBLE_MOAT"

        return {
            "displacement_mode": displacement_mode,
            "source_of_market_share": source_of_share,
            "market_share_gain_velocity_pct": market_share_gain_velocity,
            "economic_moat_rating": moat_rating,
            "industry_growth_baseline_pct": ind_growth,
            "unorganized_sector_share_pct": unorganized_share_pct
        }
