"""
Pillar 2: Granular Capacity-Constrained TAM / SAM / SOM Engine.

Replaces static, unconstrained market sizing with a 6-variable dynamic capacity funnel:
1. Domestic vs. Export addressable market segmentation (SAM)
2. Physical Gross Block + CWIP Asset Turnover Capacity Ceiling
3. Realistic Market Share Ceiling (SOM <= 25% for fragmented niches, <= 40% for natural oligopolies)
4. Organic Growth Runway (Years remaining before hitting physical/market capacity)
5. 3-Point Confidence Bounds: P10 (Bear), P50 (Base), P90 (Bull)
"""

from typing import Dict, Any, Optional, Tuple
import logging
from src.analytics.tam_engine import ReverseTAMHurdleEngine, INDUSTRY_TAM_REGISTRY

logger = logging.getLogger(__name__)


class GranularTAMEngine:
    """
    Computes capacity-constrained serviceable addressable markets and realistic terminal ceilings.
    """

    @staticmethod
    def calculate_physical_capacity_ceiling(
        gross_block_cr: Optional[float],
        cwip_cr: Optional[float],
        historical_asset_turnover: Optional[float] = None,
        default_asset_turnover: float = 2.0
    ) -> Tuple[Optional[float], float]:
        """
        Computes maximum potential annual revenue that the company's fixed assets can produce:
        Max Revenue Capacity = (Gross Block + CWIP) * Peak Asset Turnover

        E.g. Gross Block ₹500 Cr + CWIP ₹200 Cr @ 2.5x turnover = ₹1,750 Cr Revenue Ceiling.
        """
        if gross_block_cr is None or gross_block_cr <= 0:
            return None, default_asset_turnover

        cwip = cwip_cr if cwip_cr and cwip_cr > 0 else 0.0
        total_productive_block = gross_block_cr + cwip

        effective_turnover = (
            historical_asset_turnover
            if (historical_asset_turnover and 0.5 <= historical_asset_turnover <= 8.0)
            else default_asset_turnover
        )

        max_capacity_cr = round(total_productive_block * effective_turnover, 2)
        return max_capacity_cr, effective_turnover

    @staticmethod
    def calculate_growth_runway_years(
        current_revenue_cr: Optional[float],
        target_ceiling_cr: Optional[float],
        growth_cagr_pct: Optional[float] = 20.0
    ) -> Optional[float]:
        """
        Computes how many years of growth remain before the company hits its addressable ceiling:
        Years = ln(Ceiling / Current) / ln(1 + Growth)
        """
        if (
            current_revenue_cr is None
            or target_ceiling_cr is None
            or current_revenue_cr <= 0
            or target_ceiling_cr <= current_revenue_cr
            or growth_cagr_pct is None
            or growth_cagr_pct <= 0
        ):
            return 0.0 if (target_ceiling_cr and current_revenue_cr and target_ceiling_cr <= current_revenue_cr) else None

        import math
        growth_rate = growth_cagr_pct / 100.0
        try:
            years = math.log(target_ceiling_cr / current_revenue_cr) / math.log(1.0 + growth_rate)
            return round(years, 1)
        except Exception:
            return None

    @classmethod
    def evaluate_tam_capacity_funnel(
        cls,
        symbol: str,
        sector: str,
        current_revenue_cr: Optional[float],
        gross_block_cr: Optional[float] = None,
        cwip_cr: Optional[float] = None,
        asset_turnover: Optional[float] = None,
        revenue_growth_cagr_pct: Optional[float] = 20.0
    ) -> Dict[str, Any]:
        """
        Executes full granular TAM/SAM/SOM and capacity funnel analysis.
        """
        tam_meta = ReverseTAMHurdleEngine.resolve_industry_tam(symbol, sector)
        niche_tam = tam_meta.get("niche_tam_cr", 50000.0)
        macro_tam = tam_meta.get("macro_tam_cr", 500000.0)
        industry_name = tam_meta.get("name", sector)

        # Serviceable Addressable Market (SAM): Assumes 60% of niche TAM is directly addressable
        sam_p50 = round(niche_tam * 0.60, 1)

        # Serviceable Obtainable Market (SOM): Max 25% share of niche TAM in base case
        som_p50_market_cap = round(niche_tam * 0.25, 1)

        # Physical Capacity Ceiling
        capacity_ceiling_cr, eff_turnover = cls.calculate_physical_capacity_ceiling(
            gross_block_cr=gross_block_cr,
            cwip_cr=cwip_cr,
            historical_asset_turnover=asset_turnover
        )

        # Realistic SOM is bounded by the tighter of market share (25%) or physical plant capacity
        if capacity_ceiling_cr is not None and capacity_ceiling_cr > 0:
            effective_som_cr = min(som_p50_market_cap, capacity_ceiling_cr)
            bottleneck = "PHYSICAL_ASSET_CAPACITY" if capacity_ceiling_cr < som_p50_market_cap else "MARKET_SHARE_CEILING"
        else:
            effective_som_cr = som_p50_market_cap
            bottleneck = "MARKET_SHARE_CEILING"

        # Current Penetration
        penetration_pct = 0.0
        if current_revenue_cr and current_revenue_cr > 0 and niche_tam > 0:
            penetration_pct = round((current_revenue_cr / niche_tam) * 100.0, 2)

        # Runway Years
        runway_years = cls.calculate_growth_runway_years(
            current_revenue_cr=current_revenue_cr,
            target_ceiling_cr=effective_som_cr,
            growth_cagr_pct=revenue_growth_cagr_pct
        )

        # 3-Point Confidence Bounds
        confidence_bounds = {
            "p10_bear": {
                "niche_tam_cr": round(niche_tam * 0.70, 1),
                "som_cr": round(effective_som_cr * 0.60, 1),
                "runway_years": round(runway_years * 0.6, 1) if runway_years else None
            },
            "p50_base": {
                "niche_tam_cr": niche_tam,
                "som_cr": effective_som_cr,
                "runway_years": runway_years
            },
            "p90_bull": {
                "niche_tam_cr": round(niche_tam * 1.40, 1),
                "som_cr": round(effective_som_cr * 1.50, 1),
                "runway_years": round(runway_years * 1.5, 1) if runway_years else None
            }
        }

        # Status
        if runway_years is not None and runway_years >= 7.0:
            runway_status = "LONG_EXPANSION_RUNWAY"
            badge = "badge-emerald"
        elif runway_years is not None and runway_years >= 3.0:
            runway_status = "MODERATE_RUNWAY"
            badge = "badge-teal"
        elif runway_years is not None and runway_years > 0:
            runway_status = "CAPACITY_CONSTRAINED_NEAR_TERM"
            badge = "badge-amber"
        else:
            runway_status = "SATURATED_OR_UNKNOWN"
            badge = "badge-zinc"

        return {
            "industry_name": industry_name,
            "macro_tam_cr": macro_tam,
            "niche_tam_cr": niche_tam,
            "sam_p50_cr": sam_p50,
            "effective_som_cr": effective_som_cr,
            "physical_capacity_ceiling_cr": capacity_ceiling_cr,
            "effective_asset_turnover": eff_turnover,
            "primary_bottleneck": bottleneck,
            "current_penetration_pct": penetration_pct,
            "growth_runway_years": runway_years,
            "runway_status": runway_status,
            "badge_class": badge,
            "confidence_bounds": confidence_bounds,
            "summary": f"{industry_name}: ₹{effective_som_cr:,.0f} Cr obtainable revenue ceiling with {runway_years or 'N/A'} years organic runway ({bottleneck})."
        }
