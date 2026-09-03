import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, Float, Integer, Boolean, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base

class BitemporalFinancial(Base):
    """
    Layer 3: Bitemporal Primitive Financial Statements (Income Statement, Balance Sheet, Cash Flow Facts).
    Stores raw accounting primitives so that institutional metrics (ROCE, ROIC, FCF Yield, Accruals)
    can be computed dynamically point-in-time without hardcoded bias.
    """
    __tablename__ = "bitemporal_financials"

    financial_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)
    
    period_type: Mapped[str] = mapped_column(String(16), nullable=False) # 'QUARTERLY', 'ANNUAL', 'TTM'
    period_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    # Bi-Temporal Timestamps
    publication_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    system_rec_start: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    system_rec_end: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime(9999, 12, 31, 23, 59, 59))
    
    is_restatement: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False) # 'NSE_XBRL', 'YFINANCE_PIT', 'ANNUAL_REPORT', 'UPSTOX_MASTER'
    source_document: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    data_version: Mapped[str] = mapped_column(String(16), default="v1")
    
    # ──────────────────────────────────────────────────────────────
    # 1. Income Statement Primitives (Unit: INR Crores, EPS in INR)
    # ──────────────────────────────────────────────────────────────
    revenue: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    other_income: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ebitda: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    depreciation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ebit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    interest_expense: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pbt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tax_expense: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eps_diluted: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ──────────────────────────────────────────────────────────────
    # 2. Balance Sheet Primitives (Unit: INR Crores)
    # ──────────────────────────────────────────────────────────────
    cash_and_equivalents: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trade_receivables: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    inventories: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    other_current_assets: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_current_assets: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    ppe_gross: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ppe_net: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    capital_wip: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    intangibles: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_assets: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    trade_payables: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    short_term_debt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    other_current_liabilities: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_liabilities: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    long_term_debt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_debt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_liabilities: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    equity_share_capital: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reserves_and_surplus: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_worth: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    shares_outstanding: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ──────────────────────────────────────────────────────────────
    # 2a. Debt Disaggregation (critical for correct D/E calculation)
    # IND-AS 116 lease liabilities must NOT be conflated with financial debt.
    # ──────────────────────────────────────────────────────────────
    financial_debt_lt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Long-term bank loans, NCDs, bonds
    financial_debt_st: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Working capital, CPs, short-term loans
    lease_liabilities_lt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # IND-AS 116 long-term lease obligations
    lease_liabilities_st: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # IND-AS 116 current lease obligations
    current_investments: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Liquid investments (for net debt)
    net_debt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # total_debt - cash - current_investments

    # Consolidation scope: must be CONSOLIDATED or STANDALONE — never mixed within a snapshot
    consolidation_scope: Mapped[str] = mapped_column(String(16), default="CONSOLIDATED")  # CONSOLIDATED, STANDALONE

    # ──────────────────────────────────────────────────────────────
    # 3. Cash Flow Statement Primitives (Unit: INR Crores)
    # ──────────────────────────────────────────────────────────────
    operating_cash_flow: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # CFO
    capex: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    investing_cash_flow: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # CFI
    financing_cash_flow: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # CFF
    free_cash_flow: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # CFO - CapEx
    
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    company: Mapped["Company"] = relationship("Company", back_populates="financials")

    __table_args__ = (
        Index("idx_pit_lookup", "company_id", "publication_date", "period_end_date"),
    )
