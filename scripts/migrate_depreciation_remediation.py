"""
Migration Script: Backfill and Remediate Depreciation in BitemporalFinancial records.
"""
import sys
import os
import logging

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.db.base import SessionLocal
from src.db.models import BitemporalFinancial, Company
from src.ingestion.screener_client import ScreenerClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DepreciationMigration")

def remediate_depreciation():
    db = SessionLocal()
    try:
        records = db.query(BitemporalFinancial).filter(BitemporalFinancial.depreciation.is_(None)).all()
        logger.info(f"Found {len(records)} financial records with null depreciation.")

        updated_from_ebit = 0
        updated_from_payload = 0
        
        for f in records:
            # 1. Try from raw payload
            raw = f.raw_payload or {}
            depr_raw = raw.get("depreciation") or raw.get("depreciation_cr")
            if depr_raw is not None and float(depr_raw) >= 0:
                f.depreciation = round(float(depr_raw), 2)
                updated_from_payload += 1
                continue

            # 2. Derive from EBITDA - EBIT if both are valid numbers and ebitda >= ebit
            if f.ebitda is not None and f.ebit is not None:
                diff = round(f.ebitda - f.ebit, 2)
                if diff >= 0:
                    f.depreciation = diff
                    updated_from_ebit += 1

        db.commit()
        logger.info(f"Remediation Complete: {updated_from_payload} updated from raw payload, {updated_from_ebit} derived from (EBITDA - EBIT).")

        remaining = db.query(BitemporalFinancial).filter(BitemporalFinancial.depreciation.is_(None)).count()
        logger.info(f"Remaining records with null depreciation: {remaining}")

    finally:
        db.close()

if __name__ == "__main__":
    remediate_depreciation()
