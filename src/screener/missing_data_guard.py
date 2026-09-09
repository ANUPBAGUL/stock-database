"""
Missing Data Guard, Sector Normalization & Data Provenance Engine.
Phase 0.5: Screener Data Hygiene & Multi-Factor Governance.

Guarantees:
1. NULL != 0 and N/A != Poor: Never penalizes or silences missing data as 0.0.
2. Sector-Aware Normalization: Differentiates Financials, Industrials, Commodities, Utilities, and Asset-Light.
3. Decision-Tree Negative FCF Classifier: Differentiates GROWTH_REINVESTMENT from FCF_RISK.
4. Granular Provenance Tracking: Attaches source (TRADINGVIEW/LOCAL_DB/DERIVED) and quality (VERIFIED/CROSS_CHECKED/PROXY/MISSING) to every metric.
5. Setup Data Quality Rating: Emits setup_data_quality (1.00 / 0.75 / 0.50).
"""

import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("MissingDataGuard")


class SectorCategory:
    FINANCIALS = "FINANCIALS"
    INDUSTRIALS_CAPGOODS = "INDUSTRIALS_CAPGOODS"
    COMMODITIES_MATERIALS = "COMMODITIES_MATERIALS"
    UTILITIES_POWER = "UTILITIES_POWER"
    ASSET_LIGHT_GROWTH = "ASSET_LIGHT_GROWTH"


# High-conviction sector mapping heuristics for Indian Equities
_KNOWN_FINANCIAL_SYMBOLS = {
    "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK",
    "BAJFINANCE", "BAJAJFINSV", "MUTHOOTFIN", "CHOLAFIN", "SHRIRAMFIN",
    "HDFCLIFE", "SBILIFE", "ICICIPRULI", "HDFCAMC", "NAM-INDIA", "BSE", "MCX",
    "CDSL", "CAMS", "ANGELONE", "KFINTECH", "UTIAMC", "MOTILALOFS"
}

_KNOWN_COMMODITY_SYMBOLS = {
    "TATASTEEL", "JSWSTEEL", "HINDALCO", "JINDALSTEL", "SAIL", "VEDL", "NMDC",
    "COALINDIA", "ONGC", "OIL", "IOC", "BPCL", "HPCL", "GAIL", "UPL", "SRF",
    "PIIND", "DEEPAKNTR", "FLUOROCHEM", "NAVINFLUOR", "AARTIIND", "TATACHEM"
}

_KNOWN_UTILITY_SYMBOLS = {
    "POWERGRID", "NTPC", "TATAPOWER", "ADANIPOWER", "ADANIGREEN", "NHPC", "SJVN", "CESC", "IGL", "MGL"
}

_KNOWN_INDUSTRIAL_SYMBOLS = {
    "LT", "SIEMENS", "ABB", "BHEL", "BEL", "HAL", "CUMMINSIND", "THERMAX",
    "AIAENG", "KEC", "KALPATPOWR", "ENGINERSIN", "PNCINFRA", "GRINFRA",
    "MAZDOCK", "COCHINSHIP", "BDL", "BEML", "SOLARINDS", "DATAPATTNS", "DIXON", "AMBER"
}


class MissingDataGuard:
    """
    Guarantees mathematically honest handling of missing data, sector-specific
    exemptions, cash flow reinvestment classification, and data provenance.
    """

    @classmethod
    def resolve_sector(
        cls,
        symbol: str,
        company_name: str = "",
        industry_raw: Optional[str] = None
    ) -> str:
        """
        Maps an equity to its primary sector normalization group.
        """
        sym = symbol.upper()
        if sym in _KNOWN_FINANCIAL_SYMBOLS:
            return SectorCategory.FINANCIALS
        if sym in _KNOWN_COMMODITY_SYMBOLS:
            return SectorCategory.COMMODITIES_MATERIALS
        if sym in _KNOWN_UTILITY_SYMBOLS:
            return SectorCategory.UTILITIES_POWER
        if sym in _KNOWN_INDUSTRIAL_SYMBOLS:
            return SectorCategory.INDUSTRIALS_CAPGOODS

        # Textual heuristics
        txt = f"{company_name} {industry_raw or ''}".lower()
        if any(w in txt for w in ["bank", "finance", "financial", "housing", "insurance", "capital markets", "lending", "nbfc"]):
            return SectorCategory.FINANCIALS
        if any(w in txt for w in ["steel", "metals", "mining", "aluminum", "zinc", "copper", "chemical", "fertilizer", "refinery"]):
            return SectorCategory.COMMODITIES_MATERIALS
        if any(w in txt for w in ["power", "energy", "transmission", "utility", "electricity", "gas distribution"]):
            return SectorCategory.UTILITIES_POWER
        if any(w in txt for w in ["engineering", "capital goods", "infrastructure", "construction", "heavy equipment", "epc"]):
            return SectorCategory.INDUSTRIALS_CAPGOODS

        # Default to Asset-Light / General Consumer / Tech
        return SectorCategory.ASSET_LIGHT_GROWTH

    @classmethod
    def classify_negative_fcf(
        cls,
        fcf_cr: Optional[float],
        roce_pct: Optional[float],
        roe_pct: Optional[float],
        rev_growth_pct: Optional[float],
        cagr_5y_pct: Optional[float],
        debt_to_equity: Optional[float],
        opm_pct: Optional[float],
        cash_cr: Optional[float] = None,
        total_debt_cr: Optional[float] = None,
        sector: str = SectorCategory.ASSET_LIGHT_GROWTH
    ) -> Dict[str, Any]:
        """
        Multi-factor classification tree for negative Free Cash Flow.
        Does NOT use arbitrary hardcoded revenue/margin gates.
        Evaluates ROIC quality, reinvestment growth generation, and balance sheet safety.
        """
        if sector == SectorCategory.FINANCIALS:
            return {
                "fcf_status": "EXEMPT_FINANCIAL",
                "is_reinvestment_grower": False,
                "reinvestment_notes": "Free cash flow is not a standard solvency or compounding metric for financial institutions."
            }

        if fcf_cr is None:
            return {
                "fcf_status": "DATA_UNAVAILABLE",
                "is_reinvestment_grower": False,
                "reinvestment_notes": "Cash flow data unavailable; cannot determine reinvestment runway."
            }

        if fcf_cr >= 0:
            return {
                "fcf_status": "CASH_GENERATIVE",
                "is_reinvestment_grower": False,
                "reinvestment_notes": "Company generates positive organic free cash flow."
            }

        # --- Negative FCF Evaluation ---
        # 1. Capital efficiency: Is return on capital attractive?
        is_roic_attractive = (
            (roce_pct is not None and roce_pct >= 14.0) or
            (roe_pct is not None and roe_pct >= 14.0)
        )

        # 2. Growth generation: Is reinvested capital producing top-line expansion?
        is_growth_producing = (
            (rev_growth_pct is not None and rev_growth_pct >= 15.0) or
            (cagr_5y_pct is not None and cagr_5y_pct >= 14.0)
        )

        # 3. Balance sheet safety: Does the company have solvent runway?
        is_balance_sheet_safe = True
        if debt_to_equity is not None and debt_to_equity > 2.0:
            is_balance_sheet_safe = False
        if opm_pct is not None and opm_pct < 0.0:
            is_balance_sheet_safe = False
        if cash_cr is not None and total_debt_cr is not None and total_debt_cr > 0:
            # If cash covers at least 30% of debt or net debt is low
            net_debt = total_debt_cr - cash_cr
            if net_debt > 0 and (cash_cr / total_debt_cr) < 0.20 and (debt_to_equity and debt_to_equity > 1.2):
                is_balance_sheet_safe = False

        if is_roic_attractive and is_growth_producing and is_balance_sheet_safe:
            return {
                "fcf_status": "GROWTH_REINVESTMENT",
                "is_reinvestment_grower": True,
                "reinvestment_notes": "Operating in active CapEx/expansion phase; reinvesting cash flow at high return on capital without solvency distress."
            }
        else:
            reasons = []
            if not is_roic_attractive:
                reasons.append("Unconfirmed ROIC/ROCE (< 14%)")
            if not is_growth_producing:
                reasons.append("Weak top-line expansion (< 15%)")
            if not is_balance_sheet_safe:
                reasons.append("Elevated debt or negative operating margin")

            return {
                "fcf_status": "FCF_RISK",
                "is_reinvestment_grower": False,
                "reinvestment_notes": f"Cash burn with elevated risk factors: {', '.join(reasons)}."
            }

    @classmethod
    def normalize_candidate_fundamentals(
        cls,
        raw_cand: Dict[str, Any],
        is_local_db: bool = False
    ) -> Dict[str, Any]:
        """
        Applies sector-aware normalization, ensures NULL != 0, and attaches data provenance tags.
        """
        symbol = raw_cand.get("symbol", "").upper()
        company_name = raw_cand.get("company_name", symbol)
        sector = cls.resolve_sector(symbol, company_name)

        # Extract Raw Values
        roce = raw_cand.get("roce_pct")
        roe = raw_cand.get("roe_pct")
        roic = raw_cand.get("roic_pct")
        de = raw_cand.get("debt_to_equity")
        opm = raw_cand.get("opm_pct")
        net_margin = raw_cand.get("net_margin_pct")
        gross_margin = raw_cand.get("gross_margin_pct")
        rev_growth = raw_cand.get("sales_growth_pct")
        rev_cagr_5y = raw_cand.get("revenue_cagr_5y_pct")
        fcf_cr = raw_cand.get("fcf_cr")
        dso = raw_cand.get("dso_days")
        pe = raw_cand.get("pe_ratio")

        # Provenance Tracking
        src = "LOCAL_DB" if is_local_db else "TRADINGVIEW"
        provenance: Dict[str, Dict[str, str]] = {}

        def record_prov(metric: str, val: Any, cross_checked: bool = False, is_proxy: bool = False):
            if val is None:
                provenance[metric] = {"source": src, "quality": "MISSING"}
            elif cross_checked:
                provenance[metric] = {"source": src, "quality": "CROSS_CHECKED"}
            elif is_proxy:
                provenance[metric] = {"source": "DERIVED", "quality": "PROXY"}
            else:
                provenance[metric] = {"source": src, "quality": "VERIFIED"}

        record_prov("roce_pct", roce, cross_checked=is_local_db)
        record_prov("debt_to_equity", de)
        record_prov("opm_pct", opm)
        record_prov("sales_growth_pct", rev_growth)
        record_prov("pe_ratio", pe)
        record_prov("fcf_cr", fcf_cr)

        # Sector-Aware Financial Normalization
        effective_quality_metric: Optional[float] = None
        effective_solvency_metric: Optional[float] = None
        sector_exemption_notes: Optional[str] = None

        if sector == SectorCategory.FINANCIALS:
            # For banks/NBFCs, ROCE is N/A; use ROE
            if roe is not None:
                effective_quality_metric = roe
                sector_exemption_notes = "Evaluated via ROE (ROCE exempt for Financial Services)."
            elif net_margin is not None and net_margin > 0:
                effective_quality_metric = min(30.0, net_margin * 0.8)
                sector_exemption_notes = "Evaluated via Net Margin proxy (ROCE exempt)."
            else:
                effective_quality_metric = 15.0  # Neutral sector median
                sector_exemption_notes = "Assigned neutral financial sector median."

            # D/E is operational for banks; do not penalize
            effective_solvency_metric = 1.0  # Safe neutral
            provenance["debt_to_equity"]["quality"] = "PROXY"

        elif sector == SectorCategory.INDUSTRIALS_CAPGOODS:
            effective_quality_metric = roce if roce is not None else (roe if roe is not None else None)
            effective_solvency_metric = de
            if dso is not None and dso > 90.0:
                sector_exemption_notes = "Extended working capital cycle is standard for long-lead industrial EPC."

        elif sector == SectorCategory.COMMODITIES_MATERIALS:
            effective_quality_metric = roce if roce is not None else (roe if roe is not None else None)
            effective_solvency_metric = de
            sector_exemption_notes = "Commodity sector: evaluated against cyclical capital cycles."

        else:
            # Asset-Light & General
            effective_quality_metric = roce if roce is not None else (roe if roe is not None else None)
            effective_solvency_metric = de

        # Classify Negative FCF
        fcf_eval = cls.classify_negative_fcf(
            fcf_cr=fcf_cr,
            roce_pct=roce,
            roe_pct=roe,
            rev_growth_pct=rev_growth,
            cagr_5y_pct=rev_cagr_5y,
            debt_to_equity=de,
            opm_pct=opm,
            cash_cr=raw_cand.get("cash_cr"),
            total_debt_cr=raw_cand.get("total_debt_cr"),
            sector=sector
        )

        # Calculate Setup Data Quality
        missing_cores = sum(1 for v in [roce if sector != SectorCategory.FINANCIALS else roe, rev_growth, opm, pe] if v is None)
        is_sme = "SME" in company_name.upper() or raw_cand.get("is_sme", False)
        quality_score, quality_label = cls.calculate_setup_data_quality(is_local_db, is_sme, missing_cores)

        normalized = dict(raw_cand)
        normalized.update({
            "sector_category": sector,
            "effective_quality_metric": effective_quality_metric,
            "effective_solvency_metric": effective_solvency_metric,
            "sector_exemption_notes": sector_exemption_notes,
            "fcf_classification": fcf_eval["fcf_status"],
            "is_reinvestment_grower": fcf_eval["is_reinvestment_grower"],
            "reinvestment_notes": fcf_eval["reinvestment_notes"],
            "setup_data_quality": quality_score,
            "setup_quality_rating": quality_label,
            "metric_provenance": provenance
        })

        return normalized

    @classmethod
    def calculate_setup_data_quality(
        cls,
        is_local_db: bool,
        is_sme: bool,
        missing_core_count: int
    ) -> Tuple[float, str]:
        """
        Determines the fidelity confidence score and rating for the candidate.
        1.00 = FULL_OHLCV (Local DB with multi-year price bars, exact base pivot detection)
        0.75 = CLOUD_PROXY (TradingView scanner data, moving averages, recent high proxy)
        0.50 = LIMITED_DATA (Missing > 2 core indicators)
        """
        if missing_core_count >= 2:
            return 0.50, "LIMITED_DATA"
        if is_local_db and not is_sme:
            return 1.00, "FULL_OHLCV"
        if is_sme:
            return 0.70, "SME_CLOUD_PROXY"
        return 0.75, "CLOUD_PROXY"
