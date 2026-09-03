"""
Bitemporal Ingestion Engine.

Implements bi-temporal storage for financial statements with full restatement tracking.

BITEMPORAL TIMESTAMP DISCIPLINE:
  publication_date:   When the company/exchange originally published this filing.
                      For historical backfills via yfinance this is ESTIMATED.
  system_rec_start:   When OUR SYSTEM first recorded this fact.
                      For backfills: always datetime.utcnow() at ingest time.
                      NOT set to publication_date — that would misrepresent
                      when our system actually had access to the data.
  system_rec_end:     datetime(9999,12,31) for the currently active record.
                      Set to rec_start of the superseding record on restatement.

BACKFILL FLAG:
  is_backfill=True:   system_rec_start was set to ingestion time, not publication_date.
                      PIT queries must account for this when reasoning about
                      "what did the system know at time T?"
"""

import logging
from datetime import date, datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from src.db.models import BitemporalFinancial, Company
from src.ingestion.validator import DataValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BitemporalIngestionEngine:
    """
    Ingests financial statement records with bi-temporal protection.
    Prevents look-ahead bias and tracks restatements accurately.
    """

    @staticmethod
    def ingest_financial_record(
        db: Session,
        company_id: str,
        period_type: str,       # 'QUARTERLY', 'ANNUAL', 'TTM'
        period_end_date: date,
        publication_date: datetime,
        source: str,
        metrics: Dict[str, Any],
        raw_payload: Optional[Dict[str, Any]] = None,
        system_rec_start: Optional[datetime] = None,
        is_backfill: bool = True,           # True for historical data ingested retroactively
        source_quality: str = "ESTIMATED_PUB_DATE",  # ACTUAL_NSE_FILING | ESTIMATED_PUB_DATE
        consolidation_scope: str = "YFINANCE_UNVERIFIED",
    ) -> BitemporalFinancial:
        """
        Ingest a financial statement record into the bitemporal store.

        Args:
            system_rec_start: When THIS SYSTEM first ingested the record.
                              If None: defaults to datetime.utcnow() (current ingest time).
                              For historical backfills, this is NOT set to publication_date
                              because we didn't actually have this data on that date.
            is_backfill: True when the record is being retroactively backfilled.
                         False when ingested live at the time of publication.
            source_quality: ACTUAL_NSE_FILING when pub_date comes from NSE API directly.
                            ESTIMATED_PUB_DATE when pub_date is approximated (yfinance path).
        """
        # Validate balance sheet double-entry where possible
        is_valid, msg = DataValidator.validate_balance_sheet(metrics)
        if not is_valid:
            logger.warning(f"[BitemporalIngest] Balance sheet warning | company={company_id} period={period_end_date}: {msg}")

        # system_rec_start = ingestion time, NOT publication_date.
        # For backfills we record when we actually stored this, not when it was published.
        rec_start = system_rec_start or datetime.utcnow()

        # Check for existing active record for this (company, period_type, period_end_date)
        existing_active = db.query(BitemporalFinancial).filter(
            BitemporalFinancial.company_id == company_id,
            BitemporalFinancial.period_type == period_type,
            BitemporalFinancial.period_end_date == period_end_date,
            BitemporalFinancial.system_rec_end >= rec_start
        ).first()

        is_restatement = False
        if existing_active:
            logger.info(
                f"[BitemporalIngest] Restatement detected | company={company_id} "
                f"period={period_end_date}. Closing old record (system_rec_end={rec_start})."
            )
            existing_active.system_rec_end = rec_start
            is_restatement = True

        new_record = BitemporalFinancial(
            company_id=company_id,
            period_type=period_type,
            period_end_date=period_end_date,
            publication_date=publication_date,
            system_rec_start=rec_start,
            system_rec_end=datetime(9999, 12, 31, 23, 59, 59),
            is_restatement=is_restatement,
            source=source,
            # Income statement
            revenue=metrics.get("revenue"),
            ebitda=metrics.get("ebitda"),
            ebit=metrics.get("ebit"),
            pat=metrics.get("pat"),
            eps=metrics.get("eps"),
            # Cash flow
            operating_cash_flow=metrics.get("operating_cash_flow"),
            capex=metrics.get("capex"),
            # Balance sheet — full primitives
            total_debt=metrics.get("total_debt"),
            cash_and_equivalents=metrics.get("cash_and_equivalents"),
            total_assets=metrics.get("total_assets"),
            total_liabilities=metrics.get("total_liabilities"),
            net_worth=metrics.get("net_worth"),
            shares_outstanding=metrics.get("shares_outstanding"),
            trade_receivables=metrics.get("trade_receivables"),
            current_liabilities=metrics.get("current_liabilities"),
            # Debt disaggregation (Fix 3 schema fields)
            financial_debt_lt=metrics.get("financial_debt_lt"),
            financial_debt_st=metrics.get("financial_debt_st"),
            lease_liabilities_lt=metrics.get("lease_liabilities_lt"),
            lease_liabilities_st=metrics.get("lease_liabilities_st"),
            current_investments=metrics.get("current_investments"),
            net_debt=metrics.get("net_debt"),
            # Consolidation and provenance
            consolidation_scope=metrics.get("consolidation_scope", consolidation_scope),
            raw_payload=raw_payload or metrics
        )

        db.add(new_record)
        db.commit()
        db.refresh(new_record)

        logger.info(
            f"[BitemporalIngest] Stored financial_id={new_record.financial_id} | "
            f"company={company_id} period={period_end_date} source={source} "
            f"scope={new_record.consolidation_scope} quality={source_quality} "
            f"backfill={is_backfill} restatement={is_restatement}"
        )
        return new_record
