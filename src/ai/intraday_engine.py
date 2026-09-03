"""
Intraday Trading Engine — Daily Volatility Breakouts & ADV Volume Surges (1-Day Horizon).

Evaluates opening price velocity, volume acceleration against 20-day ADV,
and computes strict 1:2.0 Risk/Reward trade setups with ATR volatility stops.
"""

import logging
from datetime import date
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from src.analytics.feature_engine import FeatureEngine
from src.db.models import Company, DailyPriceRaw

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntradayEngine:
    """
    Dedicated 1-Day Intraday Momentum Breakout & Volatility Engine.
    Horizon: 1 Day (Session close exit).
    """
    MODEL_VERSION = "v2.0-intraday-breakout"

    @staticmethod
    def evaluate_company(db: Session, company_id: str, as_of_date: date) -> Optional[Dict[str, Any]]:
        prices = db.query(DailyPriceRaw).filter(
            DailyPriceRaw.company_id == company_id,
            DailyPriceRaw.trading_date <= as_of_date
        ).order_by(DailyPriceRaw.trading_date.desc()).limit(30).all()

        if len(prices) < 15:
            return None

        latest = prices[0]
        prev = prices[1]

        comp = db.query(Company).filter_by(company_id=company_id).first()
        symbol = comp.nse_symbol if comp else "UNKNOWN"
        name = comp.company_name if comp else "Unknown Company"

        # Calculate 20-day ADV volume surge
        avg_vol = sum(p.volume for p in prices[:20]) / 20.0
        vol_spike = round(latest.volume / avg_vol, 2) if avg_vol > 0 else 1.0

        ret_1d = round(((latest.close_price - prev.close_price) / prev.close_price) * 100.0, 2) if prev.close_price > 0 else 0.0

        # Calculate 14-day ATR
        highs = [p.high_price for p in reversed(prices)]
        lows = [p.low_price for p in reversed(prices)]
        closes = [p.close_price for p in reversed(prices)]
        atr, atr_pct = FeatureEngine._calculate_atr(highs, lows, closes, period=14)

        entry_price = round(latest.close_price, 2)

        # ──────────────────────────────────────────────────────────────
        # Volatility Parity Stop-Loss and Target (Strict 1:2.0 RR)
        # ──────────────────────────────────────────────────────────────
        sl_distance = max(entry_price * 0.008, 1.5 * atr)
        stop_loss_price = round(entry_price - sl_distance, 2)

        target_distance = 2.0 * sl_distance
        target_price = round(entry_price + target_distance, 2)

        risk_pct = round((sl_distance / entry_price) * 100.0, 2)
        target_gain_pct = round((target_distance / entry_price) * 100.0, 2)

        # Intraday Conviction Score
        intraday_score = min(99, max(45, int(65 + (vol_spike * 6.0) + (ret_1d * 1.5))))

        setup_name = "MOMENTUM_EXPANSION_BREAKOUT" if (ret_1d > 0.5 and vol_spike >= 1.3) else ("MEAN_REVERSION_PULLBACK" if ret_1d < -1.5 else "RANGE_EXPANSION")

        thesis = []
        if vol_spike >= 1.5:
            thesis.append(f"Institutional volume surge: {vol_spike:.1f}x 20-day ADV")
        if ret_1d > 1.0:
            thesis.append(f"Strong 1-day momentum expansion ({ret_1d:+.2f}%)")
        thesis.append(f"Favorable 1:2.0 risk-reward setup backed by Rs.{atr:.1f} ATR")

        risks = [
            f"Hard Stop-Loss: Rs.{stop_loss_price:,.2f} (-{risk_pct}%)",
            "Mandatory intraday square-off by 3:15 PM IST"
        ]

        return {
            "company_id": company_id,
            "symbol": symbol,
            "company_name": name,
            "horizon": "1-Day Intraday",
            "model_version": IntradayEngine.MODEL_VERSION,
            "as_of_date": as_of_date.isoformat(),
            "intraday_score": intraday_score,
            "setup_name": setup_name,
            "entry_price": entry_price,
            "stop_loss": stop_loss_price,
            "target_price": target_price,
            "expected_gain_pct": target_gain_pct,
            "risk_pct": risk_pct,
            "risk_reward_ratio": "1:2.0",
            "atr_14": round(atr, 2),
            "volume_spike_ratio": vol_spike,
            "return_1d_pct": ret_1d,
            "thesis_drivers": thesis,
            "risk_invalidation": risks
        }
