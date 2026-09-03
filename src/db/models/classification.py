import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class CompanyClassificationHistory(Base):
    """
    Point-in-Time Sector, Industry & Sub-Industry Classification History.
    Allows historical reconstruction of which industry/sector a stock belonged to on any historical date T.
    """
    __tablename__ = "company_classification_history"

    classification_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    sector: Mapped[str] = mapped_column(String(100), nullable=False)
    industry: Mapped[str] = mapped_column(String(100), nullable=False)
    sub_industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[date] = mapped_column(Date, nullable=False, default=date(9999, 12, 31), index=True)
    
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="NSE_INDICES_CLASSIFICATION")
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="classification_history")

    __table_args__ = (
        Index("idx_class_pit_lookup", "company_id", "effective_from", "effective_to"),
    )
