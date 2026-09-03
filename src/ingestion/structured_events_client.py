"""
Structured Corporate Disclosures & Disruption Events Client (Layer 6 & Layer 7).

Extracts authentic corporate events directly from BSE/NSE SEBI Regulation 30/33 official filings:
- Capacity expansions, CaPEx announcements
- Order wins & material contracts
- Financial results filings & board meeting dates
- Management changes (MD/CEO/CFO appointments, resignations)
- Regulatory actions (USFDA inspections, SEBI orders)

ZERO NEWS AGGREGATOR HALLUCINATIONS:
- All events originate from official exchange announcements with PDF links on exchange servers.
- Third-party blog/news aggregators are excluded to prevent cross-ticker misattribution.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from src.ingestion.bse_announcements_client import BseAnnouncementsClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StructuredDisclosuresClient:
    """
    Ingests and normalizes official exchange corporate announcements.
    """

    @staticmethod
    def extract_structured_events(
        symbol: str, limit: int = 15, bse_client: Optional[BseAnnouncementsClient] = None
    ) -> List[Dict[str, Any]]:
        """
        Extracts verified corporate events from official exchange filings.
        """
        client = bse_client or BseAnnouncementsClient()
        raw_filings = client.fetch_official_announcements(symbol, limit=limit)

        if not raw_filings:
            logger.info(f"[StructuredDisclosures] No official filings found for {symbol}")
            return []

        structured_events = []
        for filing in raw_filings:
            event_type = filing.get("event_type", "GENERAL_CORPORATE_DISCLOSURE")
            materiality = filing.get("materiality", "LOW")
            
            # Map affected fundamental dimension
            if event_type == "EARNINGS_RESULT":
                dimension = "EARNINGS_MOMENTUM"
                confidence = 95
            elif event_type in ("CAPACITY_EXPANSION", "ORDER_WIN"):
                dimension = "REINVESTMENT_GROWTH"
                confidence = 90
            elif event_type == "MANAGEMENT_CHANGE":
                dimension = "MANAGEMENT_QUALITY"
                confidence = 85
            elif event_type == "REGULATORY_ACTION":
                dimension = "REGULATORY_RISK"
                confidence = 90
            elif event_type == "CORPORATE_ACTION":
                dimension = "CAPITAL_STRUCTURE"
                confidence = 95
            else:
                dimension = "INFORMATIONAL"
                confidence = 75

            structured_events.append({
                "event_id": filing["event_id"],
                "symbol": filing["symbol"],
                "event_type": event_type,
                "materiality": materiality,
                "confidence_score": confidence,
                "affected_dimension": dimension,
                "headline": filing["headline"],
                "summary": filing["summary"],
                "source_published_at": filing["source_published_at"],
                "ingested_at": filing["ingested_at"],
                "event_occurred_at": None,
                "source_document_url": filing.get("source_document_url"),
                "source_type": "OFFICIAL_EXCHANGE_FILING",
                "is_m6_eligible": True,
                "source_authority_rank": 1,
            })

        logger.info(f"[StructuredDisclosures] Processed {len(structured_events)} verified exchange events for {symbol}")
        return structured_events
