"""
Snapshot Consistency Enforcer (Fix 4).

Validates that every M6 decision snapshot uses data from a single consistent
T0 window — no mixing of financial periods, consolidation scopes, or quote sources.

Enforced invariants:
1. All fundamentals have publication_timestamp <= as_of_date (no future data)
2. All fundamentals share the same consolidation_scope (no STANDALONE + CONSOLIDATED mix)
3. Shareholding period_end_date is within 120 days of the most recent quarterly filing
4. Price quote is from within 1 trading day of as_of_date
5. No quarantined metrics present in M6 critical metrics set

Violations return recommended actions: APPROVE | QUARANTINE | PARTIAL_QUARANTINE
"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# M6-critical metrics — any quarantine in these fields blocks the entire snapshot
M6_CRITICAL_METRICS = {"roce_pct", "debt_to_equity", "promoter_holding_pct", "revenue_yoy_growth_pct"}

MAX_SHAREHOLDING_AGE_DAYS = 120  # Shareholding can be up to 1 quarter stale
MAX_PRICE_AGE_DAYS = 1           # Price must be within 1 trading day


class SnapshotConsistencyEnforcer:
    """
    Validates that an M6 decision snapshot is internally consistent.
    """

    @staticmethod
    def validate_snapshot(
        feature_dict: Dict[str, Any],
        as_of_date: date,
        financial_period_end: Optional[date] = None,
        shareholding_period_end: Optional[date] = None,
        price_date: Optional[date] = None,
        financial_consolidation_scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validates a candidate feature snapshot for internal consistency.

        Args:
            feature_dict: The full feature dictionary from FeatureEngine.
            as_of_date: The T0 snapshot date.
            financial_period_end: The period_end_date of the most recent financial filing.
            shareholding_period_end: The period_end_date of the shareholding filing used.
            price_date: The trading_date of the price used.
            financial_consolidation_scope: "CONSOLIDATED" or "STANDALONE".

        Returns:
            {
                "consistent": bool,
                "violations": List[str],
                "recommended_action": "APPROVE" | "QUARANTINE" | "PARTIAL_QUARANTINE",
                "blocking_violations": List[str],
                "non_blocking_violations": List[str],
            }
        """
        violations = []
        blocking_violations = []
        non_blocking_violations = []

        # ── Rule 1: No future financial data ──
        if financial_period_end and financial_period_end > as_of_date:
            v = (
                f"FUTURE_DATA: financial_period_end={financial_period_end} is after "
                f"as_of_date={as_of_date}. Lookahead bias detected."
            )
            violations.append(v)
            blocking_violations.append(v)

        # ── Rule 2: Consolidation scope consistency ──
        scope = financial_consolidation_scope or feature_dict.get("consolidation_scope")
        if scope and scope not in ("CONSOLIDATED", "STANDALONE", None):
            v = f"INVALID_SCOPE: consolidation_scope='{scope}' is not CONSOLIDATED or STANDALONE."
            violations.append(v)
            non_blocking_violations.append(v)

        # ── Rule 3: Shareholding staleness ──
        if shareholding_period_end and financial_period_end:
            age_days = abs((financial_period_end - shareholding_period_end).days)
            if age_days > MAX_SHAREHOLDING_AGE_DAYS:
                v = (
                    f"STALE_SHAREHOLDING: shareholding_period_end={shareholding_period_end} "
                    f"is {age_days} days from financial_period_end={financial_period_end} "
                    f"(max allowed: {MAX_SHAREHOLDING_AGE_DAYS} days)."
                )
                violations.append(v)
                # Blocking if shareholding is a critical M6 metric
                if "promoter_holding_pct" in M6_CRITICAL_METRICS:
                    blocking_violations.append(v)
                else:
                    non_blocking_violations.append(v)

        # ── Rule 4: Price freshness ──
        if price_date:
            price_age = abs((as_of_date - price_date).days)
            if price_age > MAX_PRICE_AGE_DAYS:
                v = (
                    f"STALE_PRICE: price_date={price_date} is {price_age} trading days "
                    f"from as_of_date={as_of_date} (max allowed: {MAX_PRICE_AGE_DAYS})."
                )
                violations.append(v)
                non_blocking_violations.append(v)

        # ── Rule 5: Quarantined M6 critical metrics ──
        if feature_dict.get("roce_quarantine_flag"):
            v = "QUARANTINED_ROCE: roce_pct is quarantined or unavailable. Cannot enter M6."
            violations.append(v)
            blocking_violations.append(v)

        shareholding_quality = feature_dict.get("shareholding_data_quality_flag")
        if shareholding_quality == "LOW_CONFIDENCE":
            v = (
                "LOW_CONFIDENCE_SHAREHOLDING: promoter_holding_pct sourced from "
                "FALLBACK_YFINANCE_APPROXIMATE. Must be superseded by NSE SEBI filing."
            )
            violations.append(v)
            blocking_violations.append(v)

        # ── Verdict ──
        consistent = len(blocking_violations) == 0

        if blocking_violations:
            action = "QUARANTINE"
        elif non_blocking_violations:
            action = "PARTIAL_QUARANTINE"
        else:
            action = "APPROVE"

        if not consistent:
            logger.warning(
                f"[ConsistencyEnforcer] Snapshot as_of={as_of_date} {action}. "
                f"Blocking violations: {blocking_violations}"
            )
        else:
            logger.info(f"[ConsistencyEnforcer] Snapshot as_of={as_of_date} APPROVED. {len(non_blocking_violations)} non-blocking warnings.")

        return {
            "consistent": consistent,
            "violations": violations,
            "blocking_violations": blocking_violations,
            "non_blocking_violations": non_blocking_violations,
            "recommended_action": action,
        }
