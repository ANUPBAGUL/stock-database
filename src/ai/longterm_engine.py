"""
Long-Term Investment Engine — Frozen Model M6 Quality Compounders (1-3 Years).

Evaluates structural business quality, capital efficiency (TTM ROCE), free cash flow,
solvency, and valuation margin of safety with zero lookahead bias.
"""

import logging
from datetime import date
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from src.analytics.feature_engine import FeatureEngine
from src.db.models import Company, DailyPriceRaw

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LongTermEngine:
    """
    Frozen Model M6 Institutional Engine for Multi-Year Compounders.
    Horizon: 1 to 3 Years.
    """
    MODEL_VERSION = "v2.0-m6-frozen-compounder"

    @staticmethod
    def evaluate_company(db: Session, company_id: str, as_of_date: date) -> Dict[str, Any]:
        feats = FeatureEngine.extract_features_as_of(db, company_id, as_of_date)

        comp = db.query(Company).filter_by(company_id=company_id).first()
        symbol = comp.nse_symbol if comp else "UNKNOWN"
        name = comp.company_name if comp else "Unknown Company"
        industry = comp.industry or "General Industry"

        roce = feats.get("roce_pct")
        rev_growth = feats.get("revenue_yoy_growth_pct") or 10.0
        pat_growth = feats.get("pat_yoy_growth_pct") or 10.0
        ebitda_margin = feats.get("ebitda_margin") or 15.0
        pat_margin = feats.get("pat_margin") or 8.0
        dte = feats.get("debt_to_equity")
        pe = feats.get("pe_ratio")
        pb = feats.get("pb_ratio")
        mcap = feats.get("market_cap_crores")
        fcf = feats.get("ttm_fcf") or 0.0
        fcf_yield = feats.get("fcf_yield_pct")  # Let FeatureEngine compute it correctly

        # ──────────────────────────────────────────────────────────────
        # Dimension 1: Capital Efficiency & Moat Score (0 - 100)
        # ──────────────────────────────────────────────────────────────
        if roce is not None and ebitda_margin is not None:
            roce_capped = min(45.0, max(0.0, roce))
            moat_score = int(min(98, max(25, 30.0 + (roce_capped * 1.1) + (min(30.0, ebitda_margin) * 0.6))))
        else:
            moat_score = None  # Cannot compute without ROCE or EBITDA margin

        # ──────────────────────────────────────────────────────────────
        # Dimension 2: Compounding Growth Consistency (0 - 100)
        # ──────────────────────────────────────────────────────────────
        growth_raw = 50.0 + (min(40.0, max(-20.0, rev_growth)) * 0.6) + (min(40.0, max(-20.0, pat_growth)) * 0.5)
        growth_score = int(min(98, max(20, growth_raw)))

        # ──────────────────────────────────────────────────────────────
        # Dimension 3: Balance Sheet & Solvency Safety (0 - 100)
        # ──────────────────────────────────────────────────────────────
        if dte is not None:
            solvency_raw = 85.0
            if dte > 2.0:
                solvency_raw -= 30
            elif dte > 1.0:
                solvency_raw -= 15
            elif dte < 0.3:
                solvency_raw += 10
            solvency_score = int(min(98, max(20, solvency_raw)))
        else:
            solvency_score = None  # Cannot compute without debt_to_equity

        # ──────────────────────────────────────────────────────────────
        # Dimension 4: Valuation Margin of Safety (0 - 100)
        # ──────────────────────────────────────────────────────────────
        if pe is not None and pe > 0:
            if pe < 15:
                val_score = 90
            elif pe < 25:
                val_score = 80
            elif pe < 40:
                val_score = 65
            elif pe < 65:
                val_score = 48
            else:
                val_score = 30
        else:
            val_score = 60

        # ──────────────────────────────────────────────────────────────
        # Composite Long-Term Conviction Score (Frozen M6 Formula)
        # ──────────────────────────────────────────────────────────────
        if moat_score is not None and growth_score is not None and solvency_score is not None:
            longterm_score = int(
                (moat_score * 0.35) +
                (growth_score * 0.25) +
                (solvency_score * 0.20) +
                (val_score * 0.20)
            )
            longterm_score = min(99, max(20, longterm_score))
        else:
            longterm_score = None  # Cannot compute composite score with missing sub-scores

        # Qualitative Grade
        if longterm_score is not None:
            if longterm_score >= 80:
                conviction_grade = "TIER_1_COMPOUNDER"
            elif longterm_score >= 65:
                conviction_grade = "HIGH_QUALITY_GROWTH"
            elif longterm_score >= 50:
                conviction_grade = "MODERATE_QUALITY"
            else:
                conviction_grade = "WATCHLIST_ONLY"
        else:
            conviction_grade = "DATA_INSUFFICIENT"

        # Key Drivers
        thesis_points = []
        if roce is not None:
            if roce >= 20.0:
                thesis_points.append(f"Exceptional capital efficiency (TTM ROCE: {roce:.1f}%)")
            elif roce >= 15.0:
                thesis_points.append(f"Healthy capital efficiency (TTM ROCE: {roce:.1f}%)")

        if fcf_yield is not None and fcf_yield >= 3.0:
            thesis_points.append(f"High Free Cash Flow conversion (FCF Yield: {fcf_yield:.1f}%)")

        if dte is not None and dte <= 0.5:
            thesis_points.append(f"Clean, low-leverage balance sheet (Debt/Equity: {dte:.2f})")

        if rev_growth >= 12.0:
            thesis_points.append(f"Consistent top-line compounding (YoY Revenue: {rev_growth:+.1f}%)")

        risk_points = []
        if pe and pe > 50.0:
            risk_points.append(f"Elevated valuation multiple (Trailing P/E: {pe:.1f})")
        if dte is not None and dte > 1.2:
            risk_points.append(f"Elevated financial leverage (Debt/Equity: {dte:.2f})")
        if pat_margin < 4.0:
            risk_points.append(f"Thin net profit margin ({pat_margin:.1f}%)")

        return {
            "company_id": company_id,
            "symbol": symbol,
            "company_name": name,
            "industry": industry,
            "horizon": "1-3 Years",
            "model_version": LongTermEngine.MODEL_VERSION,
            "as_of_date": as_of_date.isoformat(),
            "longterm_score": longterm_score,
            "conviction_grade": conviction_grade,
            "moat_score": moat_score,
            "growth_score": growth_score,
            "solvency_score": solvency_score,
            "valuation_score": val_score,
            "metrics": {
                "close_price": feats.get("close_price"),
                "ttm_roce_pct": roce,
                "ttm_fcf_yield_pct": fcf_yield,
                "trailing_pe": pe,
                "price_to_book": pb,
                "debt_to_equity": dte,
                "ebitda_margin_pct": ebitda_margin,
                "revenue_yoy_pct": rev_growth,
                "pat_yoy_pct": pat_growth,
                "market_cap_cr": mcap
            },
            "thesis_drivers": thesis_points if thesis_points else ["Stable financial baseline"],
            "risk_factors": risk_points if risk_points else ["Standard industry macro risks"]
        }
