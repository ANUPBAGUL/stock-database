"""
Database Migration: Populate Authentic Face Values & Recompute Market Caps.

Queries Screener.in for authentic face values of all active companies in multibagger.db,
updates Company.face_value, and logs the reconciled market cap and P/E ratio.
"""

import os
import sys
import logging
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.db.base import SessionLocal
from src.db.models import Company, BitemporalFinancial, DailyPriceRaw
from src.ingestion.screener_client import ScreenerClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate_face_values")


def migrate_face_values():
    db = SessionLocal()
    sc = ScreenerClient()

    try:
        companies = db.query(Company).filter(
            ~Company.company_id.like("test%"),
            ~Company.company_id.like("comp_test%"),
            ~Company.nse_symbol.like("%TEST%")
        ).all()

        logger.info(f"Starting Face Value migration for {len(companies)} active companies...")
        updated_count = 0

        for comp in companies:
            sym = comp.nse_symbol or comp.bse_code
            if not sym:
                continue

            try:
                overview = sc.fetch_company_overview(sym)
                fv = overview.get("face_value") if overview else None

                if fv and float(fv) > 0:
                    old_fv = float(comp.face_value or 10.0)
                    new_fv = float(fv)
                    if abs(old_fv - new_fv) > 0.01:
                        comp.face_value = new_fv
                        db.commit()
                        logger.info(f"[{sym}] Updated Face Value: {old_fv} -> {new_fv}")
                        updated_count += 1
                    else:
                        logger.info(f"[{sym}] Face Value already correct ({new_fv})")
                else:
                    logger.warning(f"[{sym}] Could not find face value in overview; keeping {comp.face_value}")

                time.sleep(0.3)  # Gentle rate limiting
            except Exception as e:
                logger.error(f"[{sym}] Error fetching overview: {e}")

        logger.info(f"Face Value Migration Complete! Updated {updated_count} companies.")

    finally:
        db.close()


if __name__ == "__main__":
    migrate_face_values()
