"""
Dual-Provider Cross-Check & Checksum Validator (Layer 2 Data Integrity).

Cross-checks price and financial data between Upstox (primary) and Yahoo Finance (secondary),
detecting provider anomalies, corporate action discrepancies, and data corruptions.

CONFLICT RESOLUTION RULE:
  On FLAGGED_DISCREPANCY (>1.5% price divergence):
  - Primary source (Upstox / NSE official) wins. NOT the maximum of the two prices.
  - The canonical_price is always set to price_provider_a (the more authoritative source).
  - The record is marked LOW_CONFIDENCE and flagged for manual review.
  - Taking max() was incorrect: it could prefer a stale inflated price over a correct current price.
"""

import hashlib
import json
import logging
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProviderCrossCheckEngine:
    """
    Validates cross-provider data fidelity with cryptographic checksums.
    """

    @staticmethod
    def cross_check_price_record(
        symbol: str,
        trading_date: str,
        price_provider_a: float,   # Primary source: Upstox (NSE official)
        source_a_name: str,
        price_provider_b: float,   # Secondary source: Yahoo Finance
        source_b_name: str,
        volume_a: Optional[int] = None,
        volume_b: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Cross-validates price and volume across two independent sources.

        Provider A is treated as the authoritative source (should be Upstox/NSE official).
        On discrepancy, provider A's price is used as canonical — never the maximum of the two.

        Returns:
            fidelity_status: HIGH_FIDELITY_MATCH | ACCEPTABLE_MATCH | FLAGGED_DISCREPANCY
            canonical_price: Always provider_a on discrepancy (not max)
            confidence_score: 100 | 85 | 40
        """
        if price_provider_a <= 0 or price_provider_b <= 0:
            price_divergence_pct = 100.0
        else:
            price_divergence_pct = round(
                abs(price_provider_a - price_provider_b) / price_provider_a * 100.0, 3
            )

        volume_divergence_pct = 0.0
        if volume_a and volume_b and volume_a > 0:
            volume_divergence_pct = round(abs(volume_a - volume_b) / volume_a * 100.0, 2)

        # Canonical record for checksum
        canonical_record = {
            "symbol":        symbol,
            "trading_date":  trading_date,
            "price_a":       price_provider_a,
            "price_b":       price_provider_b,
            "source_a":      source_a_name,
            "source_b":      source_b_name,
        }
        record_hash = hashlib.sha256(
            json.dumps(canonical_record, sort_keys=True).encode("utf-8")
        ).hexdigest()

        # Conflict resolution: provider A (primary/official) always wins on discrepancy
        if price_divergence_pct <= 0.5:
            fidelity_status  = "HIGH_FIDELITY_MATCH"
            confidence_score = 100
            canonical_price  = price_provider_a
        elif price_divergence_pct <= 1.5:
            fidelity_status  = "ACCEPTABLE_MATCH"
            confidence_score = 85
            canonical_price  = price_provider_a
        else:
            fidelity_status  = "FLAGGED_DISCREPANCY"
            confidence_score = 40
            # IMPORTANT: Use provider_a (primary/official source), NOT max().
            # max() was wrong: it could pick a stale high price over a correct current price.
            canonical_price  = price_provider_a
            logger.warning(
                f"[DISCREPANCY] {symbol} on {trading_date}: "
                f"{source_a_name}={price_provider_a} vs {source_b_name}={price_provider_b} "
                f"(divergence={price_divergence_pct}%). "
                f"Using primary source {source_a_name} as canonical. "
                f"Confidence: LOW. Manual review recommended."
            )

        return {
            "symbol":                symbol,
            "trading_date":          trading_date,
            "fidelity_status":       fidelity_status,
            "confidence_score":      confidence_score,
            "price_divergence_pct":  price_divergence_pct,
            "volume_divergence_pct": volume_divergence_pct,
            "canonical_price":       canonical_price,
            "canonical_source":      source_a_name,    # Always the primary source
            "record_checksum":       record_hash,
            "source_a":              f"{source_a_name}: ₹{price_provider_a:,.2f}",
            "source_b":              f"{source_b_name}: ₹{price_provider_b:,.2f}",
            "data_quality":          "HIGH_CONFIDENCE" if confidence_score >= 85 else "LOW_CONFIDENCE",
        }
