import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, Float, Boolean, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class AIPrediction(Base):
    __tablename__ = "ai_predictions"

    prediction_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    prediction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    target_horizon: Mapped[str] = mapped_column(String(20), nullable=False) # '6M', '1Y', '3Y', '5Y'
    
    predicted_conviction_score: Mapped[int] = mapped_column(Float, nullable=False)
    predicted_return_min_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    predicted_return_max_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    
    bull_case: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    base_case: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    bear_case: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    invalidating_conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Outcome Tracking (Evaluated later)
    actual_return_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    prediction_error: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    was_successful: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company")

    __table_args__ = (
        Index("idx_pred_lookup", "company_id", "prediction_date"),
    )
