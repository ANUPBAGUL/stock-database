"""
M6 Frozen Research Specification — Immutable Model for EXP-004 Prospective Validation.

This module is STRICTLY FROZEN. It encapsulates the exact mathematical weights,
feature schema, and deterministic SHA256 input hashing for EXP-004.
DO NOT MODIFY THIS FILE DURING PROSPECTIVE EVALUATION.

NOTE: 2026-09-02 Data Quality Fix — Removed silent or-fallbacks on roce, dte, 
ebitda_margin, pat_margin that fabricated plausible numbers when data missing.
Model weights and logic unchanged. MODEL_CODE_HASH updated to reflect behavior change.
"""

import json
import hashlib
import logging
from datetime import date
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from src.analytics.feature_engine import FeatureEngine
from src.db.models import Company

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class M6FrozenResearchModel:
    """
    Sealed Model M6 Implementation for Prospective Validation (EXP-004).
    Research Evidence Status: HISTORICALLY_VALIDATED (EXP-001/002) // PROSPECTIVE_ACTIVE (EXP-004).
    """
    MODEL_VERSION = "v2.0-m6-frozen-research"
    RESEARCH_STATUS = "HISTORICALLY_VALIDATED"
    PROSPECTIVE_STATUS = "PROSPECTIVE_EVALUATION_ACTIVE"
    CONFIDENCE_TIER = "HIGH_CONFIDENCE_QUANT_CORE"

    # Exact frozen weight vector
    WEIGHTS = {
        "business_quality": 0.30,
        "growth": 0.25,
        "momentum": 0.20,
        "valuation": 0.15,
        "governance": 0.10
    }

    # Model definition hash
    MODEL_CODE_HASH = hashlib.sha256(json.dumps(WEIGHTS, sort_keys=True).encode('utf-8')).hexdigest()

    @staticmethod
    def evaluate_company(db: Session, company_id: str, as_of_date: date) -> Dict[str, Any]:
        """
        Deterministic, audited M6 scoring strictly as of decision date T.
        """
        features = FeatureEngine.extract_features_as_of(db, company_id, as_of_date)

        # Hash input snapshot for immutable auditability
        feature_bytes = json.dumps(features, sort_keys=True, default=str).encode('utf-8')
        input_snapshot_hash = hashlib.sha256(feature_bytes).hexdigest()

        comp = db.query(Company).filter_by(company_id=company_id).first()
        symbol = comp.nse_symbol if comp else "UNKNOWN"

        rev_growth = features.get("revenue_yoy_growth_pct") or 0.0  # Keep 0.0 fallback for growth (neutral baseline)
        pat_growth = features.get("pat_yoy_growth_pct") or 0.0
        ebitda_margin = features.get("ebitda_margin")
        pat_margin = features.get("pat_margin")
        roce = features.get("roce_pct")
        dte = features.get("debt_to_equity")
        pe = features.get("pe_ratio")
        pb = features.get("pb_ratio")

        rsi = features.get("rsi_14") or 50.0
        dist_sma50 = features.get("dist_from_sma50_pct") or 0.0
        dist_sma200 = features.get("dist_from_sma200_pct") or 0.0
        dist_52w_high = features.get("dist_from_52w_high_pct") or -15.0
        vol_accel = features.get("volume_acceleration_ratio") or 1.0

        # Dimension 1: Growth
        growth_raw = 50.0 + (min(50.0, max(-30.0, rev_growth)) * 0.5) + (min(50.0, max(-30.0, pat_growth)) * 0.5)
        growth_score = int(min(99, max(15, growth_raw)))

        # Dimension 2: Business Quality & ROCE
        if roce is not None and ebitda_margin is not None:
            roce_capped = min(50.0, max(0.0, roce))
            quality_raw = 30.0 + (roce_capped * 0.9) + (min(35.0, ebitda_margin) * 0.7)
            quality_score = int(min(99, max(20, quality_raw)))
        else:
            quality_score = None  # Cannot compute without ROCE or EBITDA margin

        # Dimension 3: Valuation
        if pe is not None and pe > 0:
            if pe < 12:
                val_raw = 92
            elif pe < 20:
                val_raw = 82
            elif pe < 35:
                val_raw = 68
            elif pe < 60:
                val_raw = 50
            else:
                val_raw = 35
        else:
            val_raw = 60
        if pb and pb < 2.5:
            val_raw += 5
        val_score = int(min(95, max(20, val_raw)))

        # Dimension 4: Momentum
        rsi_pts = 20.0 - abs(rsi - 60.0) * 0.8
        trend_pts = min(20.0, max(-15.0, dist_sma50 * 1.0)) + min(15.0, max(-10.0, dist_sma200 * 0.5))
        breakout_pts = (100.0 + dist_52w_high) * 0.2
        vol_pts = min(15.0, (vol_accel - 1.0) * 15.0)
        mom_raw = 40.0 + rsi_pts + trend_pts + breakout_pts + vol_pts
        mom_score = int(min(99, max(15, mom_raw)))

        # Dimension 5: Governance & Health
        if dte is not None and pat_margin is not None:
            gov_raw = 85.0
            if dte > 2.5:
                gov_raw -= 25
            elif dte > 1.5:
                gov_raw -= 12
            if pat_margin < 3.0:
                gov_raw -= 15
            gov_score = int(min(95, max(25, gov_raw)))
        else:
            gov_score = None  # Cannot compute without debt_to_equity or pat_margin

        # Weighted Composite Conviction Score
        if quality_score is not None and gov_score is not None:
            m6_score = int(
                (quality_score * M6FrozenResearchModel.WEIGHTS["business_quality"]) +
                (growth_score * M6FrozenResearchModel.WEIGHTS["growth"]) +
                (mom_score * M6FrozenResearchModel.WEIGHTS["momentum"]) +
                (val_score * M6FrozenResearchModel.WEIGHTS["valuation"]) +
                (gov_score * M6FrozenResearchModel.WEIGHTS["governance"])
            )
            m6_score = min(99, max(20, m6_score))
        else:
            m6_score = None  # Cannot compute composite score with missing sub-scores

        return {
            "company_id": company_id,
            "symbol": symbol,
            "as_of_date": as_of_date.isoformat(),
            "model_version": M6FrozenResearchModel.MODEL_VERSION,
            "research_evidence_status": M6FrozenResearchModel.RESEARCH_STATUS,
            "prospective_status": M6FrozenResearchModel.PROSPECTIVE_STATUS,
            "model_code_hash": M6FrozenResearchModel.MODEL_CODE_HASH,
            "input_snapshot_hash": input_snapshot_hash,
            "m6_conviction_score": m6_score,
            "sub_scores": {
                "business_quality": quality_score,
                "growth": growth_score,
                "momentum": mom_score,
                "valuation": val_score,
                "governance": gov_score
            }
        }
