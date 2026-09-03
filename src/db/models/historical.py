import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, Float, Integer, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class HistoricalMultibaggerCase(Base):
    __tablename__ = "historical_multibagger_dataset"

    case_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    tag: Mapped[str] = mapped_column(String(30), nullable=False) # 'WINNER_10X', 'WINNER_5X', 'WINNER_2X', 'FALSE_POSITIVE', 'VALUE_TRAP', 'HIGH_GROWTH_CRASH'
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    initial_market_cap_crores: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    peak_return_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    final_return_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_drawdown_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    time_to_2x_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    time_to_5x_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    time_to_10x_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    drawdown_before_breakout_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    primary_catalysts: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    pre_breakout_fingerprint: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company")
