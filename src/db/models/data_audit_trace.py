"""
Per-Field Data Audit Trace (Fix 8).

Every value displayed in the dashboard or entering the M6 feature vector
must have a corresponding DataAuditTrace record answering:

  "Exactly which filing, which accounting facts, which formula and which
   publication timestamp produced this number?"

Fields cover the complete audit chain:
  Raw Source → Publication Timestamp → PIT Eligibility → Calculation Formula
  → Raw Inputs → Displayed Value → PIT Valid From/To → Quality Status
"""

import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, Float, JSON, ForeignKey, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base


class DataAuditTrace(Base):
    """
    Per-metric audit lineage record.

    One record per (company, snapshot, metric) tuple.
    Updated whenever the metric is recalculated from a newer filing.
    """
    __tablename__ = "data_audit_traces"

    trace_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("decision_snapshots.snapshot_id"), nullable=True, index=True)

    # The metric being traced (e.g., "roce_pct", "promoter_holding_pct", "debt_to_equity")
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # The value actually displayed / used in M6 (None if quarantined)
    displayed_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # The raw computed value before quarantine filtering
    raw_computed_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Source Lineage ──
    source_table: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)    # e.g., "bitemporal_financials"
    source_record_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True) # FK to the actual source row
    source_document_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_document_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # SHA-256

    # ── Temporal Provenance ──
    publication_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # When source was published
    data_period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)               # Financial period start
    data_period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)                 # Financial period end

    # ── Scope ──
    consolidation_scope: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # CONSOLIDATED / STANDALONE

    # ── Calculation Transparency ──
    calculation_formula: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Human-readable formula
    raw_inputs_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)          # Exact primitive values used

    # ── PIT Validity Window ──
    pit_valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # When this metric became knowable
    pit_valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)    # When superseded by a newer filing

    # ── Quality Status ──
    quality_status: Mapped[str] = mapped_column(String(32), default="APPROVED")
    # Values: APPROVED | QUARANTINED | PARTIAL_QUARANTINE | MISSING_DATA | LOW_CONFIDENCE
    quarantine_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="audit_traces")

    __table_args__ = (
        Index("idx_audit_trace_lookup", "company_id", "metric_name", "pit_valid_from"),
    )
