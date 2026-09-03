import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class ShareholdingHistory(Base):
    """
    Layer 6: Governance & Ownership Database — Detailed quarterly tracking of Promoter, Pledge, FII, DII, Mutual Funds, and Public ownership trajectories.
    """
    __tablename__ = "shareholding_history"

    shareholding_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    period_end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True) # Quarter end date (e.g., 2026-06-30)
    publication_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True) # Official filing timestamp
    
    promoter_holding_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    promoter_pledge_pct: Mapped[Optional[float]] = mapped_column(Float, default=0.0)
    fii_holding_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)       # Direct NSE SEBI LODR field
    dii_holding_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)       # Total DII (MF + Other DII)
    mf_holding_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)        # Mutual Funds sub-category of DII
    other_dii_holding_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # Insurance, pension, banks (DII ex-MF)
    retail_public_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Source authority and data quality classification
    governance_risk_flag: Mapped[str] = mapped_column(String(32), default="CLEAN") # CLEAN, HIGH_PLEDGE_RISK, LOW_PROMOTER_SKIN_IN_GAME, RAPID_PROMOTER_EXIT
    source: Mapped[str] = mapped_column(String(64), default="NSE_SEBI_LODR_SHAREHOLDING_PATTERN")
    consolidation_scope: Mapped[str] = mapped_column(String(48), default="SEBI_LODR_PATTERN_FILING") # SEBI_LODR_PATTERN_FILING, YFINANCE_APPROXIMATE, UNKNOWN
    data_quality_flag: Mapped[str] = mapped_column(String(32), default="HIGH_CONFIDENCE") # HIGH_CONFIDENCE, LOW_CONFIDENCE, NO_DATA
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="shareholding_history")

    __table_args__ = (
        Index("idx_sh_pit_lookup", "company_id", "period_end_date", "publication_timestamp"),
    )


class GovernanceEvent(Base):
    """
    Layer 6: Management & Governance Event Log — Key management transitions, auditor resignations, related-party transactions, litigations.
    """
    __tablename__ = "governance_events"

    gov_event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    publication_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # 'CEO_APPOINTMENT', 'CEO_RESIGNATION', 'CFO_CHANGE', 'AUDITOR_RESIGNATION', 'AUDIT_QUALIFICATION', 'RELATED_PARTY_TRANSACTION', 'REGULATORY_ACTION', 'RESTATEMENT'
    
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    materiality_level: Mapped[str] = mapped_column(String(32), default="MEDIUM") # LOW, MEDIUM, HIGH, CRITICAL
    
    source_document: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    document_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True) # SHA-256 for audit provenance
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="governance_events")

    __table_args__ = (
        Index("idx_gov_event_lookup", "company_id", "event_date", "publication_timestamp"),
    )
