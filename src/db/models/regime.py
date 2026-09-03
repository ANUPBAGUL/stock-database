import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from src.db.base import Base

class MarketRegimeHistory(Base):
    __tablename__ = "market_regime_history"

    regime_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    market_regime: Mapped[str] = mapped_column(String(30), nullable=False) # 'BULL', 'BEAR', 'SIDEWAYS'
    volatility_regime: Mapped[str] = mapped_column(String(30), default="NORMAL_VOL") # 'LOW_VOL', 'HIGH_VOL'
    liquidity_regime: Mapped[str] = mapped_column(String(30), default="EXPANDING") # 'EXPANDING', 'CONTRACTING'
    style_regime: Mapped[str] = mapped_column(String(50), default="QUALITY_GROWTH") # 'SMALL_CAP_MOMENTUM', 'QUALITY_GROWTH', 'VALUE'
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_regime_dates", "start_date", "end_date"),
    )
