import json
import logging
from datetime import date
from pathlib import Path
from src.db.base import SessionLocal
from src.db.models import Sector, Company

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "universe_500.json"

def seed_universe():
    if not DATA_PATH.exists():
        logger.error(f"Seed data file not found at {DATA_PATH}")
        return

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    db = SessionLocal()
    try:
        # Collect distinct sectors
        sectors_map = {}
        for item in data:
            sec_name = item.get("sector", "Unclassified")
            if sec_name not in sectors_map:
                existing_sec = db.query(Sector).filter_by(sector_name=sec_name).first()
                if not existing_sec:
                    new_sec = Sector(sector_name=sec_name)
                    db.add(new_sec)
                    db.flush()
                    sectors_map[sec_name] = new_sec.sector_id
                else:
                    sectors_map[sec_name] = existing_sec.sector_id

        # Insert companies
        added_count = 0
        for item in data:
            isin = item["isin"]
            existing = db.query(Company).filter_by(isin=isin).first()
            if not existing:
                # Parse listing_date from JSON if available
                listing_dt = None
                if item.get("listing_date"):
                    try:
                        listing_dt = date.fromisoformat(item["listing_date"])
                    except (ValueError, TypeError):
                        listing_dt = None

                company = Company(
                    isin=isin,
                    nse_symbol=item.get("nse_symbol"),
                    bse_code=item.get("bse_code"),
                    company_name=item["company_name"],
                    sector_id=sectors_map.get(item.get("sector", "Unclassified")),
                    industry=item.get("industry"),
                    listing_date=listing_dt,
                    status="ACTIVE"
                )
                db.add(company)
                added_count += 1

        db.commit()
        logger.info(f"Successfully seeded {added_count} companies into the universe!")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding universe: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_universe()
