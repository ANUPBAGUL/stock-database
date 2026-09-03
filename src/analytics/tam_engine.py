"""
Hierarchical Reverse-Engineered 10x TAM Hurdle Engine (Expectations Investing / Mauboussin Framework).
Solves for the exact market share, revenue, and NOPAT required to justify a 10x market cap realization,
distinguishing direct sub-niche TAM from broad macro industry TAM.
"""
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Curated Indian Industry & Sub-Niche TAM Database (in ₹ Crores)
INDUSTRY_TAM_REGISTRY = {
    # Specialty Chemicals & Confectionery Fats
    "SPECIALTY_FATS_CBE": {"niche_tam_cr": 25000.0, "macro_tam_cr": 120000.0, "name": "Cocoa Butter Equivalent & Specialty Fats"},
    "ELECTRONICS_MANUFACTURING_EMS": {"niche_tam_cr": 150000.0, "macro_tam_cr": 800000.0, "name": "Electronics Manufacturing Services (EMS)"},
    "IT_SERVICES_GLOBAL": {"niche_tam_cr": 500000.0, "macro_tam_cr": 12000000.0, "name": "Global IT & Digital Transformation Services"},
    "PHARMACEUTICALS_CRAMS_CDMO": {"niche_tam_cr": 60000.0, "macro_tam_cr": 350000.0, "name": "Custom Synthesis & CDMO Pharma"},
    "DEFENSE_AEROSPACE_INDIGENOUS": {"niche_tam_cr": 45000.0, "macro_tam_cr": 180000.0, "name": "Indian Indigenous Defense Components"},
    "RENEWABLE_SOLAR_COMPONENTS": {"niche_tam_cr": 80000.0, "macro_tam_cr": 400000.0, "name": "Solar Modules & Inverters"},
    "CONSUMER_QUICK_SERVICE_RESTAURANTS": {"niche_tam_cr": 35000.0, "macro_tam_cr": 250000.0, "name": "Organized QSR Chains"},
    "AUTO_ANCILLARY_EV_POWERTRAIN": {"niche_tam_cr": 40000.0, "macro_tam_cr": 300000.0, "name": "EV Powertrain & Thermal Systems"},
    "GENERAL_MANUFACTURING": {"niche_tam_cr": 50000.0, "macro_tam_cr": 500000.0, "name": "General Midcap Manufacturing"},
}

class ReverseTAMHurdleEngine:
    """
    Reverse-engineers the terminal economics required to generate a 10x return,
    checking if the required market share is mathematically plausible within the industry TAM.
    """

    @staticmethod
    def resolve_industry_tam(symbol: str, sector: str = "General") -> Dict[str, Any]:
        """
        Maps a company to its specific sub-niche TAM and macro sector TAM.
        """
        sym = symbol.upper().strip()
        if sym in ("MANORAMA", "MANORAMA.NS"):
            return INDUSTRY_TAM_REGISTRY["SPECIALTY_FATS_CBE"]
        elif sym in ("DIXON", "DIXON.NS", "AMBER", "KAYNES", "SYRMA"):
            return INDUSTRY_TAM_REGISTRY["ELECTRONICS_MANUFACTURING_EMS"]
        elif sym in ("TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"):
            return INDUSTRY_TAM_REGISTRY["IT_SERVICES_GLOBAL"]
        elif sym in ("DIVISLAB", "SUVENPHAR", "SYNGENE", "LAURUSLABS"):
            return INDUSTRY_TAM_REGISTRY["PHARMACEUTICALS_CRAMS_CDMO"]
        elif sym in ("SOLARINDS", "DATAPATTNS", "MTARTECH", "PARAS"):
            return INDUSTRY_TAM_REGISTRY["DEFENSE_AEROSPACE_INDIGENOUS"]
        
        # Sector fallback
        sec_upper = (sector or "").upper()
        if "TECH" in sec_upper or "IT" in sec_upper:
            return INDUSTRY_TAM_REGISTRY["IT_SERVICES_GLOBAL"]
        elif "PHARMA" in sec_upper:
            return INDUSTRY_TAM_REGISTRY["PHARMACEUTICALS_CRAMS_CDMO"]
        elif "ELECTRONIC" in sec_upper:
            return INDUSTRY_TAM_REGISTRY["ELECTRONICS_MANUFACTURING_EMS"]
        
        return INDUSTRY_TAM_REGISTRY["GENERAL_MANUFACTURING"]

    @staticmethod
    def evaluate_10x_reverse_hurdle(
        current_market_cap_cr: float,
        current_revenue_cr: float,
        current_pat_cr: float,
        industry_niche_tam_cr: float,
        industry_macro_tam_cr: float,
        terminal_pe_multiple: float = 28.0,
        terminal_net_margin_pct: float = 12.0,
    ) -> Dict[str, Any]:
        """
        Solves the Reverse DCF / TAM Equation for 10x Realization:
        
        1. Target 10x Market Cap = 10 * Current Market Cap
        2. Required 10x PAT = Target 10x Market Cap / Terminal PE
        3. Required 10x Revenue = Required 10x PAT / Terminal Net Margin
        4. Required Niche Market Share = Required 10x Revenue / Niche TAM
        5. Required Macro Market Share = Required 10x Revenue / Macro TAM
        """
        curr_mcap = max(10.0, current_market_cap_cr)
        target_10x_mcap = round(curr_mcap * 10.0, 2)

        # Terminal economics solve
        term_pe = max(10.0, terminal_pe_multiple)
        term_margin = max(0.02, min(0.35, terminal_net_margin_pct / 100.0 if terminal_net_margin_pct > 1.0 else terminal_net_margin_pct))

        required_pat = round(target_10x_mcap / term_pe, 2)
        required_revenue = round(required_pat / term_margin, 2)

        # Market share calculations
        niche_tam = max(100.0, industry_niche_tam_cr)
        macro_tam = max(niche_tam, industry_macro_tam_cr)

        req_niche_share_pct = round((required_revenue / niche_tam) * 100.0, 2)
        req_macro_share_pct = round((required_revenue / macro_tam) * 100.0, 2)
        curr_niche_share_pct = round((current_revenue_cr / niche_tam) * 100.0, 2) if current_revenue_cr else 0.0

        # Mathematical Feasibility Classification
        if req_niche_share_pct <= 15.0:
            feasibility = "HIGH_FEASIBILITY_RUNWAY"
            narrative = f"10x outcome requires capturing {req_niche_share_pct}% of niche TAM ({req_macro_share_pct}% of macro TAM). Massive headroom."
            is_10x_plausible = True
        elif req_niche_share_pct <= 35.0:
            feasibility = "STRETCH_TARGET"
            narrative = f"10x outcome requires capturing {req_niche_share_pct}% of niche TAM. Achievable only if becoming dominant market leader."
            is_10x_plausible = True
        elif req_macro_share_pct <= 15.0:
            feasibility = "REQUIRES_ADJACENT_EXPANSION"
            narrative = f"Niche TAM is too small ({req_niche_share_pct}% required), but requires capturing {req_macro_share_pct}% of broader macro market."
            is_10x_plausible = True
        else:
            feasibility = "MATHEMATICALLY_ABSURD"
            narrative = f"10x outcome requires {req_niche_share_pct}% niche share and {req_macro_share_pct}% macro share. Scale exceeds industry ceiling."
            is_10x_plausible = False

        return {
            "current_market_cap_cr": curr_mcap,
            "target_10x_market_cap_cr": target_10x_mcap,
            "required_10x_pat_cr": required_pat,
            "required_10x_revenue_cr": required_revenue,
            "niche_tam_cr": niche_tam,
            "macro_tam_cr": macro_tam,
            "current_niche_market_share_pct": curr_niche_share_pct,
            "required_niche_market_share_pct": req_niche_share_pct,
            "required_macro_market_share_pct": req_macro_share_pct,
            "terminal_pe_assumed": term_pe,
            "terminal_net_margin_assumed_pct": round(term_margin * 100.0, 1),
            "feasibility": feasibility,
            "is_10x_plausible": is_10x_plausible,
            "narrative": narrative
        }
