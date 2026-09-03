"""
Swing Trading Engine — Positional Momentum & Technical Volatility Envelopes (2-4 Weeks).

Evaluates trend acceleration, Wilder RSI momentum, 50-DMA alignment, volume surges,
and establishes volatility-parity risk/reward trade parameters with 1.5x ATR stop loss.
"""

import logging
from datetime import date
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from src.analytics.feature_engine import FeatureEngine
from src.db.models import Company, DailyPriceRaw

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SwingEngine:
    """
    Dedicated Positional Swing Trading Engine.
    Horizon: 2 to 4 Weeks.
    """
    MODEL_VERSION = "v2.0-swing-momentum"

    @staticmethod
    def evaluate_company(db: Session, company_id: str, as_of_date: date) -> Optional[Dict[str, Any]]:
        feats = FeatureEngine.extract_features_as_of(db, company_id, as_of_date)

        comp = db.query(Company).filter_by(company_id=company_id).first()
        symbol = comp.nse_symbol if comp else "UNKNOWN"
        name = comp.company_name if comp else "Unknown Company"
        sector_name = comp.sector.sector_name if (comp and comp.sector) else "General"

        prices = db.query(DailyPriceRaw).filter(
            DailyPriceRaw.company_id == company_id,
            DailyPriceRaw.trading_date <= as_of_date
        ).order_by(DailyPriceRaw.trading_date.desc()).limit(60).all()

        if len(prices) < 15:
            return None

        current_price = prices[0].close_price
        if current_price <= 0:
            return None

        rsi = feats.get("rsi_14") or 50.0
        dist_sma20 = feats.get("dist_from_sma20_pct") or 0.0
        dist_sma50 = feats.get("dist_from_sma50_pct") or 0.0
        dist_sma200 = feats.get("dist_from_sma200_pct") or 0.0
        dist_52w_high = feats.get("dist_from_52w_high_pct") or -20.0
        vol_accel = feats.get("volume_acceleration_ratio") or 1.0

        # Calculate 14-day ATR for volatility-based risk budgeting
        highs = [p.high_price for p in reversed(prices)]
        lows = [p.low_price for p in reversed(prices)]
        closes = [p.close_price for p in reversed(prices)]
        atr, atr_pct = FeatureEngine._calculate_atr(highs, lows, closes, period=14)

        # ──────────────────────────────────────────────────────────────
        # Momentum Scoring Logic (0 - 100)
        # ──────────────────────────────────────────────────────────────
        # 1. RSI Sweet Spot Scoring (Peak conviction in 52 - 68 zone)
        if 52.0 <= rsi <= 68.0:
            rsi_score = 95.0
        elif 45.0 <= rsi < 52.0:
            rsi_score = 75.0
        elif 68.0 < rsi <= 78.0:
            rsi_score = 70.0  # Strong but slightly stretched
        elif rsi > 78.0:
            rsi_score = 45.0  # Overbought exhaustion risk
        else:
            rsi_score = 35.0  # Oversold / bearish momentum

        # 2. Moving Average Trend Alignment
        trend_score = 50.0
        if current_price >= (current_price / (1.0 + dist_sma50 / 100.0)):
            trend_score += 20.0  # Above 50-DMA
        if current_price >= (current_price / (1.0 + dist_sma200 / 100.0)):
            trend_score += 15.0  # Above 200-DMA
        if dist_sma20 > 0:
            trend_score += 10.0

        # 3. Relative Strength (Proximity to 52-week High)
        rs_score = max(20.0, min(95.0, (100.0 + dist_52w_high) * 0.95))

        # 4. Volume Expansion Trigger
        vol_score = 50.0 + min(40.0, (vol_accel - 1.0) * 35.0)

        # Composite Swing Momentum Score
        swing_score = int(
            (rsi_score * 0.35) +
            (trend_score * 0.30) +
            (rs_score * 0.20) +
            (vol_score * 0.15)
        )
        swing_score = min(99, max(20, swing_score))

        # ──────────────────────────────────────────────────────────────
        # Volatility-Parity Trade Parameters (2-4 Weeks)
        # ──────────────────────────────────────────────────────────────
        # Stop-Loss: 1.5x ATR below entry
        sl_distance = max(current_price * 0.015, 1.5 * atr)
        stop_loss_price = round(current_price - sl_distance, 2)

        # Expected Swing Target: +2.5x ATR (or minimum +5.0%)
        target_distance = max(current_price * 0.05, 2.5 * atr)
        target_price = round(current_price + target_distance, 2)
        expected_gain_pct = round((target_distance / current_price) * 100.0, 1)
        risk_pct = round((sl_distance / current_price) * 100.0, 1)
        risk_reward = round(target_distance / max(0.1, sl_distance), 1)

        # Classify Setup Type
        if dist_52w_high >= -5.0 and vol_accel >= 1.3:
            setup_type = "52W_HIGH_BREAKOUT"
        elif 52.0 <= rsi <= 65.0 and dist_sma50 > 0:
            setup_type = "TREND_MOMENTUM_EXPANSION"
        elif rsi < 45.0 and dist_sma200 > 0:
            setup_type = "200DMA_PULLBACK_REVERSAL"
        else:
            setup_type = "CONSOLIDATION_WATCH"

        thesis = []
        if 52.0 <= rsi <= 68.0:
            thesis.append(f"RSI in optimal momentum expansion zone ({rsi:.1f})")
        if dist_sma50 > 0:
            thesis.append(f"Strong trend support: Trading {dist_sma50:+.1f}% above 50-DMA")
        if vol_accel >= 1.2:
            thesis.append(f"Institutional volume surge ({vol_accel:.1f}x 20-day ADV)")
        if dist_52w_high >= -10.0:
            thesis.append(f"High relative strength ({dist_52w_high:+.1f}% from 52W High)")

        risks = [
            f"Exit trigger: Close below Stop Loss Rs.{stop_loss_price:,.2f} (-{risk_pct}%)",
            f"14-Day Volatility Risk: Daily ATR of Rs.{atr:.1f} ({atr_pct:.1f}%)"
        ]
        if rsi > 75.0:
            risks.append("Stretched momentum (Overbought RSI > 75)")

        return {
            "company_id": company_id,
            "symbol": symbol,
            "company_name": name,
            "sector": sector_name,
            "horizon": "2-4 Weeks",
            "model_version": SwingEngine.MODEL_VERSION,
            "as_of_date": as_of_date.isoformat(),
            "swing_score": swing_score,
            "setup_type": setup_type,
            "entry_price": round(current_price, 2),
            "stop_loss": stop_loss_price,
            "target_price": target_price,
            "expected_gain_pct": expected_gain_pct,
            "risk_pct": risk_pct,
            "risk_reward_ratio": f"1:{risk_reward}",
            "indicators": {
                "rsi_14": round(rsi, 1),
                "atr_14": round(atr, 2),
                "atr_pct": round(atr_pct, 2),
                "dist_sma50_pct": round(dist_sma50, 2),
                "dist_sma200_pct": round(dist_sma200, 2),
                "dist_52w_high_pct": round(dist_52w_high, 2),
                "volume_acceleration": round(vol_accel, 2)
            },
            "thesis_drivers": thesis if thesis else ["Moderate technical trend"],
            "risk_invalidation": risks
        }
