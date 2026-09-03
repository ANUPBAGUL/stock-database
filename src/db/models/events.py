import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Date, DateTime, Float, Integer, Boolean, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class CorporateAnnouncement(Base):
    """
    Official regulatory disclosures and announcements filed with NSE/BSE under SEBI (LODR) Regulations.
    Includes deterministic materiality scoring, dual-track decay half-life, and lifecycle states.

    Timestamp discipline (CRITICAL for PIT correctness):
      source_published_at: The timestamp the source (NSE/BSE/company) originally published this event.
      ingested_at:         When our system first stored this record (always >= source_published_at).
      event_occurred_at:   When the real-world event occurred (e.g., earnings date, plant commissioning).

    Source classification:
      OFFICIAL_EXCHANGE_FILING  ← Only this and EXCHANGE_ANNOUNCEMENT drive M6 feature vectors.
      EXCHANGE_ANNOUNCEMENT
      COMPANY_INVESTOR_PRESENTATION
      EARNINGS_CALL_TRANSCRIPT
      SECONDARY_ARTICLE          ← Never drives M6. Stored for audit/reference only.
    """
    __tablename__ = "corporate_announcements"

    announcement_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # ── Triple-Timestamp Fields (mandatory for PIT integrity) ──
    source_published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)  # Original source publication time
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)  # When we ingested it
    event_occurred_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # When the real-world event happened

    # Legacy alias — kept for backward compat, always set equal to source_published_at
    publication_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    event_type: Mapped[str] = mapped_column(String(50), nullable=False) # 'ORDER_WIN', 'CAPEX', 'AUDITOR_RESIGNATION', 'MANAGEMENT_CHANGE', 'RESULT', 'REGULATORY'
    track_type: Mapped[str] = mapped_column(String(20), default="TACTICAL") # 'TACTICAL' (48h half-life), 'STRUCTURAL' (90d half-life)

    # Source authority classification — only OFFICIAL_EXCHANGE_FILING and EXCHANGE_ANNOUNCEMENT feed M6
    source_type: Mapped[str] = mapped_column(String(48), default="OFFICIAL_EXCHANGE_FILING")
    # Values: OFFICIAL_EXCHANGE_FILING | EXCHANGE_ANNOUNCEMENT | COMPANY_INVESTOR_PRESENTATION
    #         | EARNINGS_CALL_TRANSCRIPT | SECONDARY_ARTICLE

    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)

    material_value_cr: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # Extracted INR Crores (e.g., 850.0)
    execution_timeline_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    raw_materiality_score: Mapped[float] = mapped_column(Float, default=50.0) # 0 to 100
    decayed_score: Mapped[float] = mapped_column(Float, default=50.0) # Effective score after time-decay
    last_decay_update: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True) # Link to official NSE/BSE PDF
    source_document_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="NEW_ACTIVE", index=True) # NEW_ACTIVE, DECAYING, ABSORBED_INTO_PRICE, ABSORBED_INTO_FINANCIALS, HISTORICAL_ARCHIVE
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="corporate_announcements")

    __table_args__ = (
        Index("idx_announcement_lookup", "company_id", "source_published_at", "status"),
    )


class BoardMeetingAnnouncement(Base):
    """
    Forward-Looking Catalyst Tracker — Ingests advance notice of Board Meetings submitted under SEBI LODR Regulation 29.
    """
    __tablename__ = "board_meeting_announcements"

    meeting_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    
    notice_date: Mapped[datetime] = mapped_column(DateTime, nullable=False) # Date when notice was filed
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False, index=True) # Date of the actual board meeting
    
    purpose: Mapped[str] = mapped_column(String(500), nullable=False) # e.g. "Financial Results / Dividend / Fund Raising"
    event_category: Mapped[str] = mapped_column(String(50), default="FINANCIAL_RESULTS") # FINANCIAL_RESULTS, DIVIDEND, BONUS_SPLIT, FUND_RAISING
    
    days_until_meeting: Mapped[int] = mapped_column(Integer, default=0)
    urgency_status: Mapped[str] = mapped_column(String(32), default="SCHEDULED") # IMMINENT (<=3 days), SCHEDULED, COMPLETED, CANCELLED
    
    blackout_period_active: Mapped[bool] = mapped_column(Boolean, default=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="board_meetings")

    __table_args__ = (
        Index("idx_meeting_date_lookup", "symbol", "meeting_date"),
    )


class CompanyEvent(Base):
    """
    Structured corporate events parsed from exchange filings and classified by source authority.

    Timestamp discipline:
      source_published_at: Original source publication timestamp (from NSE API or yfinance pubDate).
      ingested_at:         When our system stored this record.
      event_occurred_at:   The actual real-world event date (e.g., Q4 FY26 earnings = 2026-05-12).

    IMPORTANT: A secondary article published in September 2026 about an event that occurred in
    May 2026 must store event_occurred_at = 2026-05-12 and source_type = SECONDARY_ARTICLE.
    It must NOT be presented as a new event in the dashboard or used in M6 features.
    """
    __tablename__ = "company_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)

    # Triple timestamps (mandatory for PIT correctness)
    source_published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    event_occurred_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Legacy alias
    event_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    publication_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    event_type: Mapped[str] = mapped_column(String(50), nullable=False) # 'CAPEX', 'ORDER_WIN', 'MANAGEMENT_CHANGE', 'REGULATORY', 'EARNINGS_SURPRISE'

    # Source authority: only OFFICIAL_EXCHANGE_FILING and EXCHANGE_ANNOUNCEMENT feed M6
    source_type: Mapped[str] = mapped_column(String(48), default="OFFICIAL_EXCHANGE_FILING")
    # Values: OFFICIAL_EXCHANGE_FILING | EXCHANGE_ANNOUNCEMENT | COMPANY_INVESTOR_PRESENTATION
    #         | EARNINGS_CALL_TRANSCRIPT | SECONDARY_ARTICLE

    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)

    order_size_inr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_completion_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    materiality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # 0.00 to 1.00

    ai_interpretation: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    ingested_at_col: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="events")

    __table_args__ = (
        Index("idx_event_pub_lookup", "company_id", "source_published_at"),
    )
