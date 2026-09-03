"""
Corporate Action Engine — Manages stock splits, bonuses, rights issues,
and calculates cumulative price adjustment factors.

Factor Convention:
- price_factor = old_shares / new_shares (e.g., 1/5 = 0.20 for a 1:5 split)
- share_factor = new_shares / old_shares (e.g., 5/1 = 5.0 for a 1:5 split)
- cum_factor = cumulative product of price_factors for all future actions
  (i.e., multiply pre-ex-date prices by cum_factor to get adjusted prices)

DUPLICATE GUARD:
  Each (company_id, ex_date, action_type) combination is unique.
  add_corporate_action() performs an UPSERT — if the same action already exists,
  it updates the description and factors instead of inserting a duplicate.
  Duplicate splits would corrupt cum_factor by compounding it twice.
"""

import logging
from datetime import date
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from src.db.models import CorporateAction, Company

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CorporateActionEngine:
    """
    Calculates cumulative price adjustment factors for stock splits, bonuses, and rights issues.

    Rule:
    If a company undergoes a 1:5 split (1 old share becomes 5 new shares) on Ex-Date T:
    - price_factor = 1 / 5 = 0.20
    - All prices BEFORE Ex-Date T are multiplied by 0.20
    - All share counts BEFORE Ex-Date T are divided by 0.20 (multiplied by 5.0)
    - Prices ON or AFTER Ex-Date T remain unadjusted (Factor = 1.0)
    """

    PRICE_AFFECTING_ACTIONS = ['SPLIT', 'BONUS', 'RIGHTS']

    @classmethod
    def calculate_cumulative_factors(cls, db: Session, company_id: str) -> None:
        """
        Recalculate cumulative adjustment factors for all corporate actions of a company.

        The cum_factor for each action represents the cumulative product of price_factors
        for that action and all actions with LATER ex_dates. This is what you multiply
        pre-action prices by to bring them to the latest adjusted basis.
        """
        actions = db.query(CorporateAction).filter(
            CorporateAction.company_id == company_id,
            CorporateAction.action_type.in_(cls.PRICE_AFFECTING_ACTIONS)
        ).order_by(CorporateAction.ex_date.desc()).all()

        if not actions:
            return

        running_factor = 1.0
        for action in actions:
            if action.price_factor and action.price_factor > 0:
                running_factor *= action.price_factor
            action.cum_factor = running_factor

        db.commit()
        logger.info(f"[CorporateAction] Updated cumulative factors for company_id={company_id} ({len(actions)} actions)")

    @staticmethod
    def add_corporate_action(
        db: Session,
        company_id: str,
        ex_date: date,
        action_type: str,
        old_shares: float = 1.0,
        new_shares: float = 1.0,
        announcement_date: Optional[date] = None,
        record_date: Optional[date] = None,
        dividend_amount: float = 0.0,
        description: str = ""
    ) -> CorporateAction:
        """
        Add or update a corporate action, then recalculate cumulative factors.

        UPSERT GUARD: Checks for an existing (company_id, ex_date, action_type) record
        before inserting. If found, updates description and factors only.
        This prevents double-compounding of cum_factor when the same backfill runs twice.
        """
        price_factor = old_shares / new_shares if new_shares > 0 else 1.0
        share_factor = new_shares / old_shares if old_shares > 0 else 1.0

        # Upsert guard: never insert a duplicate (company_id, ex_date, action_type)
        existing = db.query(CorporateAction).filter(
            CorporateAction.company_id == company_id,
            CorporateAction.ex_date == ex_date,
            CorporateAction.action_type == action_type,
        ).first()

        if existing:
            logger.info(
                f"[CorporateAction] Duplicate detected for company={company_id} "
                f"ex_date={ex_date} type={action_type}. Updating in-place."
            )
            existing.old_shares = old_shares
            existing.new_shares = new_shares
            existing.price_factor = price_factor
            existing.share_factor = share_factor
            existing.dividend_amount = dividend_amount
            existing.description = description or existing.description
            if announcement_date:
                existing.announcement_date = announcement_date
            if record_date:
                existing.record_date = record_date
            db.commit()
            action = existing
        else:
            action = CorporateAction(
                company_id=company_id,
                announcement_date=announcement_date,
                ex_date=ex_date,
                record_date=record_date,
                action_type=action_type,
                old_shares=old_shares,
                new_shares=new_shares,
                price_factor=price_factor,
                share_factor=share_factor,
                dividend_amount=dividend_amount,
                description=description
            )
            db.add(action)
            db.commit()

        # Recalculate cumulative factors for all actions of this company
        CorporateActionEngine.calculate_cumulative_factors(db, company_id)
        return action
