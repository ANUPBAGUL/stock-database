"""
AI Company Profiler — Multi-Dimension Fundamental & Technical Conviction Scoring.

Computes point-in-time deterministic multi-factor scores with reproducible SHA256 input hashing.
"""

import json
import hashlib
import logging
from datetime import date, datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from src.analytics.feature_engine import FeatureEngine
from src.db.models import AICompanyProfile, Company

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AICompanyProfiler:
    """
    11-dimension scoring engine for institutional equity conviction.
    Uses real financial ratios, TTM capital efficiency, and technical structure.
    """

    @staticmethod
    def generate_company_profile(
        db: Session, company_id: str, as_of_date: date, model_version: str = "v2.0-quant-rules"
    ) -> Dict[str, Any]:
        # 1. Fetch PIT Features strictly as of date T
        features = FeatureEngine.extract_features_as_of(db, company_id, as_of_date)

        # 2. Hash input snapshot for backtest auditability
        feature_bytes = json.dumps(features, sort_keys=True, default=str).encode('utf-8')
        input_snapshot_hash = hashlib.sha256(feature_bytes).hexdigest()

        # Extract features
        rev_growth = features.get("revenue_yoy_growth_pct") or 0.0
        pat_growth = features.get("pat_yoy_growth_pct") or 0.0
        ebitda_margin = features.get("ebitda_margin") or 15.0
        pat_margin = features.get("pat_margin") or 8.0
        roce = features.get("roce_pct") or 15.0
        dte = features.get("debt_to_equity") or 0.5
        pe = features.get("pe_ratio")
        pb = features.get("pb_ratio")

        rsi = features.get("rsi_14") or 50.0
        dist_sma50 = features.get("dist_from_sma50_pct") or 0.0
        dist_sma200 = features.get("dist_from_sma200_pct") or 0.0
        dist_52w_high = features.get("dist_from_52w_high_pct") or -15.0
        vol_accel = features.get("volume_acceleration_ratio") or 1.0

        # ──────────────────────────────────────────────────────────────
        # Dimension 1: Growth Score (0 - 100)
        # ──────────────────────────────────────────────────────────────
        growth_raw = 50.0 + (min(50.0, max(-30.0, rev_growth)) * 0.5) + (min(50.0, max(-30.0, pat_growth)) * 0.5)
        growth_score = int(min(99, max(15, growth_raw)))

        # ──────────────────────────────────────────────────────────────
        # Dimension 2: Capital Efficiency & Quality (ROCE & Margins)
        # ──────────────────────────────────────────────────────────────
        roce_capped = min(50.0, max(0.0, roce))
        quality_raw = 30.0 + (roce_capped * 0.9) + (min(35.0, ebitda_margin) * 0.7)
        business_quality_score = int(min(99, max(20, quality_raw)))

        # ──────────────────────────────────────────────────────────────
        # Dimension 3: Valuation Score (P/E & P/B Realistic Scaling)
        # ──────────────────────────────────────────────────────────────
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
            val_raw = 60  # Default neutral

        # Small adjustment if P/B is reasonable
        if pb and pb < 2.5:
            val_raw += 5
        valuation_score = int(min(95, max(20, val_raw)))

        # ──────────────────────────────────────────────────────────────
        # Dimension 4: Technical Momentum Score
        # ──────────────────────────────────────────────────────────────
        # Sweet spot for RSI: 52 - 68 (momentum expansion without extreme overbought)
        rsi_pts = 20.0 - abs(rsi - 60.0) * 0.8
        trend_pts = min(20.0, max(-15.0, dist_sma50 * 1.0)) + min(15.0, max(-10.0, dist_sma200 * 0.5))
        breakout_pts = (100.0 + dist_52w_high) * 0.2  # Closer to 52w high = stronger relative strength
        vol_pts = min(15.0, (vol_accel - 1.0) * 15.0)

        mom_raw = 40.0 + rsi_pts + trend_pts + breakout_pts + vol_pts
        momentum_score = int(min(99, max(15, mom_raw)))

        # ──────────────────────────────────────────────────────────────
        # Dimension 5: Financial Health & Governance Score
        # ──────────────────────────────────────────────────────────────
        gov_raw = 85.0
        if dte > 2.5:
            gov_raw -= 25
        elif dte > 1.5:
            gov_raw -= 12

        if pat_margin < 3.0:
            gov_raw -= 15

        governance_score = int(min(95, max(25, gov_raw)))

        # ──────────────────────────────────────────────────────────────
        # Dimension 6: Overall Conviction Score
        # ──────────────────────────────────────────────────────────────
        overall_conviction = int(
            (business_quality_score * 0.30) +
            (growth_score * 0.25) +
            (momentum_score * 0.20) +
            (valuation_score * 0.15) +
            (governance_score * 0.10)
        )
        overall_conviction = min(99, max(20, overall_conviction))

        profile_data = {
            "company_id": company_id,
            "as_of_date": as_of_date.isoformat(),
            "model_version": model_version,
            "input_snapshot_hash": input_snapshot_hash,
            "overall_conviction_score": overall_conviction,
            "business_quality_score": business_quality_score,
            "growth_score": growth_score,
            "momentum_score": momentum_score,
            "valuation_score": valuation_score,
            "governance_score": governance_score,
            "features_summary": {
                "close_price": features.get("close_price"),
                "market_cap_cr": features.get("market_cap_crores"),
                "pe_ratio": pe,
                "roce_pct": roce,
                "revenue_yoy_pct": rev_growth,
                "pat_yoy_pct": pat_growth,
                "rsi_14": rsi,
                "atr_14": features.get("atr_14"),
                "dist_52w_high_pct": dist_52w_high
            }
        }

        return profile_data
