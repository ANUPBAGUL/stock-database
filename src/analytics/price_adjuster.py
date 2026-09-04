"""
Price Adjuster — On-the-fly split/bonus adjustment for OHLCV data.

Converts Raw OHLCV to Split-Adjusted OHLCV using cumulative adjustment factors
from CorporateAction records. Also adjusts volume inversely to maintain
comparable volume levels across split boundaries.
"""

import logging
from datetime import date
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from src.db.models import DailyPriceRaw, CorporateAction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PriceAdjuster:
    """
    On-the-fly price adjuster for technical indicators.
    Converts Raw OHLCV to Split-Adjusted OHLCV.

    Adjustment logic:
    - Prices BEFORE an ex-date are multiplied by price_factor (old/new)
    - Volume BEFORE an ex-date is divided by price_factor (i.e., multiplied by share_factor)
    - Multiple corporate actions compound multiplicatively
    """

    @staticmethod
    def get_adjusted_prices(
        db: Session,
        company_id: str,
        start_date: date,
        end_date: date,
        as_of_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        # Fetch raw prices
        raw_prices = db.query(DailyPriceRaw).filter(
            DailyPriceRaw.company_id == company_id,
            DailyPriceRaw.trading_date >= start_date,
            DailyPriceRaw.trading_date <= end_date
        ).order_by(DailyPriceRaw.trading_date.asc()).all()

        if not raw_prices:
            return []

        # Point-In-Time Cutoff: Only consider corporate actions with ex_date <= cutoff_date when as_of_date is set.
        # If as_of_date is None, adjust across all corporate actions up to the present basis.
        cutoff_date = as_of_date

        # Fetch relevant corporate actions (SPLIT and BONUS only — these affect price continuity)
        query_actions = db.query(CorporateAction).filter(
            CorporateAction.company_id == company_id,
            CorporateAction.action_type.in_(["SPLIT", "BONUS"]),
        )
        if cutoff_date is not None:
            query_actions = query_actions.filter(CorporateAction.ex_date <= cutoff_date)

        actions = query_actions.order_by(CorporateAction.ex_date.asc()).all()

        # Pre-compute: for each action, its price_factor applies to all dates BEFORE its ex_date.
        # To adjust to the latest basis as of cutoff_date, compound all factors where price.trading_date < ex_date <= cutoff_date.
        action_list = [
            {"ex_date": act.ex_date, "price_factor": act.price_factor if act.price_factor > 0 else 1.0}
            for act in actions
        ]

        adjusted_series = []
        for price in raw_prices:
            # Compute cumulative adjustment factor:
            # Multiply all price_factors where price.trading_date < action.ex_date (and <= cutoff_date if set)
            cum_price_factor = 1.0
            for act in action_list:
                if act["ex_date"] > price.trading_date and (cutoff_date is None or act["ex_date"] <= cutoff_date):
                    cum_price_factor *= act["price_factor"]

            raw_vol = price.volume if price.volume is not None else 0
            adj_volume = int(raw_vol / cum_price_factor) if (cum_price_factor > 0 and raw_vol is not None) else raw_vol

            raw_close = price.close_price if price.close_price is not None else 0.0
            raw_open = price.open_price if price.open_price is not None else raw_close
            raw_high = price.high_price if price.high_price is not None else max(raw_open, raw_close)
            raw_low = price.low_price if price.low_price is not None else min(raw_open, raw_close)

            adjusted_series.append({
                "trading_date": price.trading_date,
                "raw_close": raw_close,
                "adj_open": round(raw_open * cum_price_factor, 4),
                "adj_high": round(raw_high * cum_price_factor, 4),
                "adj_low": round(raw_low * cum_price_factor, 4),
                "adj_close": round(raw_close * cum_price_factor, 4),
                "volume": adj_volume,
                "raw_volume": raw_vol,
                "cum_factor": cum_price_factor
            })

        return adjusted_series
