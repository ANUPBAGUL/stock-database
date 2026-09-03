import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class SectorState(Base):
    __tablename__ = "sector_states"

    state_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sector_id: Mapped[str] = mapped_column(String(36), ForeignKey("sectors.sector_id"), nullable=False, index=True)
    
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    price_momentum_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # 0 to 100
    earnings_momentum_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # 0 to 100
    valuation_percentile: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # 0 to 100
    breadth_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # % stocks above 200 SMA
    
    policy_tailwind_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    commodity_impact_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    sector_cycle_stage: Mapped[str] = mapped_column(String(30), default="ACCELERATION") # 'EARLY_RECOVERY', 'ACCELERATION', 'PEAK', 'DOWNTURN'
    overall_sector_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sector: Mapped["Sector"] = relationship("Sector")

    __table_args__ = (
        Index("idx_sector_state_lookup", "sector_id", "as_of_date"),
    )
