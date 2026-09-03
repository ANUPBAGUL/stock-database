"""
Immutable Pre-Trade Decision Snapshot Engine.

Captures the exact state of what was knowable at T0:
- Full vector of ~180 raw and derived variables (P&L primitives, ROCE, technicals, valuation percentiles)
- Cryptographic SHA-256 dataset hash
- Conviction verdict and multi-horizon ratings
- Causal why-buy / why-not-buy hypotheses
- Falsifiable invalidation conditions

NEVER OVERWRITTEN — creates an append-only audit trail of machine intelligence.
"""

import json
import hashlib
import logging
from datetime import datetime, date
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from src.db.models import DecisionSnapshot, Company
from src.analytics.feature_engine import FeatureEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DecisionSnapshotEngine:
    """
    Manages the creation and storage of immutable pre-trade T0 snapshots.
    """

    @staticmethod
    def _compute_dataset_hash(features_dict: Dict[str, Any]) -> str:
        """Generates deterministic SHA-256 hash of the feature dictionary."""
        serialized = json.dumps(features_dict, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    @classmethod
    def record_decision_snapshot(
        cls,
        db: Session,
        company_id: str,
        t0_timestamp: datetime,
        feature_vector: Dict[str, Any],
        m6_score: float,
        verdict: str,
        horizon_ratings: Dict[str, Any],
        why_buy_reasons: list,
        why_not_buy_reasons: list,
        invalidation_thresholds: dict,
        model_version: str = "M6_FROZEN_EXP004",
        feature_set_version: str = "v2.4.0"
    ) -> DecisionSnapshot:
        """
        Creates and persists an immutable T0 snapshot record.
        """
        ds_hash = cls._compute_dataset_hash(feature_vector)

        # Missingness calculation
        total_fields = len(feature_vector)
        none_fields = sum(1 for v in feature_vector.values() if v is None)
        missing_pct = round((none_fields / max(1, total_fields)) * 100, 2)
        quality_score = round(max(0.0, 100.0 - missing_pct), 2)

        snapshot = DecisionSnapshot(
            company_id=company_id,
            decision_timestamp=t0_timestamp,
            feature_set_version=feature_set_version,
            model_version=model_version,
            dataset_hash=ds_hash,
            raw_features_payload=feature_vector,
            data_quality_score=quality_score,
            missingness_pct=missing_pct,
            m6_score=m6_score,
            verdict=verdict,
            horizon_ratings=horizon_ratings,
            thesis_why_buy={"points": why_buy_reasons},
            thesis_why_not_buy={"points": why_not_buy_reasons},
            invalidation_conditions=invalidation_thresholds
        )

        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

        logger.info(f"[Decision Snapshot] Recorded immutable T0 snapshot {snapshot.snapshot_id} for company {company_id} at {t0_timestamp}.")
        return snapshot
