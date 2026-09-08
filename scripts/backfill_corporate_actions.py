"""
Script to backfill Corporate Actions (Splits, Bonuses, Dividends) for all companies
in multibagger.db using YFinanceClient and recalculate cumulative price adjustment factors.
"""

import sys
import os
import logging
from datetime import date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.db.base import SessionLocal
from src.db.models import Company, CorporateAction
from src.ingestion.yfinance_client import YFinanceClient
from src.ingestion.corporate_actions import CorporateActionEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def backfill_all_corporate_actions():
    db = SessionLocal()
    client = YFinanceClient(rate_limit_seconds=0.2)
    try:
        companies = db.query(Company).filter(Company.nse_symbol.isnot(None)).all()
        logger.info(f"Starting corporate action backfill for {len(companies)} companies...")

        total_actions_added = 0
        for comp in companies:
            symbol = comp.nse_symbol
            if not symbol:
                continue
            try:
                actions = client.fetch_corporate_actions(symbol)
                for act in actions:
                    CorporateActionEngine.add_corporate_action(
                        db=db,
                        company_id=comp.company_id,
                        ex_date=act["ex_date"],
                        action_type=act["action_type"],
                        old_shares=act["old_shares"],
                        new_shares=act["new_shares"],
                        dividend_amount=act.get("dividend_amount", 0.0),
                        description=act.get("description", "")
                    )
                    total_actions_added += 1

                # Recalculate cumulative factors
                CorporateActionEngine.calculate_cumulative_factors(db, comp.company_id)
                logger.info(f"Processed {symbol}: {len(actions)} actions found and cumulative factors calculated.")
            except Exception as e:
                logger.error(f"Failed processing corporate actions for {symbol}: {e}")

        logger.info(f"Backfill complete! Processed {len(companies)} companies, {total_actions_added} corporate action entries.")
    finally:
        db.close()

if __name__ == "__main__":
    backfill_all_corporate_actions()
