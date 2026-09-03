"""
Automated Data Relevance, Information Half-Life & Lifecycle State Daemon.

Runs daily to:
1. Recalculate half-life decay scores for active regulatory filings.
2. Transition tactical announcements to ABSORBED_INTO_PRICE after 7 days.
3. Transition structural announcements to ABSORBED_INTO_FINANCIALS once quarterly XBRL statements report the capex/revenue.
4. Transition completed board meetings and release insider trading blackout windows.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session

from src.db.models import CorporateAnnouncement, BoardMeetingAnnouncement, BitemporalFinancial
from src.analytics.announcement_decay_engine import AnnouncementDecayEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("relevance_daemon")


class DataRelevanceDaemon:
    """
    Automated lifecycle and information absorption worker.
    """

    @classmethod
    def execute_maintenance_cycle(cls, db: Session) -> Dict[str, Any]:
        """
        Executes a full lifecycle relevance check and state transition cycle.
        """
        now = datetime.utcnow()
        today = date.today()
        logger.info(f"Starting Data Relevance Maintenance Cycle at {now.isoformat()}...")

        # 1. Transition Structural Events to ABSORBED_INTO_FINANCIALS if newer statements exist
        structural_announcements = db.query(CorporateAnnouncement).filter(
            CorporateAnnouncement.track_type == "STRUCTURAL",
            CorporateAnnouncement.status.in_(["NEW_ACTIVE", "DECAYING"])
        ).all()

        absorbed_financials_count = 0
        for sa in structural_announcements:
            # Check if at least 2 quarterly filings have been published post announcement
            post_filings_count = db.query(BitemporalFinancial).filter(
                BitemporalFinancial.company_id == sa.company_id,
                BitemporalFinancial.period_type == "QUARTERLY",
                BitemporalFinancial.publication_date > sa.publication_timestamp
            ).count()

            if post_filings_count >= 2:
                sa.status = "ABSORBED_INTO_FINANCIALS"
                absorbed_financials_count += 1
                logger.info(f"Announcement '{sa.headline[:40]}' transitioned to ABSORBED_INTO_FINANCIALS (superseded by {post_filings_count} quarterly statements).")

        if absorbed_financials_count > 0:
            db.commit()

        # 2. Update Decay Scores for remaining Active Announcements
        decay_count = AnnouncementDecayEngine.update_all_announcements_decay(db)

        # 3. Transition Completed Board Meetings & Unlock Trading Windows
        completed_bm = 0
        active_meetings = db.query(BoardMeetingAnnouncement).filter(
            BoardMeetingAnnouncement.urgency_status != "COMPLETED"
        ).all()

        for bm in active_meetings:
            days_until = (bm.meeting_date - today).days
            bm.days_until_meeting = days_until

            if days_until < 0:
                bm.urgency_status = "COMPLETED"
                # Trading window re-opens 48 hours post meeting date
                if (today - bm.meeting_date).days >= 2:
                    bm.blackout_period_active = False
                completed_bm += 1
            elif days_until <= 3:
                bm.urgency_status = "IMMINENT"
                bm.blackout_period_active = True
            else:
                bm.urgency_status = "SCHEDULED"
                bm.blackout_period_active = True

        db.commit()

        summary = {
            "timestamp": now.isoformat(),
            "decayed_announcements_updated": decay_count,
            "structural_absorbed_into_financials": absorbed_financials_count,
            "board_meetings_updated": len(active_meetings),
            "board_meetings_completed": completed_bm
        }
        logger.info(f"Data Relevance Maintenance Cycle finished: {summary}")
        return summary
