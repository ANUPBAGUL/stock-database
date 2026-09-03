import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import String, Date, DateTime, Float, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.base import Base


class CorporateAction(Base):
    __tablename__ = "corporate_actions"

    action_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), nullable=False, index=True)

    announcement_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ex_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    record_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    action_type: Mapped[str] = mapped_column(String(30), nullable=False) # 'SPLIT', 'BONUS', 'RIGHTS', 'DEMERGER', 'DIVIDEND'

    old_shares: Mapped[float] = mapped_column(Float, default=1.0)
    new_shares: Mapped[float] = mapped_column(Float, default=1.0)

    price_factor: Mapped[float] = mapped_column(Float, default=1.0) # Price multiplier (e.g., 0.20 for 1:5 split)
    share_factor: Mapped[float] = mapped_column(Float, default=1.0) # Share count multiplier (e.g., 5.0 for 1:5 split)
    cum_factor: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    dividend_amount: Mapped[float] = mapped_column(Float, default=0.0)

    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship("Company", back_populates="corporate_actions")


class DailyPriceRaw(Base):
    """
    Layer 2: Raw OHLCV market data with full quote provenance.

    Price reproducibility requires all four provenance fields:
      exchange:          NSE, BSE, or COMBINED
      quote_type:        LTP, CLOSE, VWAP, OPEN, HIGH, LOW
      price_source:      UPSTOX_API, NSE_EOD, YFINANCE, BSE_EOD
      quote_timestamp:   Precise intraday IST timestamp of the quote (not just trading_date)

    Without these, a price of ₹14,590 cannot be distinguished from
    an intraday LTP vs. EOD close vs. a different exchange's close.
    """
    __tablename__ = "daily_prices_raw"

    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.company_id"), primary_key=True)
    trading_date: Mapped[date] = mapped_column(Date, primary_key=True, index=True)

    # Quote provenance (mandatory for price reproducibility)
    exchange: Mapped[str] = mapped_column(String(8), default="NSE")          # NSE, BSE, COMBINED
    quote_type: Mapped[str] = mapped_column(String(16), default="CLOSE")     # LTP, CLOSE, VWAP, OPEN, HIGH, LOW
    price_source: Mapped[str] = mapped_column(String(32), default="NSE_EOD") # UPSTOX_API, NSE_EOD, YFINANCE, BSE_EOD
    quote_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # Precise IST intraday timestamp

    open_price: Mapped[float] = mapped_column(Float, nullable=False)
    high_price: Mapped[float] = mapped_column(Float, nullable=False)
    low_price: Mapped[float] = mapped_column(Float, nullable=False)
    close_price: Mapped[float] = mapped_column(Float, nullable=False)
    adjusted_close: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    deliverable_volume: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    delivery_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    turnover: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # INR
    number_of_trades: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    vwap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    company: Mapped["Company"] = relationship("Company", back_populates="daily_prices")

    __table_args__ = (
        Index("idx_daily_price_date", "trading_date"),
    )
