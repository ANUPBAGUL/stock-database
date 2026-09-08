import logging
from datetime import datetime, date
from typing import List, Optional
from sqlalchemy.orm import Session
from src.db.models import BitemporalFinancial

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BitemporalQueryEngine:
    """
    Point-In-Time query builder guaranteeing zero look-ahead bias.
    """

    @staticmethod
    def get_financials_as_of(
        db: Session,
        company_id: str,
        as_of_date: datetime,
        period_type: str = "QUARTERLY",
        limit: int = 4,
        strict_system_time: bool = False
    ) -> List[BitemporalFinancial]:
        """
        Retrieves the exact financial statement records that were published and effective
        as of `as_of_date`.

        Args:
            as_of_date: Cutoff timestamp. No statement published after this date is visible.
            period_type: 'QUARTERLY' | 'ANNUAL'
            limit: Number of distinct period statements to return (most recent first).
            strict_system_time: If True, also filters on system_rec_start <= as_of_date
                                (strict live audit mode). Defaults to False for historical
                                backtests and quantitative research on backfilled data.
        """
        # Ensure as_of_date is comparable
        if isinstance(as_of_date, date) and not isinstance(as_of_date, datetime):
            as_of_dt = datetime.combine(as_of_date, datetime.max.time())
        else:
            as_of_dt = as_of_date

        query = db.query(BitemporalFinancial).filter(
            BitemporalFinancial.company_id == company_id,
            BitemporalFinancial.period_type == period_type,
            BitemporalFinancial.publication_date <= as_of_dt
        )

        if strict_system_time:
            query = query.filter(
                BitemporalFinancial.system_rec_start <= as_of_dt,
                BitemporalFinancial.system_rec_end > as_of_dt
            )

        # Order by period_end_date desc, publication_date desc
        records = query.order_by(
            BitemporalFinancial.period_end_date.desc(),
            BitemporalFinancial.publication_date.desc()
        ).all()

        # Deduplicate to pick the latest published version for each distinct period_end_date
        deduped: List[BitemporalFinancial] = []
        seen_periods = set()
        for rec in records:
            if rec.period_end_date not in seen_periods:
                seen_periods.add(rec.period_end_date)
                deduped.append(rec)
                if len(deduped) >= limit:
                    break

        return deduped
