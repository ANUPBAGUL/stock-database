"""
Research Eligibility & PIT Data Completeness Model.
First-class gatekeeper enforcing data depth and completeness before any company
can enter the M6 live decision stream or the M7 supervised training dataset.
"""
import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, String, Float, Integer, Date, DateTime, Boolean, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship

from src.db.base import Base

class ResearchEligibility(Base):
    __tablename__ = "research_eligibility"

    id = Column(Integer, primary_key=True, autoincrement=True)
    eligibility_id = Column(String(64), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    as_of_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Dimensional Completeness Scores (0 to 100)
    financial_history_score = Column(Float, nullable=False, default=0.0)      # Quarters of continuous audited statements
    price_history_score = Column(Float, nullable=False, default=0.0)          # Trading days of continuous unadjusted OHLCV
    shareholding_history_score = Column(Float, nullable=False, default=0.0)   # Continuous quarters of SEBI shareholding
    announcement_history_score = Column(Float, nullable=False, default=0.0)   # Official filings lineage
    valuation_history_score = Column(Float, nullable=False, default=0.0)      # Historical P/E, P/B, EV/EBITDA coverage
    governance_history_score = Column(Float, nullable=False, default=0.0)     # Auditor/board transition logging
    source_provenance_score = Column(Float, nullable=False, default=100.0)    # 100% = zero proxies, all regulatory/XBRL

    # Synthetic Overall Completeness Index
    pit_completeness_pct = Column(Float, nullable=False, default=0.0)         # 0 to 100%
    available_quarters_count = Column(Integer, nullable=False, default=0)
    available_price_days_count = Column(Integer, nullable=False, default=0)
    available_sh_quarters_count = Column(Integer, nullable=False, default=0)

    # Gatekeeper Eligibility Flags
    eligible_for_m6_live = Column(Boolean, nullable=False, default=False)
    eligible_for_m7_training = Column(Boolean, nullable=False, default=False)
    
    # Detailed Diagnostic String
    quarantine_status = Column(String(64), nullable=False, default="UNVERIFIED") 
    # Values: FULLY_ELIGIBLE | QUARANTINED_INSUFFICIENT_FINANCIALS | QUARANTINED_MISSING_PRICE | QUARANTINED_UNPROVEN_SOURCE
    quarantine_reasons = Column(JSON, nullable=True) # List of specific missing invariants

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_research_eligibility_lookup", "company_id", "as_of_timestamp"),
    )
