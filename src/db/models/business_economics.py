import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class BusinessMetric(Base):
    """
    Layer 4: Business Economics — Tracks unit-level operational facts (Capacity, Utilization, Order Book, Market Share, ASP, Customer Concentration).
    """
    __tablename__ = "business_metrics"

    metric_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    observation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # e.g., 'INSTALLED_CAPACITY', 'CAPACITY_UTILIZATION_PCT', 'MARKET_SHARE_PCT', 'ORDER_BOOK_CR', 'ASP_INR', 'EXPORT_SHARE_PCT', 'CUSTOMER_CONCENTRATION_TOP5_PCT'
    
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True) # 'MT_PER_ANNUM', 'PERCENT', 'INR_CRORE', 'UNITS'
    segment: Mapped[str] = mapped_column(String(64), default="ALL")
    
    publication_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False) # 'INVESTOR_PRESENTATION', 'ANNUAL_REPORT', 'CONCALL_TRANSCRIPT', 'EXCHANGE_FILING'
    confidence: Mapped[float] = mapped_column(Float, default=1.00)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="business_metrics")

    __table_args__ = (
        Index("idx_biz_metric_lookup", "company_id", "metric_name", "observation_date"),
    )


class ReinvestmentMetric(Base):
    """
    Layer 4: Reinvestment Engine — First-class entity for tracking Incremental Capital Allocation & ROCE Trajectories over time.
    """
    __tablename__ = "reinvestment_metrics"

    reinvestment_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    period_end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    publication_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    
    reinvestment_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # (CapEx + Change in WC) / CFO
    incremental_capital_employed: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # CapEmployed(T) - CapEmployed(T-1) in INR Cr
    incremental_ebit: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # EBIT(T) - EBIT(T-1) in INR Cr
    incremental_revenue: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # Rev(T) - Rev(T-1) in INR Cr
    
    incremental_roce_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # (Incremental EBIT / Incremental Capital) * 100
    incremental_roic_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fcf_reinvestment_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    estimated_tam_cr: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # Total Addressable Market in INR Cr
    estimated_runway_years: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="reinvestment_metrics")

    __table_args__ = (
        Index("idx_reinvest_lookup", "company_id", "period_end_date", "publication_timestamp"),
    )
