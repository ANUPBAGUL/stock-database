import uuid
from datetime import date, datetime
from typing import List, Optional
from sqlalchemy import String, Date, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class Sector(Base):
    __tablename__ = "sectors"

    sector_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sector_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    companies: Mapped[List["Company"]] = relationship("Company", back_populates="sector")

class Company(Base):
    __tablename__ = "companies"

    company_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    isin: Mapped[str] = mapped_column(String(12), unique=True, nullable=False, index=True)
    nse_symbol: Mapped[Optional[str]] = mapped_column(String(20), index=True, nullable=True)
    bse_code: Mapped[Optional[str]] = mapped_column(String(10), index=True, nullable=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    sector_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("sectors.sector_id"), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    listing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    delisting_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE") # Legacy status: ACTIVE, DELISTED, SUSPENDED

    # Orthogonal Universe Dimensions
    listing_status: Mapped[str] = mapped_column(String(32), default="ACTIVE") # ACTIVE, SUSPENDED, DELISTED, BANKRUPTCY, LIQUIDATION, MERGED, ACQUIRED
    tradability_status: Mapped[str] = mapped_column(String(32), default="TRADABLE") # TRADABLE, RESTRICTED, HALTED, SUSPENDED
    liquidity_status: Mapped[str] = mapped_column(String(32), default="LIQUID") # HIGH, MEDIUM, LOW, ILLIQUID
    research_eligibility: Mapped[str] = mapped_column(String(32), default="ELIGIBLE") # ELIGIBLE, QUARANTINED, INSUFFICIENT_DATA
    
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    face_value: Mapped[float] = mapped_column(Float, default=10.0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sector: Mapped[Optional[Sector]] = relationship("Sector", back_populates="companies")
    classification_history: Mapped[List["CompanyClassificationHistory"]] = relationship("CompanyClassificationHistory", back_populates="company")
    financials: Mapped[List["BitemporalFinancial"]] = relationship("BitemporalFinancial", back_populates="company")
    corporate_actions: Mapped[List["CorporateAction"]] = relationship("CorporateAction", back_populates="company")
    daily_prices: Mapped[List["DailyPriceRaw"]] = relationship("DailyPriceRaw", back_populates="company")
    events: Mapped[List["CompanyEvent"]] = relationship("CompanyEvent", back_populates="company")
    corporate_announcements: Mapped[List["CorporateAnnouncement"]] = relationship("CorporateAnnouncement", back_populates="company")
    board_meetings: Mapped[List["BoardMeetingAnnouncement"]] = relationship("BoardMeetingAnnouncement", back_populates="company")
    ai_profiles: Mapped[List["AICompanyProfile"]] = relationship("AICompanyProfile", back_populates="company")
    
    business_metrics: Mapped[List["BusinessMetric"]] = relationship("BusinessMetric", back_populates="company")
    reinvestment_metrics: Mapped[List["ReinvestmentMetric"]] = relationship("ReinvestmentMetric", back_populates="company")
    valuation_snapshots: Mapped[List["ValuationSnapshot"]] = relationship("ValuationSnapshot", back_populates="company")
    capital_allocation_events: Mapped[List["CapitalAllocationEvent"]] = relationship("CapitalAllocationEvent", back_populates="company")
    shareholding_history: Mapped[List["ShareholdingHistory"]] = relationship("ShareholdingHistory", back_populates="company")
    governance_events: Mapped[List["GovernanceEvent"]] = relationship("GovernanceEvent", back_populates="company")
    decision_snapshots: Mapped[List["DecisionSnapshot"]] = relationship("DecisionSnapshot", back_populates="company")
    forward_outcomes: Mapped[List["ForwardOutcome"]] = relationship("ForwardOutcome", back_populates="company")
    lifecycle_history: Mapped[List["CompanyLifecycleHistory"]] = relationship("CompanyLifecycleHistory", back_populates="company")
    failure_diagnostics: Mapped[List["MultibaggerFailureDiagnostic"]] = relationship("MultibaggerFailureDiagnostic", back_populates="company")
    source_evidence: Mapped[List["RawSourceEvidence"]] = relationship("RawSourceEvidence", back_populates="company")
    quarterly_pit_states: Mapped[List["QuarterlyPITState"]] = relationship("QuarterlyPITState", back_populates="company")
    audit_traces: Mapped[List["DataAuditTrace"]] = relationship("DataAuditTrace", back_populates="company")
    universe_memberships: Mapped[List["UniverseMembership"]] = relationship("UniverseMembership", back_populates="company")

