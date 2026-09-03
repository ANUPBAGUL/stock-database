import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, Float, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class ThesisHistory(Base):
    __tablename__ = "thesis_history"

    history_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    
    conviction_score: Mapped[float] = mapped_column(Float, nullable=False)
    thesis_summary: Mapped[str] = mapped_column(Text, nullable=False)
    thesis_change_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    previous_history_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company")

    __table_args__ = (
        Index("idx_thesis_hist_lookup", "company_id", "as_of_date"),
    )
