import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class ValuationSnapshot(Base):
    """
    Layer 5: Valuation State & Historical Percentiles — Stores comprehensive valuation state without reducing valuation to static P/E.
    """
    __tablename__ = "valuation_snapshots"

    valuation_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    observation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    publication_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    market_cap_cr: Mapped[float] = mapped_column(Float, nullable=False)
    enterprise_value_cr: Mapped[float] = mapped_column(Float, nullable=False)
    
    pe_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    forward_pe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pb_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ev_ebitda: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ev_sales: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    p_fcf: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fcf_yield_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    peg_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Historical Positioning (Valuation Percentile Bands)
    pe_1y_percentile: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pe_3y_percentile: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pe_5y_percentile: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ev_ebitda_percentile: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sector_relative_pe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="valuation_snapshots")

    __table_args__ = (
        Index("idx_val_pit_lookup", "company_id", "observation_date", "publication_timestamp"),
    )
