import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, Float, Integer, Boolean, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class DecisionSnapshot(Base):
    """
    Layer 7: The Secret Weapon — Immutable Pre-Trade Decision Snapshot.
    Records the exact vector of facts, hypotheses, model score, and invalidation criteria at the second T0 a decision was made.
    NEVER UPDATED.
    """
    __tablename__ = "decision_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    decision_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True) # Exact T0 datetime
    
    feature_set_version: Mapped[str] = mapped_column(String(32), nullable=False) # e.g., 'v2.4.0'
    model_version: Mapped[str] = mapped_column(String(32), nullable=False) # e.g., 'M6_FROZEN_EXP004'
    dataset_hash: Mapped[str] = mapped_column(String(64), nullable=False) # SHA-256 hash of PIT dataset slice
    
    raw_features_payload: Mapped[dict] = mapped_column(JSON, nullable=False) # Complete ~180 variable vector at T0
    data_quality_score: Mapped[float] = mapped_column(Float, default=100.0) # 0 to 100
    missingness_pct: Mapped[float] = mapped_column(Float, default=0.0) # % of features imputed / missing
    
    m6_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # 0 to 100
    m6_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    horizon_ratings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # Longterm, Swing, Intraday
    verdict: Mapped[str] = mapped_column(String(32), nullable=False) # CONVICTION_BUY, ACCUMULATE_ON_DIPS, WATCHLIST, PASS
    
    thesis_why_buy: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # Array of positive causal drivers
    thesis_why_not_buy: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # Array of structural friction risks
    invalidation_conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # Exact thresholds that invalidate thesis
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow) # Immutable

    company: Mapped["Company"] = relationship("Company", back_populates="decision_snapshots")
    outcome: Mapped[Optional["ForwardOutcome"]] = relationship("ForwardOutcome", back_populates="snapshot", uselist=False)

    __table_args__ = (
        Index("idx_snapshot_lookup", "company_id", "decision_timestamp"),
    )


class ForwardOutcome(Base):
    """
    Layer 8: Outcome & Multibagger Label Store — Tracks what actually happened post-T0.
    Stores multi-horizon price trajectories, max returns, max drawdowns, path volatility, and empirical binary labels.
    """
    __tablename__ = "forward_outcomes"

    outcome_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("decision_snapshots.snapshot_id"), unique=True, nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    t0_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    t0_price: Mapped[float] = mapped_column(Float, nullable=False)
    market_cap_at_t0_cr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Realized Milestone Prices & Dates
    price_at_2x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    date_2x: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    days_to_2x: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    price_at_5x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    date_5x: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    days_to_5x: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    price_at_10x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    date_10x: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    days_to_10x: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Realized Split-Adjusted Price Horizons
    price_t_1d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_t_5d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_t_20d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_t_60d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_t_120d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_t_252d: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # 1-Year Forward
    price_t_504d: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # 2-Year Forward
    price_t_756d: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # 3-Year Forward
    
    # Quantitative Risk / Reward & Path Metrics
    maximum_run_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_drawdown_before_2x: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # Drawdown before achieving 2x
    max_drawdown_before_5x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_forward_return_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_drawdown_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Relative Performance & Alpha
    benchmark_nifty500_return_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sector_return_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    alpha_generated_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    survival_status: Mapped[str] = mapped_column(String(32), default="ACTIVE") # 'ACTIVE', 'DELISTED', 'MERGED', 'SUSPENDED', 'BANKRUPTCY'
    daily_path_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # Full daily trajectory vector

    # Total Shareholder Wealth Compounding & Terminal Economic Realization
    wealth_start: Mapped[float] = mapped_column(Float, default=100.0) # W0
    wealth_end: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # WT
    cash_distributions_cr: Mapped[float] = mapped_column(Float, default=0.0) # D_t dividends
    corporate_proceeds_cr: Mapped[float] = mapped_column(Float, default=0.0) # C_t restructuring/spin-off proceeds
    terminal_equity_value_cr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cash_recovery_cr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_realized_wealth_return_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # R_T = (WT / W0) - 1

    # Generic Half-Open Outcome Interval Metadata (Audit Invariant E)
    label_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True) # Start of outcome interval
    label_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True) # End of outcome interval
    horizon_type: Mapped[str] = mapped_column(String(16), default="3Y") # '1Y', '3Y', '5Y', 'SURVIVAL'

    # Competing Risk Event Clock & Censoring Separation
    event_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True) # '10X', 'BANKRUPTCY', 'DELISTING', 'ACQUISITION', 'OTHER_TERMINAL'
    censoring_status: Mapped[str] = mapped_column(String(32), default="ONGOING", index=True) # 'MATURE', 'RIGHT_CENSORED', 'ADMINISTRATIVELY_CENSORED', 'DATA_CENSORED', 'ONGOING'
    event_time_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True) # tau_i
    
    # Empirical Multibagger Labels (Ground Truth for Research & ML)
    is_multibagger_2x: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_multibagger_5x: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_multibagger_10x: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_failure: Mapped[bool] = mapped_column(Boolean, default=False, index=True) # Max drawdown > 50% without reaching 2x
    
    last_evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    snapshot: Mapped["DecisionSnapshot"] = relationship("DecisionSnapshot", back_populates="outcome")
    company: Mapped["Company"] = relationship("Company", back_populates="forward_outcomes")

    __table_args__ = (
        Index("idx_outcomes_lookup", "company_id", "t0_date"),
        Index("idx_outcomes_interval", "label_start", "label_end"),
    )
