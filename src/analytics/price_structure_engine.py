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
        base_period: int = 50,
        stock_dates: Optional[List[Any]] = None,
        benchmark_dates: Optional[List[Any]] = None
    ) -> Tuple[Optional[float], str, str]:
        """
        Computes Mansfield Relative Strength against NIFTY 50 benchmark.
        Formula:
          RS_t = Stock_t / Benchmark_t
          Mansfield_RS_t = ((RS_t / SMA_50(RS)) - 1.0) * 100.0
        Supports calendar-date alignment when dates or dicts are provided.
        """
        if not stock_closes or not benchmark_closes:
            return None, "RS_DATA_UNAVAILABLE", "badge-zinc"

        # 1. Date alignment if dictionaries or date lists are supplied
        if isinstance(stock_closes, dict) and isinstance(benchmark_closes, dict):
            common_dates = sorted(set(stock_closes.keys()) & set(benchmark_closes.keys()))
            s_aligned = [stock_closes[d] for d in common_dates]
            b_aligned = [benchmark_closes[d] for d in common_dates]
        elif stock_dates and benchmark_dates and len(stock_dates) == len(stock_closes) and len(benchmark_dates) == len(benchmark_closes):
            s_map = dict(zip(stock_dates, stock_closes))
            b_map = dict(zip(benchmark_dates, benchmark_closes))
            common_dates = sorted(set(s_map.keys()) & set(b_map.keys()))
            s_aligned = [s_map[d] for d in common_dates]
            b_aligned = [b_map[d] for d in common_dates]
        else:
            # Length alignment fallback for raw unindexed sequences
            min_len = min(len(stock_closes), len(benchmark_closes))
            s_aligned = stock_closes[-min_len:]
            b_aligned = benchmark_closes[-min_len:]

        if len(s_aligned) < base_period or len(b_aligned) < base_period:
            return None, "RS_DATA_UNAVAILABLE", "badge-zinc"

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
        current_price: Optional[float] = None,
        trading_dates: Optional[List[Any]] = None,
        benchmark_dates: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Runs full Pillar 5 Price Structure audit.
        """
        stage_eval = cls.evaluate_stage2_trend(daily_closes, current_price)

        mansfield_score, rs_status, rs_badge = None, "RS_UNKNOWN", "badge-zinc"
        if benchmark_closes:
            mansfield_score, rs_status, rs_badge = cls.calculate_mansfield_relative_strength(
                daily_closes,
                benchmark_closes,
                stock_dates=trading_dates,
                benchmark_dates=benchmark_dates
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

    @staticmethod
    def _compute_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
        """Calculates Average True Range over specified lookback."""
        if not highs or not lows or not closes or len(closes) < 2:
            return None
        tr_list = []
        for i in range(1, len(closes)):
            h = highs[i]
            l = lows[i]
            pc = closes[i - 1]
            tr = max(h - l, abs(h - pc), abs(l - pc))
            tr_list.append(tr)
        if not tr_list:
            return None
        lookback = min(len(tr_list), period)
        return sum(tr_list[-lookback:]) / float(lookback)

    @classmethod
    def evaluate_minervini_8point_template(
        cls,
        daily_closes: List[float],
        current_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Evaluates Mark Minervini's 8-Point Stage 2 Trend Template:
        1. Price > SMA150 & Price > SMA200
        2. SMA150 > SMA200
        3. 200-day MA trending up for >= 20 sessions
        4. SMA50 > SMA150 & SMA50 > SMA200
        5. Price > SMA50
        6. Price >= 25% above 52-week low
        7. Price within 25% of 52-week high
        """
        if not daily_closes or len(daily_closes) < 20:
            return {
                "is_template_passed": False,
                "passed_criteria_count": 0,
                "total_criteria": 7,
                "details": "Insufficient history",
                "sma_50": None,
                "sma_150": None,
                "sma_200": None,
                "high_52w": current_price or 0.0,
                "low_52w": current_price or 0.0
            }

        price = current_price if current_price is not None else daily_closes[-1]
        n_days = len(daily_closes)

        sma_50 = cls._compute_sma(daily_closes, 50) if n_days >= 50 else None
        sma_150 = cls._compute_sma(daily_closes, 150) if n_days >= 150 else None
        sma_200 = cls._compute_sma(daily_closes, 200) if n_days >= 200 else None

        window_52w = daily_closes[-min(250, n_days):]
        low_52w = min(window_52w) if window_52w else price
        high_52w = max(window_52w) if window_52w else price

        dist_low_pct = ((price - low_52w) / low_52w) * 100.0 if low_52w > 0 else 0.0
        dist_high_pct = ((price - high_52w) / high_52w) * 100.0 if high_52w > 0 else 0.0

        # SMA200 slope
        sma_200_rising = False
        if n_days >= 220 and sma_200 is not None:
            sma_200_prev = cls._compute_sma(daily_closes[:-20], 200)
            sma_200_rising = bool(sma_200_prev is not None and sma_200 > sma_200_prev)
        elif sma_200 is not None:
            sma_200_rising = price > sma_200

        criteria = {
            "c1_price_above_150_200": bool(sma_150 and sma_200 and price > sma_150 and price > sma_200) if (sma_150 and sma_200) else bool(sma_50 and price > sma_50),
            "c2_150_above_200": bool(sma_150 and sma_200 and sma_150 > sma_200) if (sma_150 and sma_200) else True,
            "c3_200_rising": bool(sma_200_rising),
            "c4_50_above_150_200": bool(sma_50 and sma_150 and sma_200 and sma_50 > sma_150 and sma_50 > sma_200) if (sma_50 and sma_150 and sma_200) else bool(sma_50 and price > sma_50),
            "c5_price_above_50": bool(sma_50 and price > sma_50) if sma_50 else True,
            "c6_dist_low_25pct": bool(dist_low_pct >= 25.0),
            "c7_dist_high_25pct": bool(dist_high_pct >= -25.0),
        }
        passed_count = sum(1 for v in criteria.values() if v)
        is_passed = passed_count >= 5

        return {
            "is_template_passed": is_passed,
            "passed_criteria_count": passed_count,
            "total_criteria": len(criteria),
            "criteria": criteria,
            "sma_50": round(sma_50, 2) if sma_50 else None,
            "sma_150": round(sma_150, 2) if sma_150 else None,
            "sma_200": round(sma_200, 2) if sma_200 else None,
            "dist_low_pct": round(dist_low_pct, 1),
            "dist_high_pct": round(dist_high_pct, 1),
            "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2)
        }

    @classmethod
    def audit_swing_setup(
        cls,
        daily_closes: List[float],
        daily_highs: List[float],
        daily_lows: List[float],
        daily_volumes: List[float],
        current_price: Optional[float] = None,
        benchmark_closes: Optional[List[float]] = None,
        sector_name: str = "General"
    ) -> Dict[str, Any]:
        """
        Executes institutional 2-6 week / 45-day positional swing trading analysis.
        Implements:
        1. Minervini 8-Point Trend Template
        2. Normalized Volatility Contraction (ATR10 / ATR30)
        3. Volume Dry-Up in Context of Price Tightness (Vol5 / Vol40)
        4. Up/Down Volume Accumulation Signature & Day Counts
        5. Adaptive Pivot Buffer (ATR/Spread aligned)
        6. Structural Invalidation Stop-Loss & Position Sizing
        7. Dual Targets (Conservative Base Target T1 & 30-45 Day Positional T2)
        8. Expected Value Score & Normalized Swing Readiness (0-100)
        9. Actionability States (including FAILED_SETUP detection)
        """
        if not daily_closes or len(daily_closes) < 10 or not daily_highs or not daily_lows or not daily_volumes:
            p = current_price or (daily_closes[-1] if daily_closes else 100.0)
            return {
                "is_active": False,
                "setup_type": "BASE_CONSOLIDATION",
                "pivot_entry_price": round(p * 1.02, 2),
                "raw_pivot_price": round(p * 1.02, 2),
                "adjusted_pivot_entry": round(p * 1.02, 2),
                "adaptive_pivot_buffer": round(p * 0.002, 2),
                "wick_rejection_detected": False,
                "upper_wick_ratio": 0.0,
                "has_micro_handle": False,
                "handle_quality": "INSUFFICIENT_DATA",
                "handle_tightness_ratio": 1.0,
                "stop_loss_price": round(p * 0.95, 2),
                "structural_stop_reason": "Insufficient Candle Depth",
                "risk_pct": 5.0,
                "suggested_position_size_pct": 10.0,
                "tranche_1_probe_pct": 50.0,
                "tranche_1_trigger_price": round(p * 1.02, 2),
                "tranche_2_pyramid_pct": 50.0,
                "tranche_2_trigger_price": round(p * 1.045, 2),
                "breakeven_milestone_price": round(p * 1.07, 2),
                "target_price_t1": round(p * 1.10, 2),
                "target_price_t2": round(p * 1.18, 2),
                "risk_reward_ratio": 2.0,
                "expected_value_score": 50.0,
                "timeframe": "2-6 Weeks (Positional Swing)",
                "atr_10d": round(p * 0.02, 2),
                "atr_30d": round(p * 0.025, 2),
                "atr_20d": round(p * 0.02, 2),
                "atr_contraction_ratio": 1.0,
                "volatility_contraction_delta_pct": 0.0,
                "volume_5d_avg": 100000.0,
                "volume_40d_avg": 100000.0,
                "volume_dryup_ratio": 1.0,
                "volume_dryup_delta_pct": 0.0,
                "up_down_volume_ratio": 1.0,
                "up_days_count": 5,
                "down_days_count": 5,
                "pivot_distance_pct": 0.0,
                "actionability_status": "CONSTRUCTING_BASE",
                "trailing_stop_guide": "10 EMA (Momentum) / 20 EMA (Positional)",
                "sector_relative_strength": "NEUTRAL",
                "entry_quality_score": 50.0,
                "tape_confirmation_score": 50.0,
                "volume_structure_score": 50.0,
                "risk_reward_score": 50.0,
                "swing_readiness_score": 50.0,
                "status_notes": "Insufficient price candle history to evaluate institutional swing parameters."
            }

        price = current_price if current_price is not None else daily_closes[-1]

        # 1. Minervini Trend Template Validation
        template = cls.evaluate_minervini_8point_template(daily_closes, price)
        sma_50 = template["sma_50"]
        sma_200 = template["sma_200"]
        high_52w = template["high_52w"]
        dist_50_pct = round(((price - sma_50) / sma_50) * 100.0, 1) if sma_50 else 0.0
        dist_52w_pct = round(((price - high_52w) / high_52w) * 100.0, 1) if high_52w > 0 else 0.0

        # 2. Normalized Volatility Contraction (ATR10 / ATR30)
        atr_10 = cls._compute_atr(daily_highs, daily_lows, daily_closes, 10) or (price * 0.02)
        atr_30 = cls._compute_atr(daily_highs, daily_lows, daily_closes, 30) or atr_10
        atr_20 = cls._compute_atr(daily_highs, daily_lows, daily_closes, 20) or atr_10

        atr_contraction_ratio = round(atr_10 / atr_30, 2) if atr_30 > 0 else 1.0
        volatility_contraction_delta_pct = round((atr_contraction_ratio - 1.0) * 100.0, 1)

        # 3. Normalized Volume Dry-up (Vol5 / Vol40) with Price Support Holding Context
        vol_5 = sum(daily_volumes[-5:]) / 5.0 if len(daily_volumes) >= 5 else daily_volumes[-1]
        lookback_vol = min(40, len(daily_volumes))
        vol_40 = sum(daily_volumes[-lookback_vol:]) / float(lookback_vol) if lookback_vol > 0 else vol_5
        volume_dryup_ratio = round(vol_5 / vol_40, 2) if vol_40 > 0 else 1.0
        volume_dryup_delta_pct = round((volume_dryup_ratio - 1.0) * 100.0, 1)

        # Base floor & support holding check
        base_low = min(daily_lows[-min(30, len(daily_lows)):])
        base_high = max(daily_highs[-min(30, len(daily_highs)):])
        base_range = max(0.1, base_high - base_low)
        base_pos = (price - base_low) / base_range
        recent_low_5d = min(daily_lows[-min(5, len(daily_lows)):])
        support_holding = bool(recent_low_5d >= base_low * 0.985)

        # 3-Tier Contraction Taxonomy
        if base_pos >= 0.45 and support_holding and dist_50_pct >= -2.0:
            contraction_quality = "HEALTHY_CONTRACTION"
        elif (not support_holding) or dist_50_pct < -4.0:
            contraction_quality = "DANGEROUS_CONTRACTION"
        else:
            contraction_quality = "NEUTRAL_CONTRACTION"

        # Rolling Volatility Compression Percentile (vs historical distribution)
        hist_ratios = []
        if len(daily_closes) >= 45:
            for k in range(30, len(daily_closes), 3):
                sub_c = daily_closes[:k]
                sub_h = daily_highs[:k]
                sub_l = daily_lows[:k]
                a10 = cls._compute_atr(sub_h, sub_l, sub_c, 10)
                a30 = cls._compute_atr(sub_h, sub_l, sub_c, 30)
                if a10 and a30 and a30 > 0:
                    hist_ratios.append(a10 / a30)
        if hist_ratios:
            vol_compression_percentile = round((sum(1 for r in hist_ratios if r <= atr_contraction_ratio) / len(hist_ratios)) * 100.0, 1)
        else:
            vol_compression_percentile = 50.0

        # Closing Range Location over last 5 sessions (accumulation behavior)
        locs = [((daily_closes[i] - daily_lows[i]) / max(0.01, daily_highs[i] - daily_lows[i])) for i in range(-min(5, len(daily_closes)), 0)]
        closing_range_location_pct = round(sum(locs) / len(locs) * 100.0, 1) if locs else 50.0

        # 4. Up/Down Volume Accumulation Signature & Distribution Days (last 20 sessions)
        rec_len = min(20, len(daily_closes))
        up_vol, down_vol = 0.0, 0.0
        up_days, down_days = 0, 0
        distribution_days_count = 0
        start_idx = len(daily_closes) - rec_len + 1
        for i in range(start_idx, len(daily_closes)):
            v = float(daily_volumes[i]) if i < len(daily_volumes) else 0.0
            if daily_closes[i] >= daily_closes[i - 1]:
                up_vol += v
                up_days += 1
            else:
                down_vol += v
                down_days += 1
                if v > 1.3 * vol_40:
                    distribution_days_count += 1
        up_down_vol_ratio = round(up_vol / max(1.0, down_vol), 2)

        # 5. Market Regime Detection (Benchmark Trend)
        market_regime = "BULL_MOMENTUM"
        if benchmark_closes and len(benchmark_closes) >= 50:
            b_p = benchmark_closes[-1]
            b_sma50 = cls._compute_sma(benchmark_closes, 50)
            b_sma200 = cls._compute_sma(benchmark_closes, 200) if len(benchmark_closes) >= 200 else b_sma50
            if b_sma50 and b_sma200 and b_p > b_sma50 > b_sma200:
                market_regime = "BULL_MOMENTUM"
            elif b_sma200 and b_p > b_sma200:
                market_regime = "BULL_CORRECTION"
            else:
                market_regime = "BEAR_DEFENSIVE"

        # 6. Setup Geometry Classification
        is_tight_contraction = bool(atr_contraction_ratio <= 0.75)
        is_vol_dryup = bool(volume_dryup_ratio <= 0.75)

        if is_tight_contraction and is_vol_dryup and contraction_quality == "HEALTHY_CONTRACTION":
            setup_type = "VCP_CONTRACTION_BREAKOUT"
        elif -2.5 <= dist_50_pct <= 2.5 and sma_50 and sma_50 > (sma_200 or 0):
            setup_type = "50EMA_PULLBACK"
        elif dist_52w_pct >= -4.0:
            setup_type = "52W_HIGH_BREAKOUT"
        else:
            setup_type = "BASE_CONSOLIDATION"

        # 7. Adaptive Pivot Buffer & Pivot Entry Determination
        adaptive_buffer = round(max(0.12 * atr_10, price * 0.0015), 2)
        if setup_type == "VCP_CONTRACTION_BREAKOUT":
            raw_pivot = max(daily_highs[-min(8, len(daily_highs)):])
        elif setup_type == "50EMA_PULLBACK":
            raw_pivot = max(daily_highs[-min(3, len(daily_highs)):])
        elif setup_type == "52W_HIGH_BREAKOUT":
            raw_pivot = high_52w
        else:
            raw_pivot = max(daily_highs[-min(20, len(daily_highs)):])
        raw_pivot_price = round(raw_pivot + adaptive_buffer, 2)

        # Upper-Wick Rejection Sentinel (Anti-Trap Pivot)
        wick_rejection_detected = False
        upper_wick_ratio = 0.0
        trap_wick_high = raw_pivot
        lookback_wick = min(3, len(daily_closes))
        for idx in range(-lookback_wick, 0):
            bar_h = daily_highs[idx]
            bar_l = daily_lows[idx]
            bar_c = daily_closes[idx]
            bar_rng = max(0.01, bar_h - bar_l)
            u_wick = bar_h - bar_c
            w_ratio = u_wick / bar_rng
            crl_bar = (bar_c - bar_l) / bar_rng
            if bar_h >= raw_pivot * 0.992:
                upper_wick_ratio = max(upper_wick_ratio, round(w_ratio, 2))
                if w_ratio >= 0.35 and crl_bar < 0.50:
                    wick_rejection_detected = True
                    trap_wick_high = max(trap_wick_high, bar_h)

        if wick_rejection_detected:
            adjusted_pivot_entry = round(max(raw_pivot_price, trap_wick_high + adaptive_buffer), 2)
            pivot_entry = adjusted_pivot_entry
        else:
            adjusted_pivot_entry = raw_pivot_price
            pivot_entry = raw_pivot_price

        # Micro-Handle / Final Contraction Gate
        handle_days = min(5, len(daily_closes))
        recent_5d_high = max(daily_highs[-handle_days:])
        recent_5d_low = min(daily_lows[-handle_days:])
        handle_range = recent_5d_high - recent_5d_low
        handle_tightness_ratio = round(handle_range / max(0.1, atr_10), 2)
        handle_vol_ratio = volume_dryup_ratio

        if handle_tightness_ratio <= 1.8 and handle_vol_ratio <= 0.80:
            handle_quality = "A_PRIME_HANDLE"
            has_micro_handle = True
        elif handle_tightness_ratio <= 2.5:
            handle_quality = "LOOSE_HANDLE"
            has_micro_handle = True
        else:
            handle_quality = "V_SHAPE_EXTENDED"
            has_micro_handle = False

        # 8. Structural Invalidation Stop-Loss & Position Sizing
        if setup_type == "VCP_CONTRACTION_BREAKOUT":
            structural_floor = min(daily_lows[-min(8, len(daily_lows)):])
            stop_reason = "Contraction Trough Support"
        elif setup_type == "50EMA_PULLBACK":
            structural_floor = min(daily_lows[-min(5, len(daily_lows)):]) if len(daily_lows) >= 5 else (sma_50 * 0.99 if sma_50 else price * 0.96)
            stop_reason = "50-Day EMA Baseline"
        else:
            structural_floor = min(daily_lows[-min(20, len(daily_lows)):])
            stop_reason = "Base Swing Low Support"

        structural_stop = structural_floor - round(0.05 * atr_10, 2)
        max_atr_stop = pivot_entry - round(2.0 * atr_10, 2)
        min_atr_stop = pivot_entry - round(0.5 * atr_10, 2)
        candidate_stop = min(min_atr_stop, max(structural_stop, max_atr_stop))
        stop_loss_price = round(candidate_stop, 2)

        risk_pct = round(((pivot_entry - stop_loss_price) / pivot_entry) * 100.0, 2)
        
        # Position sizing budgeting for 1.0% account risk without artificial 4% floor
        if risk_pct > 8.5:
            suggested_position_size = 0.0
            stop_reason += " [EXCESSIVE_RISK > 8.5% -> 0% ALLOCATION]"
        else:
            raw_size = 1.0 / max(0.01, risk_pct / 100.0)
            suggested_position_size = round(min(20.0, max(0.0, raw_size)), 1)

        if market_regime == "BEAR_DEFENSIVE":
            suggested_position_size = round(suggested_position_size * 0.5, 1)

        # 9. Dual Targets (Conservative T1 & 30-45 Day Positional T2)
        base_depth = max(atr_10 * 2.0, pivot_entry - base_low)
        if price < high_52w * 0.97:
            t1 = min(high_52w, round(pivot_entry + max(base_depth * 0.85, 1.8 * atr_10), 2))
            t2 = round(pivot_entry + max(base_depth * 1.5, 3.2 * atr_10), 2)
        else:
            t1 = round(pivot_entry + max(base_depth, 2.0 * atr_10), 2)
            t2 = round(pivot_entry + max(base_depth * 1.618, 4.0 * atr_10), 2)

        target_price_t1 = round(t1, 2)
        target_price_t2 = round(t2, 2)

        risk_dist = max(0.1, pivot_entry - stop_loss_price)
        reward_dist = max(0.1, target_price_t1 - pivot_entry)
        risk_reward_ratio = round(reward_dist / risk_dist, 2)

        # 3-Stage Pyramiding & Free-Roll Protocol
        tranche_1_probe_pct = 50.0
        tranche_1_trigger_price = pivot_entry
        tranche_2_pyramid_pct = 50.0
        tranche_2_trigger_price = round(pivot_entry + (0.5 * risk_dist), 2)
        breakeven_milestone_price = round(pivot_entry + (1.0 * risk_dist), 2)
        trailing_exit_guide = "Sell 1/3 at Target 1; Trail remaining 2/3 along 10-EMA"

        # 10. Actionability State & Failed Breakout Detection
        pivot_distance_pct = round(((price - pivot_entry) / pivot_entry) * 100.0, 2)
        recent_3d_high = max(daily_highs[-min(3, len(daily_highs)):])
        if (recent_3d_high >= raw_pivot_price or recent_3d_high >= pivot_entry) and (price < raw_pivot_price * 0.985 or price < pivot_entry * 0.985):
            actionability_status = "FAILED_SETUP"
        elif pivot_distance_pct < -2.5:
            actionability_status = "CONSTRUCTING_BASE"
        elif -2.5 <= pivot_distance_pct <= 0.0:
            actionability_status = "TRIGGER_WATCH"
        elif 0.0 < pivot_distance_pct <= 2.5:
            actionability_status = "ACTIONABLE_BUY"
        elif 2.5 < pivot_distance_pct <= 5.0:
            actionability_status = "LATE_BUY_ZONE"
        else:
            actionability_status = "EXTENDED"

        # 11. Normalized Scoring (Each component strictly 0-100)
        # Entry Quality: Tightness (40) + Volume Dryup (30) + Proximity (30)
        tightness_pts = max(0.0, min(40.0, (1.0 - min(1.0, atr_contraction_ratio)) * 80.0))
        dryup_pts = max(0.0, min(30.0, (1.0 - min(1.0, volume_dryup_ratio)) * 60.0))
        prox_pts = 30.0 if actionability_status in ["TRIGGER_WATCH", "ACTIONABLE_BUY"] else (20.0 if actionability_status == "CONSTRUCTING_BASE" else 10.0)
        if contraction_quality == "HEALTHY_CONTRACTION":
            tightness_pts = min(40.0, tightness_pts + 5.0)
        entry_quality = round(tightness_pts + dryup_pts + prox_pts, 1)

        # Tape Confirmation: Trend template + MA alignment
        tape_score = 50.0
        if template["is_template_passed"]:
            tape_score += 30.0
        if dist_50_pct > 0:
            tape_score += 10.0
        if dist_52w_pct >= -15.0:
            tape_score += 10.0
        tape_score = min(100.0, max(20.0, tape_score))

        # Volume Structure: Positive Volume Asymmetry + Low Distribution Days
        ud_pts = min(50.0, (up_down_vol_ratio / 2.0) * 50.0)
        dist_deduction = min(20.0, distribution_days_count * 5.0)
        vd_pts = max(0.0, min(50.0, (1.0 - min(1.2, volume_dryup_ratio)) * 65.0) - dist_deduction)
        volume_structure = round(ud_pts + vd_pts, 1)

        # Risk/Reward Score normalized (0-100)
        rr_score = round(min(100.0, max(15.0, (risk_reward_ratio / 2.5) * 75.0)), 1)

        # Normalized Composite Swing Readiness Index (0-100)
        swing_readiness = round(
            (entry_quality * 0.35) +
            (tape_score * 0.30) +
            (volume_structure * 0.20) +
            (rr_score * 0.15), 1
        )

        # Empirical Calibration Lookup (Grounding EV in historical point-in-time replay)
        # Empirical Calibration Lookup (Layer 3: Informational empirical probability without circular feedback)
        try:
            from src.analytics.historical_swing_replay_engine import HistoricalSwingReplayEngine
            emp = HistoricalSwingReplayEngine.lookup_empirical_metrics(
                swing_readiness_score=swing_readiness,
                setup_type=setup_type,
                contraction_quality=contraction_quality,
                market_regime=market_regime
            )
        except Exception:
            emp = {
                "empirical_win_rate_pct": 50.0,
                "wilson_ci_95": [25.0, 75.0],
                "sample_size_evidence": "LOW",
                "empirical_profit_factor": 1.5,
                "empirical_avg_r": 0.8,
                "empirical_sample_size": 0,
                "empirical_avg_days_to_target": 15.0,
                "conditioning_level": "PRIOR_UNTESTED",
                "calibrated": False
            }

        # Expected Value Score (Grounding EV in empirical probability when sample is available, else prior)
        if emp.get("calibrated") and emp.get("empirical_sample_size", 0) >= 4:
            emp_win_prob = emp["empirical_win_rate_pct"] / 100.0
            ev = (emp_win_prob * risk_reward_ratio) - ((1.0 - emp_win_prob) * 1.0)
            ev_score = round(min(100.0, max(10.0, 50.0 + (ev * 22.0))), 1)
        else:
            win_prob = 0.40 + (0.12 if setup_type == "VCP_CONTRACTION_BREAKOUT" and contraction_quality == "HEALTHY_CONTRACTION" else 0.0) + (0.08 if up_down_vol_ratio >= 1.5 else 0.0) + (0.05 if template["is_template_passed"] else 0.0)
            if distribution_days_count >= 3:
                win_prob -= 0.10
            win_prob = min(0.75, max(0.25, win_prob))
            ev = (win_prob * risk_reward_ratio) - ((1.0 - win_prob) * 1.0)
            ev_score = round(min(100.0, max(10.0, 50.0 + (ev * 22.0))), 1)

        # ARCHITECTURAL PRINCIPLE: Layer 3 empirical metrics inform, but NEVER override Layer 2 structural invalidation
        is_active = bool(
            template["is_template_passed"] and
            actionability_status in ["TRIGGER_WATCH", "ACTIONABLE_BUY", "LATE_BUY_ZONE"] and
            risk_reward_ratio >= 1.7 and
            suggested_position_size > 0.0
        )

        ci = emp.get("wilson_ci_95", [0.0, 100.0])
        emp_note = f" [Hist Win P(T1): {emp['empirical_win_rate_pct']:.0f}% ({ci[0]:.0f}%-{ci[1]:.0f}%), PF: {emp['empirical_profit_factor']:.2f}x, N={emp['empirical_sample_size']} ({emp.get('sample_size_evidence', 'LOW')})]" if emp.get("empirical_sample_size", 0) > 0 else ""
        wick_note = f" [Trap Wick Rejected -> Pivot Adjusted to Rs.{adjusted_pivot_entry:.2f}]" if wick_rejection_detected else ""
        handle_note = f" [{handle_quality}]"

        status_notes = (
            f"{setup_type} ({contraction_quality}{handle_note}): ATR ratio {atr_contraction_ratio:.2f} (pctile {vol_compression_percentile:.0f}%), "
            f"Vol dry-up {volume_dryup_ratio:.2f} ({volume_dryup_delta_pct:+.1f}%). "
            f"Pivot Rs.{pivot_entry:.2f} ({pivot_distance_pct:+.1f}%){wick_note}. "
            f"Stop Rs.{stop_loss_price:.2f} (-{risk_pct:.1f}%, {stop_reason}). "
            f"Positive Vol Asymmetry {up_down_vol_ratio:.1f}x ({up_days}U/{down_days}D, {distribution_days_count} Dist). "
            f"R:R {risk_reward_ratio:.2f}x (T1 Rs.{target_price_t1:.2f}, T2 Rs.{target_price_t2:.2f}). "
            f"EV Score {ev_score:.0f}. Regime: {market_regime}.{emp_note}"
        )

        return {
            "is_active": is_active,
            "setup_type": setup_type,
            "pivot_entry_price": pivot_entry,
            "raw_pivot_price": raw_pivot_price,
            "adjusted_pivot_entry": adjusted_pivot_entry,
            "adaptive_pivot_buffer": adaptive_buffer,
            "wick_rejection_detected": wick_rejection_detected,
            "upper_wick_ratio": upper_wick_ratio,
            "has_micro_handle": has_micro_handle,
            "handle_quality": handle_quality,
            "handle_tightness_ratio": handle_tightness_ratio,
            "stop_loss_price": stop_loss_price,
            "structural_stop_reason": stop_reason,
            "risk_pct": risk_pct,
            "trade_risk_pct": risk_pct,
            "portfolio_risk_budget_pct": 1.0,
            "suggested_position_size_pct": suggested_position_size,
            "tranche_1_probe_pct": tranche_1_probe_pct,
            "tranche_1_trigger_price": tranche_1_trigger_price,
            "tranche_2_pyramid_pct": tranche_2_pyramid_pct,
            "tranche_2_trigger_price": tranche_2_trigger_price,
            "breakeven_milestone_price": breakeven_milestone_price,
            "target_price": target_price_t1,
            "target_price_t1": target_price_t1,
            "target_price_t2": target_price_t2,
            "risk_reward_ratio": risk_reward_ratio,
            "expected_value_score": ev_score,
            "timeframe": "2-6 Weeks (Positional Swing)",
            "atr_10d": round(atr_10, 2),
            "atr_30d": round(atr_30, 2),
            "atr_20d": round(atr_20, 2),
            "atr_contraction_ratio": atr_contraction_ratio,
            "volatility_contraction_delta_pct": volatility_contraction_delta_pct,
            "volume_5d_avg": round(vol_5, 1),
            "volume_40d_avg": round(vol_40, 1),
            "volume_dryup_ratio": volume_dryup_ratio,
            "volume_dryup_delta_pct": volume_dryup_delta_pct,
            "up_down_volume_ratio": up_down_vol_ratio,
            "up_days_count": up_days,
            "down_days_count": down_days,
            "pivot_distance_pct": pivot_distance_pct,
            "actionability_status": actionability_status,
            "contraction_quality": contraction_quality,
            "vol_compression_percentile": vol_compression_percentile,
            "distribution_days_count": distribution_days_count,
            "closing_range_location_pct": closing_range_location_pct,
            "market_regime": market_regime,
            "trailing_stop_guide": trailing_exit_guide,
            "sector_relative_strength": "NEUTRAL",
            "entry_quality_score": entry_quality,
            "tape_confirmation_score": tape_score,
            "volume_structure_score": volume_structure,
            "risk_reward_score": rr_score,
            "swing_readiness_score": swing_readiness,
            "empirical_win_rate_pct": emp.get("empirical_win_rate_pct", 0.0),
            "wilson_ci_low_pct": ci[0],
            "wilson_ci_high_pct": ci[1],
            "sample_size_evidence": emp.get("sample_size_evidence", "LOW"),
            "data_diversity": "MODERATE",
            "empirical_profit_factor": emp.get("empirical_profit_factor", 0.0),
            "empirical_avg_r": emp.get("empirical_avg_r", 0.0),
            "expected_r_multiple": emp.get("empirical_avg_r", 0.0),
            "empirical_sample_size": emp.get("empirical_sample_size", 0),
            "empirical_avg_days_to_target": emp.get("empirical_avg_days_to_target", 0.0),
            "mfe_pre_stop_avg_pct": emp.get("avg_mfe_pre_stop_pct", 0.0),
            "execution_risk_spread_r": 0.0,
            "status_notes": status_notes
        }
