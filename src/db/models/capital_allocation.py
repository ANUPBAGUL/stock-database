import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class CapitalAllocationEvent(Base):
    """
    Layer 5: Capital Allocation & Dilution Database — Tracks major deployment of corporate capital, share issuance, QIPs, and buybacks.
    """
    __tablename__ = "capital_allocation_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    publication_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    allocation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # 'CAPEX', 'ACQUISITION', 'DIVIDEND', 'BUYBACK', 'DEBT_REPAYMENT', 'QIP_EQUITY_RAISE', 'PREFERENTIAL_ISSUE', 'ESOP_DILUTION'
    
    amount_cr: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # INR Crores
    shares_issued: Mapped[float] = mapped_column(Float, default=0.0) # Number of shares issued or bought back
    dilution_pct: Mapped[float] = mapped_column(Float, default=0.0) # Equity dilution % (+ve for issuance, -ve for buyback)
    
    funding_source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True) # 'INTERNAL_ACCRUALS', 'DEBT', 'EQUITY_DILUTION'
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_document: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="capital_allocation_events")

    __table_args__ = (
        Index("idx_cap_alloc_pit", "company_id", "event_date", "publication_timestamp"),
    )
