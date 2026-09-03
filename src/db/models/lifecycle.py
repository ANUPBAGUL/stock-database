import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, Float, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class CompanyLifecycleHistory(Base):
    """
    Layer 4: 8-Stage Company Growth Lifecycle Dataset.
    Tracks what lifecycle stage a business occupied at T0:
    1_EARLY_SMALL, 2_SCALING, 3_RAPID_EARNINGS_EXPANSION, 4_OPERATING_LEVERAGE,
    5_INSTITUTIONAL_DISCOVERY, 6_RERATING, 7_MATURE, 8_DECLINING.
    """
    __tablename__ = "company_lifecycle_history"

    lifecycle_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    observation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    publication_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    # '1_EARLY_SMALL', '2_SCALING', '3_RAPID_EARNINGS_EXPANSION', '4_OPERATING_LEVERAGE',
    # '5_INSTITUTIONAL_DISCOVERY', '6_RERATING', '7_MATURE', '8_DECLINING'
    
    stage_numeric_order: Mapped[int] = mapped_column(Integer, nullable=False) # 1 to 8
    transition_trigger: Mapped[Optional[str]] = mapped_column(String(128), nullable=True) # e.g. 'CAPEX_COMMISSIONING_DRIVING_OPERATING_LEVERAGE'
    
    market_cap_cr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roce_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    revenue_growth_yoy_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    institutional_stake_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    stage_confidence: Mapped[float] = mapped_column(Float, default=1.00)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="lifecycle_history")

    __table_args__ = (
        Index("idx_lifecycle_pit", "company_id", "observation_date", "publication_timestamp"),
    )
