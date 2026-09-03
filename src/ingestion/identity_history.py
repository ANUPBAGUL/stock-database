import uuid
from datetime import date, datetime
from typing import Dict, Any, Optional
from sqlalchemy import Column, String, Date, DateTime, JSON, ForeignKey
from src.db.base import Base

class CompanyIdentityHistory(Base):
    """
    Tracks security identity history anchored by ISIN to handle ticker changes,
    name revisions, demergers, and delistings without data corruption.
    """
    __tablename__ = "company_identity_history"

    history_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    isin = Column(String(12), nullable=False, index=True)
    
    nse_symbol = Column(String(20), nullable=True, index=True)
    bse_scrip_code = Column(String(10), nullable=True, index=True)
    company_name = Column(String(255), nullable=False)
    
    effective_start_date = Column(Date, nullable=False, index=True)
    effective_end_date = Column(Date, nullable=True) # None means currently active
    
    change_reason = Column(String(100), nullable=True) # e.g. NAME_CHANGE, TICKER_REVISION, DEMERGER, DELISTING
    delisting_date = Column(Date, nullable=True)
    suspension_date = Column(Date, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "history_id": self.history_id,
            "company_id": self.company_id,
            "isin": self.isin,
            "nse_symbol": self.nse_symbol,
            "bse_scrip_code": self.bse_scrip_code,
            "company_name": self.company_name,
            "effective_start_date": self.effective_start_date.isoformat(),
            "effective_end_date": self.effective_end_date.isoformat() if self.effective_end_date else None,
            "change_reason": self.change_reason,
            "delisting_date": self.delisting_date.isoformat() if self.delisting_date else None,
            "suspension_date": self.suspension_date.isoformat() if self.suspension_date else None
        }
