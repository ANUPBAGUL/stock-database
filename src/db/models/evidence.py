import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, Float, Text, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class RawSourceEvidence(Base):
    """
    Layer 1: Raw Source Evidence & Auditability.
    Links any extracted number or event directly to the original filing document, URL, parser version, and SHA-256 hash.
    """
    __tablename__ = "raw_source_evidence"

    evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_table: Mapped[str] = mapped_column(String(64), nullable=False, index=True) # e.g. 'bitemporal_financials', 'corporate_announcements'
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True) # Primary key of the specific entity
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    source_type: Mapped[str] = mapped_column(String(64), nullable=False) # 'NSE_XBRL_FILING', 'SEBI_LODR_ANNOUNCEMENT', 'BSE_PDF', 'ANNUAL_REPORT'
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    document_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True) # SHA-256 hash of original document
    document_date: Mapped[date] = mapped_column(Date, nullable=False)
    publication_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    retrieval_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    parser_version: Mapped[str] = mapped_column(String(32), default="v1.0.0")
    
    raw_document_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True) # Local/S3 path or filing accession ID
    extracted_fields_payload: Mapped[dict] = mapped_column(JSON, nullable=False) # Key-value map of exact extracted items
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="source_evidence")

    __table_args__ = (
        Index("idx_evidence_entity_lookup", "entity_table", "entity_id"),
        Index("idx_evidence_hash_lookup", "document_hash"),
    )


class CausalEvidenceNode(Base):
    """
    Causal Knowledge Graph Node linking structural catalysts to economic effects.
    """
    __tablename__ = "causal_evidence_nodes"

    node_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    source_node: Mapped[str] = mapped_column(String(100), nullable=False) # e.g., 'GOVT_DEFENCE_POLICY'
    target_node: Mapped[str] = mapped_column(String(100), nullable=False) # e.g., 'ORDER_BOOK_GROWTH'
    
    confidence_score: Mapped[float] = mapped_column(Float, default=0.8) # 0.0 to 1.0
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_document_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company")

    __table_args__ = (
        Index("idx_evidence_lookup", "company_id", "source_node"),
    )
