"""
DEPRECATED — Corporate Announcements Client (Old).

This module is DEPRECATED. All callers must migrate to:
    src.ingestion.structured_events_client.StructuredDisclosuresClient

Reasons for deprecation:
1. Uses yfinance news as source — labels it "EXCHANGE_NEWS_FEED" which is misleading.
   yfinance is a financial data aggregator, not an exchange news feed.
2. No triple-timestamp discipline (source_published_at, ingested_at, event_occurred_at).
3. No source_type classification (SECONDARY_ARTICLE vs OFFICIAL_EXCHANGE_FILING).
4. Events generated here bypass the M6 source authority filter entirely.
5. Default fallback injects a synthetic "Regular quarterly operations filing" event
   with published_time = datetime.utcnow() — a fabricated event with a fake timestamp.

Migration path:
    # Old (DEPRECATED):
    from src.ingestion.announcements_client import CorporateAnnouncementsClient
    events = CorporateAnnouncementsClient.fetch_company_announcements(symbol)

    # New (CORRECT):
    from src.ingestion.structured_events_client import StructuredDisclosuresClient
    events = StructuredDisclosuresClient.extract_structured_events(symbol)

    # For official NSE exchange filings (preferred):
    from src.ingestion.nse_announcements_pipeline import NseAnnouncementsPipeline
    events = NseAnnouncementsPipeline.fetch_and_store(db, symbol)
"""

import warnings
import logging
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class CorporateAnnouncementsClient:
    """
    DEPRECATED. Use StructuredDisclosuresClient or NseAnnouncementsPipeline instead.
    """

    @staticmethod
    def fetch_company_announcements(symbol: str, limit: int = 5) -> List[Dict[str, Any]]:
        warnings.warn(
            "CorporateAnnouncementsClient.fetch_company_announcements() is DEPRECATED. "
            "Use StructuredDisclosuresClient.extract_structured_events() for secondary news, "
            "or NseAnnouncementsPipeline.fetch_and_store() for official NSE filings. "
            "This method returns SECONDARY_ARTICLE events with no triple-timestamp discipline.",
            DeprecationWarning,
            stacklevel=2,
        )
        logger.warning(
            f"[DEPRECATED] CorporateAnnouncementsClient called for {symbol}. "
            "Routing to StructuredDisclosuresClient..."
        )

        # Route to the correct implementation instead of silently using the old broken one
        from src.ingestion.structured_events_client import StructuredDisclosuresClient
        return StructuredDisclosuresClient.extract_structured_events(symbol, limit=limit)
