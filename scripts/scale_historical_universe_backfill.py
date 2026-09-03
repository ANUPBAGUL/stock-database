"""
Broad Historical Universe Backfill & Survivorship Dataset Expansion Engine.
Expands the Point-in-Time research dataset across broad Indian equities (Nifty 500, Smallcap, Failures).
Populates:
1. UniverseMembership records (active constituents + historical delistings/failures)
2. 10-year quarterly bitemporal statements (XBRL)
3. Historical T0 ResearchFeatureSnapshot vectors with full provenance & deterministic canonical hashes
4. Compounded wealth forward outcomes with generic interval metadata
"""
import os
import sys
import uuid
import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.db.base import SessionLocal
from src.db.models import Company, Sector, UniverseMembership
from src.analytics.historical_pit_replay import HistoricalPITReplayEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("UniverseScaleBackfill")

# Broad multi-sector cohort including market leaders, smallcaps, cyclical turnarounds, and historical failure control cases
EXPANDED_UNIVERSE_SEED = [
    # Technology & IT Services
    {"symbol": "INFY", "name": "Infosys Limited", "sector": "Technology & Services", "universe": "NIFTY_500", "status": "ACTIVE"},
    {"symbol": "WIPRO", "name": "Wipro Limited", "sector": "Technology & Services", "universe": "NIFTY_500", "status": "ACTIVE"},
    {"symbol": "HCLTECH", "name": "HCL Technologies Limited", "sector": "Technology & Services", "universe": "NIFTY_500", "status": "ACTIVE"},
    {"symbol": "KPITTECH", "name": "KPIT Technologies Limited", "sector": "Technology & Services", "universe": "NIFTY_500", "status": "ACTIVE"},
    {"symbol": "COFORGE", "name": "Coforge Limited", "sector": "Technology & Services", "universe": "NIFTY_500", "status": "ACTIVE"},

    # EMS & Electronics Manufacturing
    {"symbol": "AMBER", "name": "Amber Enterprises India Ltd", "sector": "Consumer Discretionary", "universe": "NIFTY_500", "status": "ACTIVE"},
    {"symbol": "SYRMA", "name": "Syrma SGS Technology Ltd", "sector": "Consumer Discretionary", "universe": "NIFTY_500", "status": "ACTIVE"},
    {"symbol": "PGEL", "name": "PG Electroplast Limited", "sector": "Consumer Discretionary", "universe": "NIFTY_SMALLCAP_250", "status": "ACTIVE"},

    # Pharmaceuticals & Specialty Chemicals
    {"symbol": "CIPLA", "name": "Cipla Limited", "sector": "Healthcare & Pharma", "universe": "NIFTY_500", "status": "ACTIVE"},
    {"symbol": "SUNPHARMA", "name": "Sun Pharmaceutical Ind Ltd", "sector": "Healthcare & Pharma", "universe": "NIFTY_500", "status": "ACTIVE"},
    {"symbol": "NEULANDLAB", "name": "Neuland Laboratories Ltd", "sector": "Healthcare & Pharma", "universe": "NIFTY_SMALLCAP_250", "status": "ACTIVE"},
    {"symbol": "DEEPAKNTR", "name": "Deepak Nitrite Limited", "sector": "Materials & Metals", "universe": "NIFTY_500", "status": "ACTIVE"},
    {"symbol": "AARTIIND", "name": "Aarti Industries Limited", "sector": "Materials & Metals", "universe": "NIFTY_500", "status": "ACTIVE"},

    # Industrials, Capital Goods & Defense
    {"symbol": "HAL", "name": "Hindustan Aeronautics Ltd", "sector": "Industrials & Capital Goods", "universe": "NIFTY_500", "status": "ACTIVE"},
    {"symbol": "BEL", "name": "Bharat Electronics Limited", "sector": "Industrials & Capital Goods", "universe": "NIFTY_500", "status": "ACTIVE"},
    {"symbol": "POLYCAB", "name": "Polycab India Limited", "sector": "Industrials & Capital Goods", "universe": "NIFTY_500", "status": "ACTIVE"},
    {"symbol": "KEI", "name": "KEI Industries Limited", "sector": "Industrials & Capital Goods", "universe": "NIFTY_500", "status": "ACTIVE"},

    # Consumer Staples & Discretionary
    {"symbol": "TITAN", "name": "Titan Company Limited", "sector": "Consumer Discretionary", "universe": "NIFTY_500", "status": "ACTIVE"},
    {"symbol": "TRENT", "name": "Trent Limited", "sector": "Consumer Discretionary", "universe": "NIFTY_500", "status": "ACTIVE"},
    {"symbol": "VARUN", "name": "Varun Beverages Limited", "sector": "Consumer Staples", "universe": "NIFTY_500", "status": "ACTIVE"},

    # Historical Failures, Bankruptcies & Cyclical Peaks (SURVIVORSHIP CONTROL COHORT)
    {"symbol": "DHFL", "name": "Dewan Housing Finance Corp Ltd", "sector": "Banking & Financials", "universe": "HISTORICAL_FAILURES", "status": "BANKRUPTCY", "from_year": 2015, "to_year": 2019},
    {"symbol": "SINTEX", "name": "Sintex Industries Limited", "sector": "Materials & Metals", "universe": "HISTORICAL_FAILURES", "status": "BANKRUPTCY", "from_year": 2015, "to_year": 2020},
    {"symbol": "RCOM", "name": "Reliance Communications Limited", "sector": "Technology & Services", "universe": "HISTORICAL_FAILURES", "status": "DELISTED", "from_year": 2015, "to_year": 2018},
    {"symbol": "UNITECH", "name": "Unitech Limited", "sector": "Industrials & Capital Goods", "universe": "HISTORICAL_FAILURES", "status": "SUSPENDED", "from_year": 2015, "to_year": 2021},
    {"symbol": "GTLINFRA", "name": "GTL Infrastructure Limited", "sector": "Technology & Services", "universe": "HISTORICAL_FAILURES", "status": "ACTIVE", "from_year": 2015, "to_year": 2025}
]

class BroadUniverseBackfiller:
    """
    Seeds universe membership and executes multi-year PIT trajectory reconstruction.
    """

    @classmethod
    def seed_universe_memberships(cls, db):
        logger.info("Seeding Historical Universe Memberships...")
        for item in EXPANDED_UNIVERSE_SEED:
            sym = item["symbol"]
            sec_name = item["sector"]

            # Ensure sector
            sec = db.query(Sector).filter_by(sector_name=sec_name).first()
            if not sec:
                sec = Sector(sector_id=str(uuid.uuid4()), sector_name=sec_name)
                db.add(sec)
                db.flush()

            # Ensure company
            comp = db.query(Company).filter(
                (Company.nse_symbol == sym) | (Company.company_name == item["name"])
            ).first()

            if not comp:
                comp = Company(
                    company_id=str(uuid.uuid4()),
                    isin=f"INE{hash(sym) % 1000000000:09d}",
                    nse_symbol=sym,
                    company_name=item["name"],
                    sector_id=sec.sector_id,
                    industry=sec_name,
                    listing_status=item.get("status", "ACTIVE"),
                    tradability_status="TRADABLE" if item.get("status") == "ACTIVE" else "SUSPENDED",
                    liquidity_status="HIGH" if item.get("universe") == "NIFTY_500" else "LOW",
                    research_eligibility="ELIGIBLE"
                )
                db.add(comp)
                db.flush()

            # Add UniverseMembership record if missing
            u_mem = db.query(UniverseMembership).filter_by(
                company_id=comp.company_id,
                universe_name=item["universe"]
            ).first()

            if not u_mem:
                from_date = date(item.get("from_year", 2016), 1, 1)
                to_date = date(item["to_year"], 12, 31) if "to_year" in item else None
                u_mem = UniverseMembership(
                    membership_id=str(uuid.uuid4()),
                    company_id=comp.company_id,
                    symbol=sym,
                    universe_name=item["universe"],
                    effective_from=from_date,
                    effective_to=to_date,
                    listing_status=item.get("status", "ACTIVE"),
                    tradability_status="TRADABLE" if item.get("status") == "ACTIVE" else "SUSPENDED",
                    liquidity_status="HIGH" if item.get("universe") == "NIFTY_500" else "LOW",
                    research_eligibility="ELIGIBLE",
                    inclusion_reason="SURVIVORSHIP_FREE_INDEX_OR_FAILURE_SEED"
                )
                db.add(u_mem)

        db.commit()
        logger.info(f"Seeded {len(EXPANDED_UNIVERSE_SEED)} universe membership profiles.")

    @classmethod
    def execute_trajectory_backfills(cls, max_companies: int = 15):
        db = SessionLocal()
        try:
            cls.seed_universe_memberships(db)

            # Ingest and replay trajectories for active companies
            active_members = db.query(UniverseMembership).filter(
                UniverseMembership.universe_name.in_(["NIFTY_500", "NIFTY_SMALLCAP_250"])
            ).limit(max_companies).all()

            logger.info(f"Starting historical PIT replay across {len(active_members)} broad universe stocks...")
            completed = 0
            for mem in active_members:
                sym = mem.symbol
                logger.info(f"[{completed+1}/{len(active_members)}] Backfilling PIT trajectory for {sym}...")
                try:
                    res = HistoricalPITReplayEngine.backfill_company_historical_trajectory(sym, db)
                    logger.info(f"  -> {sym}: {res.get('research_feature_snapshots_created')} snapshots, {res.get('forward_outcomes_linked')} outcomes.")
                    completed += 1
                except Exception as e:
                    logger.warning(f"  -> {sym} backfill error: {e}")

            logger.info("Broad universe backfill batch completed!")
        finally:
            db.close()

if __name__ == "__main__":
    BroadUniverseBackfiller.execute_trajectory_backfills(max_companies=10)
