import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class DataLineageRecord(Base):
    __tablename__ = "data_lineage_records"

    lineage_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    target_prediction_id: Mapped[str] = mapped_column(String(36), ForeignKey("ai_predictions.prediction_id"), nullable=False, index=True)
    
    feature_name: Mapped[str] = mapped_column(String(100), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1.0")
    
    source_table: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. 'bitemporal_financials'
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    
    publication_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    retrieved_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_lineage_lookup", "target_prediction_id", "feature_name"),
    )
