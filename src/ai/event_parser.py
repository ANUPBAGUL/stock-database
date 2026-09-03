import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from src.db.models import CompanyEvent, Company

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EventParser:
    """
    Parses unstructured text announcements into structured company events.
    """

    @staticmethod
    def parse_announcement(
        db: Session,
        company_id: str,
        headline: str,
        text: str,
        publication_date: datetime,
        source_url: str = ""
    ) -> CompanyEvent:
        
        # Rule-based / NLP classification heuristics
        event_type = "OTHER"
        order_size_inr = None
        materiality_score = 0.50

        headline_lower = headline.lower() + " " + text.lower()

        # Order Win check
        if any(w in headline_lower for w in ["bagged order", "order worth", "received order", "awarded contract"]):
            event_type = "ORDER_WIN"
            materiality_score = 0.75
            # Try regex extraction for order size in crores
            match = re.search(r'(?:rs\.?|inr|worth)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore)', headline_lower)
            if match:
                val_str = match.group(1).replace(',', '')
                order_size_inr = float(val_str) * 10000000.0 # Convert Crores to absolute INR

        # Capex check
        elif any(w in headline_lower for w in ["capacity expansion", "new plant", "capex", "investment of"]):
            event_type = "CAPEX"
            materiality_score = 0.80

        # Management change check
        elif any(w in headline_lower for w in ["resignation of ceo", "appointment of ceo", "cfo resigns"]):
            event_type = "MANAGEMENT_CHANGE"
            materiality_score = 0.70

        ai_interpretation = {
            "summary": headline,
            "classified_type": event_type,
            "confidence": 0.85,
            "key_takeaway": f"Material event '{event_type}' detected for company."
        }

        event = CompanyEvent(
            company_id=company_id,
            event_date=publication_date,
            publication_date=publication_date,
            event_type=event_type,
            headline=headline,
            summary=text[:1900],
            order_size_inr=order_size_inr,
            materiality_score=materiality_score,
            ai_interpretation=ai_interpretation,
            source_url=source_url
        )

        db.add(event)
        db.commit()
        db.refresh(event)

        logger.info(f"Parsed and created CompanyEvent ID={event.event_id} (Type={event_type})")
        return event
