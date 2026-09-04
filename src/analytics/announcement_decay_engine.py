"""
Announcement Materiality Scoring & Half-Life Time-Decay Engine.

Implements the Dual-Track exponential decay framework:
- Track A (Tactical Events): Half-Life = 48 Hours. Absorbed into price within 7 days.
- Track B (Structural Catalysts): Half-Life = 90 Days. Absorbed into financials after 2 quarters.
"""

import math
import re
import logging
from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from src.db.models import CorporateAnnouncement, Company, BitemporalFinancial

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Category Base Weights (0 to 100)
CATEGORY_WEIGHTS = {
    "REGULATORY_APPROVAL": 100.0,
    "REGULATORY_BAN": 100.0,
    "CAPEX_COMMISSIONING": 90.0,
    "CAPACITY_EXPANSION": 90.0,
    "ORDER_WIN": 85.0,
    "CONTRACT_AWARD": 85.0,
    "AUDITOR_RESIGNATION": 80.0,
    "MANAGEMENT_CHANGE": 80.0,
    "CREDIT_RATING_UPGRADE": 75.0,
    "CREDIT_RATING_DOWNGRADE": 75.0,
    "EARNINGS_SURPRISE": 70.0,
    "EARNINGS_FILING": 70.0,
    "DIVIDEND": 40.0,
    "BONUS_SPLIT": 40.0,
    "BUYBACK": 50.0,
    "GENERAL_FILING": 20.0
}

# Half-Life Parameters (in hours)
HALF_LIFE_TACTICAL_HOURS = 48.0   # 2 Days
HALF_LIFE_STRUCTURAL_HOURS = 2160.0 # 90 Days (90 * 24)

# Positive & Negative Keyword Lexicons
POSITIVE_KEYWORDS = [
    "awarded", "commissioned", "expansion", "approved", "upgraded", "growth",
    "highest ever", "debt free", "order win", "patent granted", "record profit",
    "secured", "wins order", "contract signed", "commercial production"
]

NEGATIVE_KEYWORDS = [
    "resigned", "fraud", "investigation", "downgraded", "strike", "penalty",
    "delayed", "cancelled", "loss", "show cause", "default", "breached",
    "resignation", "warning", "sebi order", "tax notice"
]


class AnnouncementDecayEngine:
    """
    Quantitative scoring, half-life decay, and lifecycle state manager for official corporate filings.
    """

    @staticmethod
    def extract_monetary_value_cr(text: str) -> Optional[float]:
        """
        Extracts INR Crore value from disclosure text using regex patterns.
        Handles 'Rs. 500 Cr', '₹ 1,200 Crores', 'USD 50 Mn', etc.
        """
        if not text:
            return None

        # Pattern: (Rs|₹|INR)?\s*([0-9,.]+)\s*(Cr|Crore|Crores)
        cr_match = re.search(r'(?:Rs\.?|₹|INR)?\s*([\d,]+(?:\.\d+)?)\s*(?:Cr|Crore|Crores)', text, re.IGNORECASE)
        if cr_match:
            try:
                val_str = cr_match.group(1).replace(',', '')
                return float(val_str)
            except ValueError:
                pass

        # Pattern: USD / Dollar Millions (Approx 1 USD Mn = ~8.4 Cr)
        usd_match = re.search(r'(?:\$|USD)\s*([\d,]+(?:\.\d+)?)\s*(?:Mn|Million)', text, re.IGNORECASE)
        if usd_match:
            try:
                val_str = usd_match.group(1).replace(',', '')
                return round(float(val_str) * 8.4, 2)
            except ValueError:
                pass

        return None

    @classmethod
    def classify_event_track(cls, event_type: str, headline: str) -> str:
        """
        Determines whether an event is TACTICAL (48h half-life) or STRUCTURAL (90d half-life).
        """
        evt = event_type.upper()
        hl = headline.lower()

        # Structural events affect long-term capacity, debt, or multi-year contracts
        if evt in ["CAPEX_COMMISSIONING", "CAPACITY_EXPANSION", "ORDER_WIN", "CONTRACT_AWARD"]:
            return "STRUCTURAL"
        if any(w in hl for w in ["multi-year", "5-year", "10-year", "megawatt", "capacity addition", "new plant"]):
            return "STRUCTURAL"

        return "TACTICAL"

    @classmethod
    def score_announcement(
        cls,
        event_type: str,
        headline: str,
        summary: str = "",
        ttm_revenue_cr: float = 1000.0,
        price_jump_pct: float = 0.0,
        volume_spike_ratio: float = 1.0
    ) -> Tuple[float, float, str]:
        """
        Computes the deterministic raw score, extracted INR Cr value, and track type.
        Returns: (raw_materiality_score, extracted_value_cr, track_type)
        """
        evt = event_type.upper()
        combined_text = f"{headline} {summary}".lower()

        # 1. Base Category Weight
        base_weight = CATEGORY_WEIGHTS.get(evt, 30.0)

        # 2. Extract monetary amount
        val_cr = cls.extract_monetary_value_cr(f"{headline} {summary}")

        # 3. Size Materiality Multiplier
        size_mult = 1.0
        if val_cr is not None and ttm_revenue_cr > 0:
            ratio = val_cr / ttm_revenue_cr
            if ratio >= 0.50:
                size_mult = 2.0  # Transformational (>50% of annual revenue)
            elif ratio >= 0.20:
                size_mult = 1.5  # High significance (20% - 50%)
            elif ratio >= 0.05:
                size_mult = 1.0  # Standard (5% - 20%)
            else:
                size_mult = 0.6  # Minor (<5%)

        # 4. Directional Tone Multiplier
        pos_hits = sum(1 for w in POSITIVE_KEYWORDS if w in combined_text)
        neg_hits = sum(1 for w in NEGATIVE_KEYWORDS if w in combined_text)

        if neg_hits > pos_hits:
            direction = -1.0
        elif pos_hits > 0:
            direction = 1.0
        else:
            direction = 1.0 if base_weight >= 70 else 0.5

        # 5. Market Confirmation Multiplier (Price + Volume Surge)
        market_mult = 1.0
        if price_jump_pct >= 2.0 and volume_spike_ratio >= 1.8:
            market_mult = 1.3  # Confirmed institutional buying
        elif price_jump_pct <= -2.0 and direction > 0:
            market_mult = 0.8  # Sell-on-news / distribution

        raw_score = min(100.0, max(-100.0, base_weight * size_mult * direction * market_mult))
        track_type = cls.classify_event_track(evt, headline)

        return round(raw_score, 1), val_cr, track_type

    @classmethod
    def calculate_decayed_score(
        cls,
        raw_score: float,
        track_type: str,
        publication_time: datetime,
        current_time: Optional[datetime] = None
    ) -> Tuple[float, str]:
        """
        Calculates the active decayed score using the exponential half-life formula:
        S(t) = S_raw * e^(-lambda * delta_hours)
        Returns: (decayed_score, new_status)
        """
        now = current_time or datetime.now(timezone.utc)
        pub_dt = publication_time
        if hasattr(now, "tzinfo") and now.tzinfo is not None:
            if hasattr(pub_dt, "tzinfo") and pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        else:
            if hasattr(pub_dt, "tzinfo") and pub_dt.tzinfo is not None:
                pub_dt = pub_dt.replace(tzinfo=None)

        delta_hours = max(0.0, (now - pub_dt).total_seconds() / 3600.0)

        half_life_hours = HALF_LIFE_STRUCTURAL_HOURS if track_type == "STRUCTURAL" else HALF_LIFE_TACTICAL_HOURS
        decay_constant = math.log(2) / half_life_hours

        decay_factor = math.exp(-decay_constant * delta_hours)
        decayed_score = round(raw_score * decay_factor, 1)

        # State transition rules
        if delta_hours <= 24.0:
            status = "NEW_ACTIVE"
        elif track_type == "TACTICAL":
            if delta_hours > 168.0 or abs(decayed_score) < (abs(raw_score) * 0.08): # 7 days or <8%
                status = "ABSORBED_INTO_PRICE"
            else:
                status = "DECAYING"
        elif track_type == "STRUCTURAL":
            if delta_hours > 4320.0 or abs(decayed_score) < (abs(raw_score) * 0.15): # 180 days
                status = "ABSORBED_INTO_FINANCIALS"
            else:
                status = "DECAYING"
        else:
            status = "DECAYING"

        return decayed_score, status

    @classmethod
    def update_all_announcements_decay(cls, db: Session) -> int:
        """
        Refreshes the decayed scores and lifecycle status for all active announcements in the database.
        """
        now = datetime.utcnow()
        active_items = db.query(CorporateAnnouncement).filter(
            CorporateAnnouncement.status.in_(["NEW_ACTIVE", "DECAYING"])
        ).all()

        updated_count = 0
        for item in active_items:
            pub_time = item.source_published_at or item.publication_timestamp or item.ingested_at or now
            decayed, new_status = cls.calculate_decayed_score(
                raw_score=item.raw_materiality_score or 0.0,
                track_type=item.track_type or "TACTICAL",
                publication_time=pub_time,
                current_time=now
            )
            item.decayed_score = decayed
            item.status = new_status
            item.last_decay_update = now
            updated_count += 1

        if updated_count > 0:
            db.commit()
            logger.info(f"Updated decay status for {updated_count} corporate announcements.")

        return updated_count
