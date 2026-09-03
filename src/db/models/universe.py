"""
Historical Universe Membership and Survivorship Model.
Tracks exact point-in-time constituent membership across market indices and failure control groups.
Guarantees survivorship-free sampling by maintaining historical delistings, bankruptcies, and mergers.
"""
import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

class UniverseMembership(Base):
    """
    Historical Universe Membership Record.
    Reconstructs: 'Was Company X in Universe U on Date T0, and what was its tradability/liquidity status?'
    """
    __tablename__ = "universe_memberships"

    membership_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    
    universe_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True) 
    # e.g., 'NIFTY_500', 'NIFTY_SMALLCAP_250', 'NIFTY_MICROCAP_250', 'HISTORICAL_FAILURES', 'BSE_ALLCAP'

    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True) # None = ongoing member

    # Orthogonal Universe Dimensions
    listing_status: Mapped[str] = mapped_column(String(32), default="ACTIVE") 
    # 'ACTIVE', 'SUSPENDED', 'DELISTED', 'BANKRUPTCY', 'LIQUIDATION', 'MERGED', 'ACQUIRED'

    tradability_status: Mapped[str] = mapped_column(String(32), default="TRADABLE")
    # 'TRADABLE', 'RESTRICTED', 'HALTED', 'SUSPENDED'

    liquidity_status: Mapped[str] = mapped_column(String(32), default="LIQUID")
    # 'HIGH', 'MEDIUM', 'LOW', 'ILLIQUID'

    research_eligibility: Mapped[str] = mapped_column(String(32), default="ELIGIBLE")
    # 'ELIGIBLE', 'QUARANTINED', 'INSUFFICIENT_DATA'

    inclusion_reason: Mapped[str] = mapped_column(String(128), default="INDEX_CONSTITUENT")
    # 'INDEX_CONSTITUENT', 'BANKRUPTCY_SURVIVORSHIP_CONTROL', 'SEBI_LODR_MEMBER', 'HISTORICAL_10X_SAMPLE'

    exclusion_reason: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # 'DELISTING_INSOLVENCY', 'MERGER_ABSORPTION', 'INDEX_REBALANCE', 'LIQUIDITY_DROP'

    source: Mapped[str] = mapped_column(String(64), default="NSE_OFFICIAL_ARCHIVE")
    source_document_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="universe_memberships")

    __table_args__ = (
        Index("idx_universe_membership_pit", "company_id", "universe_name", "effective_from", "effective_to"),
    )
