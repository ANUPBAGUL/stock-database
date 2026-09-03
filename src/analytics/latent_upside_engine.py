"""
Latent Upside Map ("Distance to Excellence") Engine.
Models the latent power of operating leverage by evaluating what earnings and market cap
the company would generate if its capacity utilization, operating margins, and asset turnover
reach industry top-quartile excellence benchmarks.
"""
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class LatentUpsideEngine:
    """
    Computes the Latent Operational Upside and Distance to Excellence Map.
    """

    @staticmethod
    def calculate_latent_upside_map(
        current_revenue_cr: float,
        current_ebit_cr: float,
        current_pat_cr: float,
        current_market_cap_cr: float,
        current_roce_pct: float,
        current_capacity_utilization_pct: float = 65.0,
        sector_top_quartile_opm_pct: float = 16.0,
        sector_top_quartile_roce_pct: float = 28.0,
        benchmark_target_utilization_pct: float = 85.0,
        tax_rate_pct: float = 25.0
    ) -> Dict[str, Any]:
        """
        Simulates the Operational Leverage and Multiple Expansion to Top-Quartile Excellence:
        
        1. Capacity Expansion Factor = Benchmark Utilization (85%) / Current Utilization (e.g. 65%)
        2. Potential Revenue at Excellence = Current Revenue * Capacity Factor
        3. Potential EBIT = Potential Revenue * max(Current OPM, Sector Top-Quartile OPM)
        4. Potential PAT = Potential EBIT * (1 - Tax Rate)
        5. Operational Leverage Multiplier = Potential PAT / Current PAT
        """
        curr_rev = max(1.0, current_revenue_cr)
        curr_ebit = max(0.1, current_ebit_cr)
        curr_pat = max(0.1, current_pat_cr)
        curr_mcap = max(1.0, current_market_cap_cr)
        tax_rate = max(0.10, min(0.35, tax_rate_pct / 100.0 if tax_rate_pct > 1.0 else tax_rate_pct))

        curr_opm = round((curr_ebit / curr_rev) * 100.0, 2)
        curr_util = max(30.0, min(95.0, current_capacity_utilization_pct))
        target_util = max(curr_util, min(95.0, benchmark_target_utilization_pct))

        # 1. Volume Capacity Scaling Factor
        utilization_factor = round(target_util / curr_util, 2)
        potential_revenue = round(curr_rev * utilization_factor, 2)

        # 2. Operating Margin Expansion at Scale
        target_opm = max(curr_opm, sector_top_quartile_opm_pct)
        opm_expansion_bps = round((target_opm - curr_opm) * 100.0, 0)

        # 3. Potential Earnings Under Excellence
        potential_ebit = round(potential_revenue * (target_opm / 100.0), 2)
        potential_pat = round(potential_ebit * (1.0 - tax_rate), 2)

        # 4. Multipliers
        operational_leverage_multiplier = round(potential_pat / curr_pat, 2)
        roce_gap_pct = max(0.0, round(sector_top_quartile_roce_pct - current_roce_pct, 2))

        # 5. Distance to Excellence Score (0 = Already at Top Quartile, 100 = Massive Untapped Operating Gap)
        distance_score = round(min(100.0, (roce_gap_pct * 2.0) + (opm_expansion_bps / 50.0) + ((utilization_factor - 1.0) * 100.0)), 1)

        # Classify Latent Compounding Profile
        if operational_leverage_multiplier >= 2.0:
            profile = "EXPLOSIVE_LATENT_OPERATIONAL_LEVERAGE"
            narrative = f"Massive latent capacity: {operational_leverage_multiplier}x PAT expansion achievable at {target_util}% utilization & {target_opm}% OPM without equity dilution."
        elif operational_leverage_multiplier >= 1.4:
            profile = "HEALTHY_OPERATIONAL_RUNWAY"
            narrative = f"Significant operating runway: {operational_leverage_multiplier}x PAT expansion achievable via margin expansion (+{round(opm_expansion_bps/100, 1)}% OPM)."
        else:
            profile = "NEAR_PEAK_OPERATIONAL_EFFICIENCY"
            narrative = "Operating near peak efficiency; further growth requires greenfield CapEx or new product lines."

        return {
            "current_opm_pct": curr_opm,
            "target_excellence_opm_pct": target_opm,
            "opm_expansion_latent_bps": opm_expansion_bps,
            "current_capacity_utilization_pct": curr_util,
            "target_capacity_utilization_pct": target_util,
            "potential_revenue_at_excellence_cr": potential_revenue,
            "potential_pat_at_excellence_cr": potential_pat,
            "operational_leverage_multiplier": operational_leverage_multiplier,
            "distance_to_excellence_score": distance_score,
            "roce_gap_to_excellence_pct": roce_gap_pct,
            "latent_profile": profile,
            "latent_narrative": narrative,
            "evidence_source": "SECTOR_75TH_PERCENTILE_BENCHMARK",
            "evidence_confidence": "HIGH_GROUNDED" if target_opm <= (curr_opm * 1.5) else "MEDIUM_STRETCH"
        }
