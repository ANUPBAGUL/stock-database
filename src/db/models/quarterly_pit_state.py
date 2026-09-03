import uuid
from datetime import date, datetime
from typing import Optional, List
from sqlalchemy import String, Date, DateTime, Float, Integer, Boolean, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class QuarterlyPITState(Base):
    """
    Quarterly Point-in-Time Integrated Observation State.
    
    Preserves the complete consolidated state of a company at every quarterly reporting boundary
    the exact moment (publication_timestamp) its quarterly numbers became knowable to the market.
    
    Enables multi-quarter trajectory alignment:
    - What did future 10x multibaggers look like at Q-12, Q-8, Q-4, and Q-2 before rerating?
    - Differential Analysis: Winner vs False-Positive feature trajectory comparison.
    """
    __tablename__ = "quarterly_pit_states"

    state_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    quarter_end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True) # e.g. 2024-06-30
    publication_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True) # Official filing release
    financial_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("bitemporal_financials.financial_id"), nullable=True)
    
    # ──────────────────────────────────────────────────────────────
    # 1. Scale & Growth Acceleration
    # ──────────────────────────────────────────────────────────────
    market_cap_cr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    revenue_ttm_cr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    revenue_growth_yoy_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ebitda_growth_yoy_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pat_growth_yoy_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eps_ttm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eps_growth_yoy_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ──────────────────────────────────────────────────────────────
    # 2. Profitability, Operating Leverage & Return on Capital
    # ──────────────────────────────────────────────────────────────
    gross_margin_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ebitda_margin_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pat_margin_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roce_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roic_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    incremental_roce_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reinvestment_rate_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fcf_to_pat_conversion_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ──────────────────────────────────────────────────────────────
    # 3. Balance Sheet Health & Capital Structure
    # ──────────────────────────────────────────────────────────────
    debt_to_equity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_debt_to_ebitda: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    working_capital_days: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dilution_rate_yoy_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ──────────────────────────────────────────────────────────────
    # 4. Business Unit Economics & Microstructure
    # ──────────────────────────────────────────────────────────────
    capacity_utilization_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    order_book_cr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    market_share_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ──────────────────────────────────────────────────────────────
    # 5. Valuation Positioning & Market Expectations
    # ──────────────────────────────────────────────────────────────
    pe_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pe_3y_percentile: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ev_ebitda: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fcf_yield_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ──────────────────────────────────────────────────────────────
    # 6. Governance, Ownership & Lifecycle Classification
    # ──────────────────────────────────────────────────────────────
    promoter_holding_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    promoter_pledge_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    institutional_holding_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    institutional_stake_change_qoq: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    lifecycle_stage: Mapped[str] = mapped_column(String(32), default="2_SCALING")
    active_catalyst_decay_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # ──────────────────────────────────────────────────────────────
    # 7. Model State at Quarterly Boundary
    # ──────────────────────────────────────────────────────────────
    m6_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    m6_verdict: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    raw_feature_vector_payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    # ──────────────────────────────────────────────────────────────
    # 8. Subsequent Forward Realized Trajectory (Q+1 to Q+12)
    # ──────────────────────────────────────────────────────────────
    fwd_return_1q_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fwd_return_2q_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fwd_return_4q_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # 1-Year Forward
    fwd_return_8q_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # 2-Year Forward
    fwd_return_12q_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # 3-Year Forward
    
    fwd_max_run_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fwd_max_drawdown_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_multibagger_2x: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_multibagger_5x: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_multibagger_10x: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_failure: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="quarterly_pit_states")

    __table_args__ = (
        Index("idx_q_pit_lookup", "company_id", "quarter_end_date", "publication_timestamp"),
        Index("idx_q_multibagger_scan", "lifecycle_stage", "is_multibagger_2x", "is_multibagger_5x", "is_multibagger_10x"),
    )
