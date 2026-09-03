#!/usr/bin/env python3
"""
Force Re-Ingest Script — Clears stale financial and shareholding data, then re-fetches.

Usage:
    python scripts/force_reingest.py POLYCAB
    python scripts/force_reingest.py HDFCBANK --dry-run

Purpose:
- Fixes data quality issues where stale records exist from before bug fixes
- Deletes BitemporalFinancial and Shareholding records for the given symbol
- Re-runs ingestion pipeline to fetch fresh data from yfinance and NSE

Use Cases:
- After fixing field mapping bugs (e.g., receivables → trade_receivables)
- After fixing shares_outstanding unit bugs (yfinance millions vs absolute)
- When consolidation_scope or other metadata needs refresh
"""

import sys
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from src.db.base import get_session
from src.db.models import Company, BitemporalFinancial, Shareholding
from src.ingestion.yfinance_client import YFinanceClient
from src.ingestion.bitemporal_ingest import BitemporalIngestor
from src.ingestion.shareholding_client import ShareholdingClient
from src.ingestion.nse_client import NseClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def force_reingest_symbol(nse_symbol: str, dry_run: bool = False):
    """
    Clear stale financial and shareholding data, then re-fetch.
    
    Args:
        nse_symbol: NSE symbol (e.g., "POLYCAB")
        dry_run: If True, show what would be deleted but don't execute
    """
    db: Session = next(get_session())
    
    try:
        # Step 1: Resolve company
        company = db.query(Company).filter_by(nse_symbol=nse_symbol).first()
        if not company:
            logger.error(f"Company with NSE symbol '{nse_symbol}' not found in database.")
            return
        
        company_id = company.company_id
        logger.info(f"Found company: {company.company_name} (ID: {company_id})")
        
        # Step 2: Count existing records
        fin_count = db.query(BitemporalFinancial).filter_by(company_id=company_id).count()
        sh_count = db.query(Shareholding).filter_by(company_id=company_id).count()
        
        logger.info(f"Found {fin_count} BitemporalFinancial records, {sh_count} Shareholding records")
        
        if dry_run:
            logger.info("[DRY RUN] Would delete the above records and re-fetch. Exiting.")
            return
        
        # Step 3: Delete stale records
        logger.info("Deleting stale BitemporalFinancial records...")
        db.query(BitemporalFinancial).filter_by(company_id=company_id).delete()
        
        logger.info("Deleting stale Shareholding records...")
        db.query(Shareholding).filter_by(company_id=company_id).delete()
        
        db.commit()
        logger.info("Stale data cleared.")
        
        # Step 4: Re-fetch financials from yfinance
        logger.info("Re-fetching quarterly financials from yfinance...")
        yf_client = YFinanceClient()
        yf_financials = yf_client.fetch_quarterly_financials(nse_symbol)
        
        if not yf_financials:
            logger.warning(f"No financial data returned from yfinance for {nse_symbol}")
        else:
            logger.info(f"Retrieved {len(yf_financials)} quarterly records from yfinance")
            
            # Ingest via BitemporalIngestor
            ingestor = BitemporalIngestor(db)
            ingestion_time = datetime.now(timezone.utc)
            
            for fin in yf_financials:
                ingestor.ingest_financial_record(
                    company_id=company_id,
                    metrics=fin,
                    publication_date=fin["publication_date"],
                    ingestion_time=ingestion_time,
                    data_source="yfinance",
                    quality_score=65  # yfinance baseline quality
                )
            
            db.commit()
            logger.info(f"Ingested {len(yf_financials)} financial records into BitemporalFinancial")
        
        # Step 5: Re-fetch shareholding from NSE
        logger.info("Re-fetching shareholding pattern from NSE...")
        nse_client = NseClient()
        sh_client = ShareholdingClient()
        
        try:
            sh_records = sh_client.fetch_and_store_shareholding(db, nse_client, nse_symbol, company_id)
            if sh_records:
                logger.info(f"Ingested {len(sh_records)} shareholding records")
            else:
                logger.warning(f"No shareholding data returned for {nse_symbol}")
        except Exception as e:
            logger.error(f"Error fetching shareholding: {e}")
        
        logger.info(f"✓ Force re-ingest complete for {nse_symbol}")
        
    except Exception as e:
        logger.error(f"Error during force re-ingest: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/force_reingest.py <NSE_SYMBOL> [--dry-run]")
        print("Example: python scripts/force_reingest.py POLYCAB")
        sys.exit(1)
    
    nse_symbol = sys.argv[1].upper()
    dry_run = "--dry-run" in sys.argv
    
    logger.info(f"Starting force re-ingest for {nse_symbol} (dry_run={dry_run})")
    force_reingest_symbol(nse_symbol, dry_run=dry_run)


if __name__ == "__main__":
    main()
