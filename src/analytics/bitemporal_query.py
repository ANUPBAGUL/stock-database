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
        limit: int = 4
    ) -> List[BitemporalFinancial]:
        """
        Retrieves the exact financial statement records that were published and active
        at `as_of_date`.
        """
        query = db.query(BitemporalFinancial).filter(
            BitemporalFinancial.company_id == company_id,
            BitemporalFinancial.period_type == period_type,
            BitemporalFinancial.publication_date <= as_of_date,
            BitemporalFinancial.system_rec_start <= as_of_date,
            BitemporalFinancial.system_rec_end > as_of_date
        ).order_by(BitemporalFinancial.period_end_date.desc()).limit(limit)

        return query.all()
