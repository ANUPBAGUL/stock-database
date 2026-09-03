import uuid
from datetime import date, datetime
from typing import Optional, List
from sqlalchemy import String, Date, DateTime, Float, Integer, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class MultibaggerFailureDiagnostic(Base):
    """
    Layer 8: Multi-Factor Failed Multibagger & False-Positive Diagnostic Log.
    
    Permits compound multi-factor failure modeling (e.g., VALUATION_COMPRESSION + CYCLICAL_REVERSAL + MARGIN_COMPRESSION)
    with empirical quantitative evidence and confidence scores.
    """
    __tablename__ = "multibagger_failure_diagnostics"

    failure_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("decision_snapshots.snapshot_id"), nullable=False, index=True)
    outcome_id: Mapped[str] = mapped_column(String(36), ForeignKey("forward_outcomes.outcome_id"), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    # Primary & Secondary Failure Classification
    failure_category: Mapped[str] = mapped_column(String(64), nullable=False, index=True) # Primary bucket
    primary_failure_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    secondary_failure_reasons: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # ["CYCLICAL_REVERSAL", "MARGIN_COMPRESSION"]
    failure_evidence: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # [{"metric": "ROCE", "expected": 30.0, "realized": 8.0}, ...]
    
    failure_confidence: Mapped[float] = mapped_column(Float, default=0.90) # 0.0 to 1.0
    failure_detected_at: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    severity_rank: Mapped[int] = mapped_column(Integer, default=1)
    first_detected_date: Mapped[date] = mapped_column(Date, nullable=False)
    post_mortem_notes: Mapped[str] = mapped_column(String(2000), nullable=False)
    
    # Causal Divergence Metrics (T0 Expected vs Realized)
    expected_roce_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    realized_roce_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_revenue_growth: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    realized_revenue_growth: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    peak_drawdown_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    snapshot: Mapped["DecisionSnapshot"] = relationship("DecisionSnapshot")
    outcome: Mapped["ForwardOutcome"] = relationship("ForwardOutcome")
    company: Mapped["Company"] = relationship("Company", back_populates="failure_diagnostics")

    __table_args__ = (
        Index("idx_failure_cat_lookup", "company_id", "primary_failure_reason"),
    )
