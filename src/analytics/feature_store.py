"""
Point-in-Time Feature Store & Metadata Registry (Layer 3 Feature Architecture).

Provides a versioned, point-in-time feature interface with provenance metadata,
calculation timestamps, missing-data status, and quality flags.
"""

import logging
from datetime import date, datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from src.analytics.feature_engine import FeatureEngine
from src.db.models import Company, DailyPriceRaw

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FeatureStore:
    """
    Institutional Feature Store with deterministic versioning and quality flags.
    """
    FEATURE_STORE_VERSION = "v2.0-pit-feature-store"

    @staticmethod
    def get_stock_features(
        db: Session, company_id: str, as_of_date: date
    ) -> Dict[str, Any]:
        """
        Extracts all point-in-time features with explicit metadata for each feature.
        """
        raw_feats = FeatureEngine.extract_features_as_of(db, company_id, as_of_date)

        comp = db.query(Company).filter_by(company_id=company_id).first()
        symbol = comp.nse_symbol if comp else "UNKNOWN"

        feature_catalog = {}
        missing_count = 0
        total_count = len(raw_feats)

        for feat_name, feat_val in raw_feats.items():
            is_missing = feat_val is None
            if is_missing:
                missing_count += 1

            feature_catalog[feat_name] = {
                "feature_name": feat_name,
                "value": feat_val,
                "as_of_date": as_of_date.isoformat(),
                "calculation_version": FeatureStore.FEATURE_STORE_VERSION,
                "is_missing": is_missing,
                "quality_score": 100 if not is_missing else 0
            }

        data_completeness_pct = round(((total_count - missing_count) / max(1, total_count)) * 100.0, 1)

        return {
            "company_id": company_id,
            "symbol": symbol,
            "as_of_date": as_of_date.isoformat(),
            "feature_store_version": FeatureStore.FEATURE_STORE_VERSION,
            "data_completeness_pct": data_completeness_pct,
            "total_features": total_count,
            "missing_features": missing_count,
            "raw_features": raw_feats,
            "feature_catalog": feature_catalog
        }
