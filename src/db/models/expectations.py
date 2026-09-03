import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class MarketExpectation(Base):
    __tablename__ = "market_expectations"

    expectation_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    period_end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    # Consensus Estimates
    consensus_revenue: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    consensus_eps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    implied_pe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Actual Results (Filled after announcement)
    actual_revenue: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_eps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Expectation Gaps / Surprises
    revenue_surprise_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eps_surprise_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rerating_gap_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # -100 to +100
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company")

    __table_args__ = (
        Index("idx_expectation_lookup", "company_id", "period_end_date"),
    )
