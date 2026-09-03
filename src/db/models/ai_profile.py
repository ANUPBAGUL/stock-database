import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, Integer, JSON, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class AICompanyProfile(Base):
    __tablename__ = "ai_company_profiles"

    profile_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # 11-Dimension Scores (0 to 100)
    business_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    financial_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    growth_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    industry_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    catalyst_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    valuation_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    momentum_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    governance_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    risk_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    transformation_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    historical_multibagger_similarity_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    overall_conviction_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Structured AI Reasoning
    investment_thesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_risks: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    catalyst_timeline: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    input_snapshot_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="ai_profiles")

    __table_args__ = (
        Index("idx_ai_profile_lookup", "company_id", "as_of_date"),
    )
