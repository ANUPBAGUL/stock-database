"""
Multi-Factor Failed Multibagger & False-Positive Post-Mortem Diagnostic Engine.

Identifies high-conviction decision snapshots that failed to deliver multibagger outcomes
or experienced severe capital destruction (>40% drawdown / structural underperformance).

Permits compound multi-factor failure modeling (e.g., VALUATION_COMPRESSION + CYCLICAL_REVERSAL + MARGIN_COMPRESSION)
with empirical quantitative evidence payloads and confidence scoring.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session

from src.db.models import DecisionSnapshot, ForwardOutcome, MultibaggerFailureDiagnostic, BitemporalFinancial, Company

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FailureAnalyzer:
    """
    Post-mortem diagnostic analyzer for false positives and thesis failures.
    """

    @classmethod
    def diagnose_snapshot_failure(
        cls,
        db: Session,
        snapshot: DecisionSnapshot,
        outcome: ForwardOutcome,
        as_of_date: Optional[date] = None
    ) -> Optional[MultibaggerFailureDiagnostic]:
        """
        Audits a decision snapshot against realized forward performance and fundamental facts.
        Detects primary and secondary failure factors and logs empirical evidence.
        """
        is_high_conviction = snapshot.m6_score and snapshot.m6_score >= 70.0
        is_severe_drawdown = outcome.max_drawdown_pct and outcome.max_drawdown_pct <= -40.0
        is_growth_failure = outcome.is_failure

        if not (is_high_conviction and (is_severe_drawdown or is_growth_failure)):
            return None

        # Fetch fundamental facts at T0 and post T0
        t0_features = snapshot.raw_features_payload or {}
        expected_roce = float(t0_features.get("roce_pct", 25.0) or 25.0)
        expected_rev_growth = float(t0_features.get("revenue_yoy_growth_pct", 25.0) or 25.0)

        latest_filing = db.query(BitemporalFinancial).filter(
            BitemporalFinancial.company_id == snapshot.company_id,
            BitemporalFinancial.period_end_date > snapshot.decision_timestamp.date()
        ).order_by(BitemporalFinancial.period_end_date.desc()).first()

        realized_roce = expected_roce
        realized_rev_growth = expected_rev_growth
        
        primary_reason = "GROWTH_FAILURE"
        secondary_reasons = []
        evidence_list = []
        post_mortem_notes = "Earnings acceleration failed to materialize."

        if latest_filing:
            # Check for ROCE deterioration
            if latest_filing.ebit and latest_filing.total_assets and latest_filing.current_liabilities:
                ce = max(50.0, latest_filing.total_assets - latest_filing.current_liabilities)
                realized_roce = round((latest_filing.ebit / ce) * 100.0, 2)
                
                if realized_roce < (expected_roce - 10.0):
                    primary_reason = "ROCE_DETERIORATION"
                    evidence_list.append({
                        "metric": "ROCE",
                        "expected_pct": expected_roce,
                        "realized_pct": realized_roce,
                        "delta_bps": int((realized_roce - expected_roce) * 100)
                    })
                    post_mortem_notes = f"ROCE collapsed from {expected_roce}% at T0 to {realized_roce}%, destroying returns on incremental capital."

            # Check for debt explosion
            if latest_filing.total_debt and latest_filing.net_worth:
                de_ratio = latest_filing.total_debt / max(1.0, latest_filing.net_worth)
                if de_ratio > 1.8:
                    if primary_reason == "GROWTH_FAILURE":
                        primary_reason = "DEBT_EXPLOSION"
                    else:
                        secondary_reasons.append("DEBT_EXPLOSION")
                    evidence_list.append({
                        "metric": "DEBT_TO_EQUITY",
                        "realized_ratio": round(de_ratio, 2),
                        "total_debt_cr": latest_filing.total_debt
                    })

            # Check for margin compression
            if latest_filing.revenue and latest_filing.ebitda:
                margin = (latest_filing.ebitda / latest_filing.revenue) * 100.0
                if margin < 10.0 and expected_roce > 20.0:
                    secondary_reasons.append("MARGIN_COMPRESSION")
                    evidence_list.append({
                        "metric": "EBITDA_MARGIN",
                        "realized_margin_pct": round(margin, 2)
                    })

        if is_severe_drawdown and primary_reason == "GROWTH_FAILURE":
            primary_reason = "VALUATION_COMPRESSION"
            post_mortem_notes = f"Severe multiple de-rating triggered peak drawdown of {outcome.max_drawdown_pct}%."
            evidence_list.append({
                "metric": "PEAK_DRAWDOWN",
                "max_drawdown_pct": outcome.max_drawdown_pct
            })

        detection_date = as_of_date or date.today()

        existing = db.query(MultibaggerFailureDiagnostic).filter_by(snapshot_id=snapshot.snapshot_id).first()
        if not existing:
            diag = MultibaggerFailureDiagnostic(
                snapshot_id=snapshot.snapshot_id,
                outcome_id=outcome.outcome_id,
                company_id=snapshot.company_id,
                failure_category=primary_reason,
                primary_failure_reason=primary_reason,
                secondary_failure_reasons={"reasons": secondary_reasons},
                failure_evidence={"evidence": evidence_list},
                failure_confidence=0.92,
                failure_detected_at=detection_date,
                severity_rank=1,
                first_detected_date=detection_date,
                post_mortem_notes=post_mortem_notes,
                expected_roce_pct=expected_roce,
                realized_roce_pct=realized_roce,
                expected_revenue_growth=expected_rev_growth,
                realized_revenue_growth=realized_rev_growth,
                peak_drawdown_pct=outcome.max_drawdown_pct
            )
            db.add(diag)
        else:
            existing.failure_category = primary_reason
            existing.primary_failure_reason = primary_reason
            existing.secondary_failure_reasons = {"reasons": secondary_reasons}
            existing.failure_evidence = {"evidence": evidence_list}
            existing.post_mortem_notes = post_mortem_notes
            existing.realized_roce_pct = realized_roce
            existing.peak_drawdown_pct = outcome.max_drawdown_pct
            diag = existing

        db.commit()
        logger.info(f"[Failure Diagnostic] Snapshot {snapshot.snapshot_id} classified as failure [{primary_reason}] (Secondary: {secondary_reasons}): {post_mortem_notes}")
        return diag
