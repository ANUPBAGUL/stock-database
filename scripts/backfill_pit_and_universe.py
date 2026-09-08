"""
Point-In-Time States & Survivorship Universe Backfill Runner.

1. Seeds UniverseMembership records (including failure cohorts DHFL, SINTEX, RCOM).
2. Populates quarterly_pit_states for all active companies in multibagger.db.
"""

import os
import sys
import logging

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.db.base import SessionLocal
from src.db.models import Company, QuarterlyPITState
from src.analytics.quarterly_pit_builder import QuarterlyPITBuilder
from scripts.scale_historical_universe_backfill import BroadUniverseBackfiller

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill_pit_and_universe")


def run_backfill():
    db = SessionLocal()
    try:
        # 1. Seed universe memberships
        logger.info("Seeding Universe Memberships & Survivorship Control Cohorts...")
        BroadUniverseBackfiller.seed_universe_memberships(db)

        # 2. Build Quarterly PIT States for all active companies
        companies = db.query(Company).filter(
            Company.status == "ACTIVE",
            ~Company.company_id.like("test%"),
            ~Company.nse_symbol.like("%TEST%")
        ).all()

        logger.info(f"Populating Quarterly PIT States for {len(companies)} companies...")
        total_states = 0
        for comp in companies:
            try:
                states = QuarterlyPITBuilder.build_quarterly_states_for_company(db, comp.company_id)
                total_states += len(states)
                if states:
                    logger.info(f"[{comp.nse_symbol or comp.company_id}] Built {len(states)} PIT states.")
            except Exception as e:
                logger.error(f"[{comp.nse_symbol or comp.company_id}] Error building PIT states: {e}")

        logger.info(f"Successfully generated {total_states} Quarterly PIT records in quarterly_pit_states.")

    finally:
        db.close()


if __name__ == "__main__":
    run_backfill()
