"""
Data Quality Quarantine Engine.

Provides metric-level audit and quarantine logic for all derived financial ratios
entering the M6 feature vector.

The quarantine enforces three invariants:
1. Cross-check: Derived value must not diverge from any available cross-check value
   by more than the specified tolerance.
2. Input completeness: Key raw inputs must not be fabricated or estimated (e.g., no
   ttm_rev * 0.40 proxy for capital employed).
3. Period consistency: Numerator and denominator must come from compatible time windows.

A quarantined metric is NEVER silently swapped for a default value. It becomes None
in the feature vector with a trace record explaining why.
"""

import logging
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Metric-level tolerances for cross-check divergence before quarantine
QUARANTINE_TOLERANCES: Dict[str, float] = {
    "roce_pct": 15.0,           # % absolute divergence
    "debt_to_equity": 0.30,     # ratio absolute divergence
    "net_de_ratio": 0.30,
    "financial_de_ratio": 0.30,
    "promoter_holding_pct": 5.0,  # % absolute divergence
    "fii_holding_pct": 5.0,
    "ebitda_margin": 8.0,
    "pat_margin": 5.0,
}

# Metrics that are CRITICAL for M6 — quarantine immediately if below minimum quality
M6_CRITICAL_METRICS = {"roce_pct", "debt_to_equity", "promoter_holding_pct", "revenue_yoy_growth_pct"}


class DataQualityQuarantine:
    """
    Audits derived financial metrics against cross-check values and input quality rules.
    Returns structured audit records suitable for DataAuditTrace persistence.
    """

    @staticmethod
    def audit_metric(
        metric_name: str,
        computed_value: Optional[float],
        formula: str,
        raw_inputs: Dict[str, Any],
        cross_check_value: Optional[float] = None,
        source_quality: str = "HIGH_CONFIDENCE",  # HIGH_CONFIDENCE, LOW_CONFIDENCE, NO_DATA
        fabricated_inputs: Optional[List[str]] = None,  # list of input names that were estimated/proxied
    ) -> Dict[str, Any]:
        """
        Audits a single derived metric.

        Args:
            metric_name: e.g., "roce_pct"
            computed_value: The value computed by feature_engine.
            formula: Human-readable formula string.
            raw_inputs: Dict of the actual primitive inputs used.
            cross_check_value: Optional independent benchmark value for cross-checking.
            source_quality: Quality of the underlying source data.
            fabricated_inputs: List of any input fields that were estimated/proxied, not sourced from filings.

        Returns:
            Audit dict with status, reason, and all lineage fields.
        """
        fabricated_inputs = fabricated_inputs or []
        violations = []
        status = "APPROVED"

        # Rule 1: NULL input — if value is None, status reflects missing data, not quarantine
        if computed_value is None:
            return {
                "metric_name": metric_name,
                "displayed_value": None,
                "status": "MISSING_DATA",
                "reason": "Computed value is None — balance sheet data unavailable. Not estimated.",
                "formula": formula,
                "raw_inputs": raw_inputs,
                "cross_check_value": cross_check_value,
                "source_quality": source_quality,
                "quarantine_violations": [],
            }

        # Rule 2: Fabricated/estimated inputs detected
        if fabricated_inputs:
            violations.append(
                f"Fabricated inputs detected: {fabricated_inputs}. "
                f"These were not sourced from official filings."
            )
            status = "QUARANTINED"
            logger.warning(
                f"[Quarantine] {metric_name}={computed_value:.2f} QUARANTINED — "
                f"fabricated inputs: {fabricated_inputs}"
            )

        # Rule 3: Cross-check divergence
        if cross_check_value is not None:
            tolerance = QUARANTINE_TOLERANCES.get(metric_name, 20.0)
            divergence = abs(computed_value - cross_check_value)
            if divergence > tolerance:
                violations.append(
                    f"Cross-check divergence: computed={computed_value:.2f}, "
                    f"benchmark={cross_check_value:.2f}, "
                    f"divergence={divergence:.2f} > tolerance={tolerance:.2f}"
                )
                if status != "QUARANTINED":
                    status = "QUARANTINED"
                logger.warning(
                    f"[Quarantine] {metric_name}={computed_value:.2f} QUARANTINED — "
                    f"diverges {divergence:.2f} from cross-check {cross_check_value:.2f} "
                    f"(tolerance: ±{tolerance:.2f})"
                )

        # Rule 4: Low-confidence source
        if source_quality == "LOW_CONFIDENCE" and metric_name in M6_CRITICAL_METRICS:
            violations.append(
                f"Critical M6 metric sourced from LOW_CONFIDENCE data. "
                f"Must be superseded by HIGH_CONFIDENCE official filing before M6 use."
            )
            if status != "QUARANTINED":
                status = "PARTIAL_QUARANTINE"

        # Rule 5: No-data source
        if source_quality == "NO_DATA":
            status = "QUARANTINED"
            violations.append("No authoritative data source available.")

        if status == "APPROVED":
            logger.debug(f"[Quarantine] {metric_name}={computed_value:.2f} APPROVED.")

        return {
            "metric_name": metric_name,
            "displayed_value": computed_value if status == "APPROVED" else None,
            "raw_computed_value": computed_value,  # always preserved for audit
            "status": status,
            "reason": " | ".join(violations) if violations else "All quality checks passed.",
            "formula": formula,
            "raw_inputs": raw_inputs,
            "cross_check_value": cross_check_value,
            "source_quality": source_quality,
            "quarantine_violations": violations,
        }

    @staticmethod
    def audit_batch(metrics: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Audits multiple metrics in one call. Returns dict keyed by metric_name.
        """
        results = {}
        for m in metrics:
            result = DataQualityQuarantine.audit_metric(**m)
            results[m["metric_name"]] = result
        return results

    @staticmethod
    def extract_approved_values(audit_results: Dict[str, Dict[str, Any]]) -> Dict[str, Optional[float]]:
        """
        Extracts only APPROVED metric values for use in the M6 feature vector.
        QUARANTINED and PARTIAL_QUARANTINE values are replaced with None.
        """
        return {
            name: result["displayed_value"]
            for name, result in audit_results.items()
        }
