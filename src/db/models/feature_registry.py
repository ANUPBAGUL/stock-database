import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from src.db.base import Base

class FeatureVersionRegistry(Base):
    __tablename__ = "feature_version_registry"

    feature_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    feature_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # e.g. 'v1.0', 'v2.0'
    
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    calculation_script: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_feature_ver", "feature_name", "version", unique=True),
    )
