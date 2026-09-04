"""
Pillar 5: Quantitative Price Structure, Mansfield Relative Strength, and VCP Engine.

Implements Mark Minervini's *SEPA (Specific Entry Point Analysis)*, Stan Weinstein's
*Stage Analysis*, and the Mansfield Relative Strength against the benchmark (NIFTY 50).

Key Capabilities:
1. Stan Weinstein / Minervini Stage 2 Trend Template Validation:
   - Price > SMA50 > SMA150 > SMA200
   - 200-day Moving Average sloping upwards for >= 20 sessions
   - Price >= 25% above 52-week low and within 25% of 52-week high
2. Mansfield Relative Strength vs. NIFTY 50:
   - Quantifies outperformance momentum against the Indian benchmark
3. Volatility Contraction Pattern (VCP) & Volume Dry-Up:
   - Detects tightening price swings accompanied by volume dry-up (< 65% of 50DMA volume)
"""

from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


class PriceStructureEngine:
    """
    Evaluates price trend structure, benchmark relative strength, and accumulation signatures.
    """

    @staticmethod
    def _compute_sma(values: List[float], period: int) -> Optional[float]:
        """Helper to compute Simple Moving Average on a list."""
        if not values or len(values) < period or period <= 0:
            return None
        return sum(values[-period:]) / period

    @classmethod
    def evaluate_stage2_trend(
        cls,
        daily_closes: List[float],
        current_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Evaluates Minervini / Weinstein Stage 2 Trend Template.
        daily_closes should be ordered chronologically [oldest ... newest].
        """
        if not daily_closes or len(daily_closes) < 20:
            price = current_price or (daily_closes[-1] if daily_closes else None)
            return {
                "stage": "INSUFFICIENT_HISTORY",
                "badge_class": "badge-zinc",
                "is_stage2": False,
                "current_price": price,
                "sma_50": None,
                "sma_150": None,
                "sma_200": None,
                "sma_200_slope_positive": False,
                "distance_from_52w_low_pct": None,
                "distance_from_52w_high_pct": None,
                "summary": "Insufficient price candle history to evaluate moving averages."
            }

        price = current_price if current_price is not None else daily_closes[-1]
        n_days = len(daily_closes)

        # 52-week window (up to 250 trading days)
        window_52w = daily_closes[-min(250, n_days):]
        low_52w = min(window_52w)
        high_52w = max(window_52w)

        dist_low_pct = round(((price - low_52w) / low_52w) * 100.0, 1) if low_52w > 0 else 0.0
        dist_high_pct = round(((price - high_52w) / high_52w) * 100.0, 1) if high_52w > 0 else 0.0

        sma_50 = cls._compute_sma(daily_closes, 50) if n_days >= 50 else None
        sma_150 = cls._compute_sma(daily_closes, 150) if n_days >= 150 else None
        sma_200 = cls._compute_sma(daily_closes, 200) if n_days >= 200 else None

        # SMA 200 Slope (over last 20 trading days)
        sma_200_slope_positive = False
        if n_days >= 220:
            sma_200_now = sma_200
            sma_200_prev = cls._compute_sma(daily_closes[:-20], 200)
            if sma_200_now is not None and sma_200_prev is not None:
                sma_200_slope_positive = bool(sma_200_now > sma_200_prev)
        elif sma_200 is not None:
            # Fallback if between 200 and 220 days
            sma_200_slope_positive = price > sma_200

        # Stage Classification
        is_stage2 = False
        if sma_50 and sma_150 and sma_200:
            is_ma_aligned = (price > sma_50) and (sma_50 > sma_150) and (sma_150 > sma_200)
            is_above_support = dist_low_pct >= 25.0 and dist_high_pct >= -25.0

            if is_ma_aligned and sma_200_slope_positive and is_above_support:
                is_stage2 = True
                stage = "STAGE_2_UPTREND"
                badge = "badge-emerald"
                summary = f"Confirmed Stage 2 Uptrend: Price > 50DMA > 150DMA > 200DMA with rising baseline (+{dist_low_pct:.1f}% from 52w low)."
            elif price < sma_50 and (sma_150 < sma_200 or price < sma_200):
                stage = "STAGE_4_DECLINE"
                badge = "badge-rose"
                summary = "Stage 4 Downtrend: Major moving averages breached; institutional distribution."
            elif price > sma_200 and not is_ma_aligned:
                stage = "STAGE_1_ACCUMULATION"
                badge = "badge-teal"
                summary = "Stage 1 Basing / Accumulation: Consolidating above 200DMA without full alignment."
            else:
                stage = "STAGE_3_TOPPING"
                badge = "badge-amber"
                summary = "Stage 3 Topping / Transition: Choppy price action near highs with deteriorating momentum."
        elif sma_50 and price > sma_50:
            stage = "STAGE_2_EMERGING"
            badge = "badge-teal"
            is_stage2 = True
            summary = "Emerging short-term uptrend above 50DMA (limited 200DMA history)."
        else:
            stage = "UNCERTAIN_STRUCTURE"
            badge = "badge-zinc"
            summary = "Price structure neutral / insufficient historical depth."

        return {
            "stage": stage,
            "badge_class": badge,
            "is_stage2": is_stage2,
            "current_price": price,
            "sma_50": round(sma_50, 2) if sma_50 else None,
            "sma_150": round(sma_150, 2) if sma_150 else None,
            "sma_200": round(sma_200, 2) if sma_200 else None,
            "sma_200_slope_positive": sma_200_slope_positive,
            "distance_from_52w_low_pct": dist_low_pct,
            "distance_from_52w_high_pct": dist_high_pct,
            "summary": summary
        }

    @classmethod
    def calculate_mansfield_relative_strength(
        cls,
        stock_closes: List[float],
        benchmark_closes: List[float],
        base_period: int = 50
    ) -> Tuple[Optional[float], str, str]:
        """
        Computes Mansfield Relative Strength against NIFTY 50 benchmark.
        Formula:
          RS_t = Stock_t / Benchmark_t
          Mansfield_RS_t = ((RS_t / SMA_50(RS)) - 1.0) * 100.0
        """
        if (
            not stock_closes
            or not benchmark_closes
            or len(stock_closes) < base_period
            or len(benchmark_closes) < base_period
        ):
            return None, "RS_DATA_UNAVAILABLE", "badge-zinc"

        # Align lengths
        min_len = min(len(stock_closes), len(benchmark_closes))
        s_aligned = stock_closes[-min_len:]
        b_aligned = benchmark_closes[-min_len:]

        # Compute relative ratio series
        rs_series = []
        for s_val, b_val in zip(s_aligned, b_aligned):
            if b_val > 0:
                rs_series.append(s_val / b_val)
            else:
                rs_series.append(1.0)

        if len(rs_series) < base_period:
            return None, "RS_PERIOD_SHORT", "badge-zinc"

        rs_current = rs_series[-1]
        rs_sma = cls._compute_sma(rs_series, base_period)

        if rs_sma is None or rs_sma <= 0:
            return None, "RS_UNDEFINED", "badge-zinc"

        mansfield_score = round(((rs_current / rs_sma) - 1.0) * 100.0, 2)

        if mansfield_score >= 10.0:
            status = "STRONG_OUTPERFORMANCE"
            badge = "badge-emerald"
        elif mansfield_score > 0.0:
            status = "POSITIVE_RELATIVE_STRENGTH"
            badge = "badge-teal"
        elif mansfield_score >= -10.0:
            status = "LAGGING_BENCHMARK"
            badge = "badge-amber"
        else:
            status = "SEVERE_UNDERPERFORMANCE"
            badge = "badge-rose"

        return mansfield_score, status, badge

    @classmethod
    def detect_vcp_compression(
        cls,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float],
        lookback: int = 40
    ) -> Dict[str, Any]:
        """
        Detects Volatility Contraction Pattern (VCP) and volume dry-up absorption.
        """
        if (
            not closes
            or len(closes) < lookback
            or not highs
            or not lows
            or not volumes
            or len(volumes) < lookback
        ):
            return {
                "is_vcp_detected": False,
                "volume_dryup_ratio": None,
                "volatility_contraction_ratio": None,
                "summary": "Insufficient candle depth for VCP pattern recognition."
            }

        # Recent 10-day range vs Prior 30-day range
        recent_range = max(highs[-10:]) - min(lows[-10:])
        prior_range = max(highs[-lookback:-10]) - min(lows[-lookback:-10])

        volatility_contraction_ratio = round(recent_range / prior_range, 2) if prior_range > 0 else 1.0

        # Volume Dry-Up: Latest 5-day avg volume vs 50-day (or lookback) avg volume
        recent_vol = sum(volumes[-5:]) / 5.0
        avg_vol = sum(volumes[-lookback:]) / float(lookback)

        volume_dryup_ratio = round(recent_vol / avg_vol, 2) if avg_vol > 0 else 1.0

        # VCP Trigger: Range tightens by >= 40% (ratio <= 0.60) and Volume dries up (ratio <= 0.70)
        is_vcp = bool(volatility_contraction_ratio <= 0.60 and volume_dryup_ratio <= 0.70)

        if is_vcp:
            summary = f"VCP Compression Confirmed: Volatility tightened to {volatility_contraction_ratio * 100:.0f}% with volume dry-up ({volume_dryup_ratio * 100:.0f}% of average)."
        else:
            summary = "No active VCP compression signature."

        return {
            "is_vcp_detected": is_vcp,
            "volume_dryup_ratio": volume_dryup_ratio,
            "volatility_contraction_ratio": volatility_contraction_ratio,
            "summary": summary
        }

    @classmethod
    def audit_price_structure(
        cls,
        daily_closes: List[float],
        benchmark_closes: Optional[List[float]] = None,
        daily_highs: Optional[List[float]] = None,
        daily_lows: Optional[List[float]] = None,
        daily_volumes: Optional[List[float]] = None,
        current_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Runs full Pillar 5 Price Structure audit.
        """
        stage_eval = cls.evaluate_stage2_trend(daily_closes, current_price)

        mansfield_score, rs_status, rs_badge = None, "RS_UNKNOWN", "badge-zinc"
        if benchmark_closes:
            mansfield_score, rs_status, rs_badge = cls.calculate_mansfield_relative_strength(
                daily_closes, benchmark_closes
            )

        vcp_eval = {"is_vcp_detected": False, "volume_dryup_ratio": None, "volatility_contraction_ratio": None, "summary": "N/A"}
        if daily_highs and daily_lows and daily_volumes:
            vcp_eval = cls.detect_vcp_compression(daily_highs, daily_lows, daily_closes, daily_volumes)

        # Technical Score (0 - 100)
        score = 0
        if stage_eval["is_stage2"]:
            score += 50
        elif stage_eval["stage"] == "STAGE_1_ACCUMULATION":
            score += 30

        if mansfield_score is not None:
            if mansfield_score > 10.0:
                score += 30
            elif mansfield_score > 0.0:
                score += 20
            elif mansfield_score > -5.0:
                score += 10

        if vcp_eval.get("is_vcp_detected"):
            score += 20

        score = min(100, score)

        return {
            "stage_analysis": stage_eval,
            "mansfield_rs": {
                "score": mansfield_score,
                "status": rs_status,
                "badge_class": rs_badge
            },
            "vcp_analysis": vcp_eval,
            "technical_score": score,
            "is_stage4_circuit_breaker": bool(stage_eval["stage"] == "STAGE_4_DECLINE")
        }
