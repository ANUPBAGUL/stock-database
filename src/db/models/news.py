import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Float, Integer, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class NewsArticle(Base):
    __tablename__ = "news_articles"

    article_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    publication_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    article_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dedup_group_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    novelty_score: Mapped[float] = mapped_column(Float, default=1.0) # 1.0 = completely new, 0.1 = repeat story
    
    expected_revenue_impact_inr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_eps_impact_inr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    impact_time_horizon_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    source_name: Mapped[str] = mapped_column(String(100), default="EXCHANGE_FEED")
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company")

    __table_args__ = (
        Index("idx_news_pub_lookup", "company_id", "publication_date"),
    )
