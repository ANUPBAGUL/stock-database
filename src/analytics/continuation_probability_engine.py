"""
Next-Day Follow-Through & Continuation Probability Engine.
Trendlyne-Referenced, Institutional-Grade Microstructure & Delivery Quant Engine.

Calculates the mathematical probability of a top gainer continuing upward tomorrow
versus suffering an intraday fade or mean-reversion trap.

Core Quantitative Dimensions:
1. Microstructure: Close Location Value (CLV), Relative Volume (RVOL), Upper-Wick Trap Sentinel.
2. Official NSE Delivery: Delivery %, 3-Day Delivery Velocity d(Delivery)/dt, Floating Supply Absorption Ratio (FSAR).
3. Institutional Elasticity: Extension from EMA20 in units of ATR14 (Rubber-Band Risk).
4. Trendlyne-Grade DVM: Durability, Valuation, Momentum Composite.
5. Horizon Tuning: Calibrated for TODAY (1D), WEEKLY (1W), and YEARLY (1Y).
6. 9:15 AM ORB-15 Playbook: Tactical rules for opening range breakout vs gap fade.
7. Devil's Advocate Sentinel: Tail-risk invalidation levels.
"""

import math
from typing import Dict, Any, List, Optional, Tuple

from src.mcp.sector_constituents_store import SectorConstituentsStore


class ContinuationProbabilityEngine:
    """
    Computes explainable, institutional-grade follow-through probabilities
    and actionable 2R/3R execution brackets.
    """

    @staticmethod
    def calculate_clv(high: float, low: float, close_px: float) -> float:
        """
        Close Location Value (CLV): Measures where the stock closed relative to its daily range.
        Formula: (Close - Low) / (High - Low)
        Range: 0.0 (closed at Low) to 1.0 (closed at High).
        """
        spread = high - low
        if spread <= 0.0001:
            return 0.5
        clv = (close_px - low) / spread
        return round(max(0.0, min(1.0, clv)), 4)

    @staticmethod
    def calculate_upper_wick_ratio(open_px: float, high: float, low: float, close_px: float) -> float:
        """
        Upper-Wick Trap Sentinel: Measures overhead rejection shadow.
        Formula: (High - max(Open, Close)) / (High - Low)
        """
        spread = high - low
        if spread <= 0.0001:
            return 0.0
        body_top = max(open_px, close_px)
        upper_wick = max(0.0, high - body_top)
        return round(upper_wick / spread, 4)

    @staticmethod
    def calculate_fsar(
        delivery_qty: int,
        float_shares: Optional[float] = None,
        total_shares: Optional[float] = None,
        promoter_holding_pct: Optional[float] = None
    ) -> Optional[float]:
        """
        Floating Supply Absorption Ratio (FSAR):
        Percentage of the entire circulating free float physically locked into demat today.
        Formula: (Deliverable Quantity / Free Float Shares) * 100

        If float_shares is omitted but total_shares and promoter_holding_pct are provided,
        derives free-float = total_shares * (1 - promoter_holding_pct / 100.0).
        """
        target_float = float_shares
        if (target_float is None or target_float <= 1000) and total_shares and total_shares > 1000:
            if promoter_holding_pct is not None and 0.0 <= promoter_holding_pct < 100.0:
                target_float = total_shares * (1.0 - (promoter_holding_pct / 100.0))
            else:
                target_float = total_shares * 0.50

        if target_float and target_float > 1000 and delivery_qty > 0:
            fsar = (delivery_qty / target_float) * 100.0
            return round(fsar, 3)
        return None

    @staticmethod
    def calculate_elasticity(cmp: float, ema20: Optional[float], atr: Optional[float]) -> float:
        """
        Institutional Elasticity Ratio (IER):
        Measures how far the stock is stretched from its 20-day mean in ATR units.
        Formula: (CMP - EMA20) / ATR14
        """
        if ema20 and atr and atr > 0.01:
            return round((cmp - ema20) / atr, 2)
        return 1.5

    @classmethod
    def evaluate_candidate(
        cls,
        stock: Dict[str, Any],
        delivery_info: Optional[Dict[str, Any]],
        dvm_scores: Dict[str, float],
        horizon: str = "TODAY",
        macro_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates a top-performing stock and computes its continuation probability,
        factor score breakdown, execution playbook, and Devil's Advocate warning.
        Incorporate macro market drag (CMMI, Nifty trend) and Upper Circuit freeze detection.
        """
        sym = stock.get("symbol", "").upper().replace("NSE:", "").strip()
        cmp = float(stock.get("close", 0.0) or 0.0)

        # Resolve Sector for Macro RRG Alignment
        resolved_sector = stock.get("identified_nse_sector")
        if not resolved_sector:
            resolved_sector = SectorConstituentsStore.identify_sector_for_symbol(sym)
        if not resolved_sector and stock.get("industry"):
            resolved_sector = SectorConstituentsStore.identify_sector_by_tv_industry(stock.get("industry"))

        open_px = float(stock.get("open", cmp) or cmp)
        high = float(stock.get("high", cmp) or cmp)
        low = float(stock.get("low", cmp) or cmp)
        day_chg = float(stock.get("change", 0.0) or 0.0)
        perf_w = float(stock.get("Perf.W", 0.0) or 0.0)
        perf_1m = float(stock.get("Perf.1M", 0.0) or 0.0)
        perf_y = float(stock.get("Perf.Y", 0.0) or 0.0)
        rvol = float(stock.get("relative_volume_10d_calc", 1.0) or 1.0)
        rsi = float(stock.get("RSI", 55.0) or 55.0)
        vwap = float(stock.get("VWAP", cmp) or cmp)
        atr = float(stock.get("ATR", max(1.0, cmp * 0.02)) or (cmp * 0.02))
        h52 = float(stock.get("price_52_week_high", cmp) or cmp)
        float_shares = stock.get("float_shares_outstanding")
        beta = float(stock.get("beta_1_year", 1.0) or 1.0)
        mcap_cr = round(float(stock.get("market_cap_basic", 0.0) or 0.0) / 10000000.0, 2)

        # Approximate EMA20 if not provided directly
        ema20 = stock.get("EMA20")
        if not ema20:
            ema50 = float(stock.get("EMA50", cmp) or cmp)
            # EMA20 is typically between CMP and EMA50 in a breakout
            ema20 = round((cmp * 0.6) + (ema50 * 0.4), 2)
        else:
            ema20 = float(ema20)

        # 1. Microstructure metrics
        clv = cls.calculate_clv(high, low, cmp)
        upper_wick = cls.calculate_upper_wick_ratio(open_px, high, low, cmp)
        ier = cls.calculate_elasticity(cmp, ema20, atr)

        # Circuit Limit Detection (Upper Circuit Freeze Sentinel)
        # Typical NSE bands: 2%, 5%, 10%, 20%. Locked if closed at peak with frozen spread or exact band
        is_at_high = (high > 0 and (high - cmp) / high <= 0.0015)
        is_frozen_range = (cmp > 0 and (high - low) / cmp <= 0.004)
        is_circuit_gain = any(abs(day_chg - band) <= 0.35 for band in (2.0, 5.0, 10.0, 20.0))
        is_circuit_locked = is_at_high and (is_frozen_range or is_circuit_gain) and (day_chg >= 1.9)

        # 2. Authentic NSE Delivery metrics
        deliv_pct = 0.0
        deliv_qty = 0
        deliv_velocity = 0.0
        trajectory_label = "UNAVAILABLE"
        fsar = None

        is_t1_baseline = False
        if delivery_info and delivery_info.get("has_data"):
            deliv_pct = float(delivery_info.get("latest_delivery_pct", 0.0))
            deliv_qty = int(delivery_info.get("latest_delivery_qty", 0))
            deliv_velocity = float(delivery_info.get("delivery_velocity", 0.0))
            trajectory_label = delivery_info.get("trajectory_label", "STABLE_DELIVERY")
            is_t1_baseline = bool(
                delivery_info.get("is_provisional", False)
                or delivery_info.get("is_t1_baseline", False)
                or (delivery_info.get("is_eod_confirmed") is False)
            )
        elif delivery_info and "delivery_pct" in delivery_info:
            deliv_pct = float(delivery_info.get("delivery_pct", 0.0))
            deliv_qty = int(delivery_info.get("delivery_qty", 0))
            is_t1_baseline = bool(
                delivery_info.get("is_provisional", False)
                or delivery_info.get("is_t1_baseline", False)
                or (delivery_info.get("is_eod_confirmed") is False)
            )

        total_shares = stock.get("total_shares_outstanding") or stock.get("shares_outstanding")
        if not total_shares and cmp > 0 and stock.get("market_cap_basic"):
            total_shares = float(stock["market_cap_basic"]) / cmp
        promoter_pct = stock.get("promoter_holding_pct") or stock.get("promoter_holding")
        if promoter_pct is not None:
            promoter_pct = float(promoter_pct)

        fsar = cls.calculate_fsar(
            delivery_qty=deliv_qty,
            float_shares=float_shares,
            total_shares=total_shares,
            promoter_holding_pct=promoter_pct
        )

        # 3. Factor-based scoring (Base: 50.0 pts)
        score = 50.0
        factors = []

        # --- Microstructure Factor (CLV) ---
        if clv >= 0.90:
            clv_pts = round(8.0 + ((clv - 0.90) / 0.10) * 3.0, 1)
            score += clv_pts
            factors.append({"name": f"Closing Auction Aggression (CLV {clv*100:.0f}%)", "impact": f"+{clv_pts:.1f} pts", "status": "BULLISH"})
        elif clv >= 0.70:
            clv_pts = round(3.0 + ((clv - 0.70) / 0.20) * 5.0, 1)
            score += clv_pts
            factors.append({"name": f"Upper-Decile Close (CLV {clv*100:.0f}%)", "impact": f"+{clv_pts:.1f} pts", "status": "BULLISH"})
        elif clv < 0.40:
            clv_pts = round(6.0 + ((0.40 - clv) / 0.40) * 8.0, 1)
            score -= clv_pts
            factors.append({"name": f"Closing Liquidity Rejection (CLV {clv*100:.0f}%)", "impact": f"-{clv_pts:.1f} pts", "status": "BEARISH"})
        else:
            factors.append({"name": f"Mid-Range Close (CLV {clv*100:.0f}%)", "impact": "+0.0 pts", "status": "NEUTRAL"})

        # --- Upper-Wick Trap Sentinel ---
        if upper_wick < 0.05:
            score += 3.0
            factors.append({"name": "Marubozu / Minimal Upper Shadow (<5%)", "impact": "+3.0 pts", "status": "BULLISH"})
        elif upper_wick >= 0.35:
            score -= 16.0
            factors.append({"name": f"Upper Wick Trap Sentinel ({upper_wick*100:.0f}% shadow)", "impact": "-16.0 pts", "status": "TRAP_WARNING"})
        elif upper_wick >= 0.15:
            wick_pts = round(((upper_wick - 0.15) / 0.20) * 8.0, 1)
            score -= wick_pts
            factors.append({"name": f"Overhead Resistance Shadow ({upper_wick*100:.0f}%)", "impact": f"-{wick_pts:.1f} pts", "status": "CAUTION"})

        # --- Authentic Delivery Factor (Session Aware) ---
        t1_label = " (T-1 Baseline)" if is_t1_baseline else ""
        deliv_mult = 0.85 if is_t1_baseline else 1.0

        if deliv_pct >= 60.0:
            deliv_pts = round((10.0 + min(4.0, (deliv_pct - 60.0) * 0.15)) * deliv_mult, 1)
            score += deliv_pts
            factors.append({"name": f"Heavy Institutional Delivery ({deliv_pct:.1f}% >= 60%){t1_label}", "impact": f"+{deliv_pts:.1f} pts", "status": "INSTITUTIONAL"})
        elif deliv_pct >= 45.0:
            deliv_pts = round((6.0 + ((deliv_pct - 45.0) / 15.0) * 4.0) * deliv_mult, 1)
            score += deliv_pts
            factors.append({"name": f"Strong Institutional Delivery ({deliv_pct:.1f}%){t1_label}", "impact": f"+{deliv_pts:.1f} pts", "status": "BULLISH"})
        elif deliv_pct >= 35.0:
            deliv_pts = round((2.0 + ((deliv_pct - 35.0) / 10.0) * 4.0) * deliv_mult, 1)
            score += deliv_pts
            factors.append({"name": f"Above-Average Delivery ({deliv_pct:.1f}%){t1_label}", "impact": f"+{deliv_pts:.1f} pts", "status": "BULLISH"})
        elif deliv_pct >= 22.0:
            deliv_pts = round(((deliv_pct - 22.0) / 13.0) * 2.0 * deliv_mult, 1)
            score += deliv_pts
            factors.append({"name": f"Moderate Delivery Activity ({deliv_pct:.1f}%){t1_label}", "impact": f"+{deliv_pts:.1f} pts", "status": "NEUTRAL"})
        elif 0.0 < deliv_pct < 18.0:
            deliv_pts = round((8.0 + ((18.0 - deliv_pct) / 18.0) * 8.0) * deliv_mult, 1)
            score -= deliv_pts
            factors.append({"name": f"Retail Intraday Churn Hazard ({deliv_pct:.1f}% < 18%){t1_label}", "impact": f"-{deliv_pts:.1f} pts", "status": "RETAIL_CHURN"})
        elif deliv_pct == 0.0:
            score -= 5.0
            factors.append({"name": "Delivery Data Pending EOD Report", "impact": "-5.0 pts", "status": "PENDING"})

        # --- 3-Day Delivery Velocity ---
        if trajectory_label == "STAIRCASE_ACCUMULATION":
            score += 5.0
            factors.append({"name": f"3-Day Delivery Staircase (+{deliv_velocity:.1f}%/day)", "impact": "+5.0 pts", "status": "ACCUMULATION"})
        elif trajectory_label == "DISTRIBUTION_CHURN":
            score -= 8.0
            factors.append({"name": f"Delivery Collapsing ({deliv_velocity:.1f}%/day)", "impact": "-8.0 pts", "status": "DISTRIBUTION"})

        # --- Float Absorption (FSAR) ---
        if fsar is not None:
            if fsar >= 1.0 and deliv_pct >= 35.0:
                fsar_pts = round(min(5.0, 2.5 + (fsar * 1.5)), 1)
                score += fsar_pts
                factors.append({"name": f"Float Lockup Squeeze (FSAR {fsar:.2f}% with {deliv_pct:.1f}% delivery)", "impact": f"+{fsar_pts:.1f} pts", "status": "SUPPLY_SQUEEZE"})
            elif fsar >= 0.5 and deliv_pct >= 30.0:
                score += 2.5
                factors.append({"name": f"Substantial Float Absorption (FSAR {fsar:.2f}%)", "impact": "+2.5 pts", "status": "BULLISH"})
            elif fsar >= 1.0 and deliv_pct < 20.0 and deliv_pct > 0.0:
                score -= 8.0
                factors.append({"name": f"False Float Lockup Trap (High volume but only {deliv_pct:.1f}% delivery)", "impact": "-8.0 pts", "status": "TRAP_WARNING"})

        # --- Relative Volume Surge ---
        if rvol >= 3.0:
            rvol_pts = round(4.0 + min(4.0, (rvol - 3.0) * 0.8), 1)
            score += rvol_pts
            factors.append({"name": f"Volume Velocity Shock ({rvol:.1f}x)", "impact": f"+{rvol_pts:.1f} pts", "status": "BULLISH"})
        elif rvol >= 1.5:
            rvol_pts = round(((rvol - 1.5) / 1.5) * 4.0, 1)
            score += rvol_pts
            factors.append({"name": f"Above-Average Volume ({rvol:.1f}x)", "impact": f"+{rvol_pts:.1f} pts", "status": "BULLISH"})
        elif rvol < 1.0:
            rvol_pts = round((1.0 - rvol) * 6.0, 1)
            score -= rvol_pts
            factors.append({"name": f"Below-Average Turnover ({rvol:.1f}x)", "impact": f"-{rvol_pts:.1f} pts", "status": "BEARISH"})

        # --- Institutional Elasticity Ratio (Overextension Penalty) ---
        if ier > 4.5:
            score -= 14.0
            factors.append({"name": f"Rubber-Band Overextension (IER {ier:.1f} > 4.5 ATR)", "impact": "-14.0 pts", "status": "EXHAUSTION"})
        elif ier > 3.0:
            ier_pts = round((ier - 3.0) * 5.0, 1)
            score -= ier_pts
            factors.append({"name": f"Extended from 20-Day Mean (IER {ier:.1f} ATR)", "impact": f"-{ier_pts:.1f} pts", "status": "CAUTION"})
        elif 0.8 <= ier <= 2.2:
            score += 2.0
            factors.append({"name": f"Healthy Base Coiling (IER {ier:.1f} ATR)", "impact": "+2.0 pts", "status": "BASE"})

        # --- Trendlyne DVM Validation ---
        durability = dvm_scores.get("durability", 60.0)
        valuation = dvm_scores.get("valuation", 50.0)
        momentum = dvm_scores.get("momentum", 60.0)

        dvm_pts = round(((durability - 50.0) / 50.0) * 3.0 + ((momentum - 50.0) / 50.0) * 4.0, 1)
        score += dvm_pts
        if dvm_pts > 0:
            factors.append({"name": f"DVM Quality Sponsorship (D:{durability:.0f} M:{momentum:.0f})", "impact": f"+{dvm_pts:.1f} pts", "status": "QUALITY"})
        elif dvm_pts < -3.0:
            factors.append({"name": f"DVM Fundamental Headwinds (D:{durability:.0f} M:{momentum:.0f})", "impact": f"{dvm_pts:.1f} pts", "status": "SOLVENCY_RISK"})

        # --- Horizon-Specific Modulation ---
        if horizon == "WEEKLY":
            if rsi >= 85.0:
                score -= 8.0
                factors.append({"name": f"Weekly Overbought Fatigue (RSI {rsi:.1f} >= 85)", "impact": "-8.0 pts", "status": "OVERBOUGHT"})
            if perf_w >= 35.0 and deliv_pct < 30.0 and deliv_pct > 0:
                score -= 10.0
                factors.append({"name": "Low Delivery on Monster Weekly Surge", "impact": "-10.0 pts", "status": "VULNERABLE"})
        elif horizon == "YEARLY":
            dist_52w = ((h52 - cmp) / h52) * 100.0 if h52 > 0 else 10.0
            if dist_52w <= 3.0:
                score += 6.0
                factors.append({"name": "At/Near 52-Week High (<3% away)", "impact": "+6.0 pts", "status": "BASE_BREAKOUT"})
            elif dist_52w > 20.0:
                score -= 6.0
                factors.append({"name": f"Lagging 52-Week Peak ({dist_52w:.1f}% away)", "impact": "-6.0 pts", "status": "OVERHEAD_SUPPLY"})

        # --- Sector RRG Momentum Alignment Factor ---
        if macro_context and resolved_sector:
            leading_sectors = [s.upper() for s in macro_context.get("leading_sectors", [])]
            improving_sectors = [s.upper() for s in macro_context.get("improving_sectors", [])]
            lagging_sectors = [s.upper() for s in macro_context.get("lagging_sectors", [])]

            res_sec_upper = resolved_sector.upper()
            if res_sec_upper in leading_sectors:
                score += 3.0
                factors.append({
                    "name": f"Sector RRG Tailwind (Leading: {resolved_sector})",
                    "impact": "+3.0 pts",
                    "status": "SECTOR_TAILWIND"
                })
            elif res_sec_upper in improving_sectors:
                score += 1.5
                factors.append({
                    "name": f"Sector RRG Accumulation (Improving: {resolved_sector})",
                    "impact": "+1.5 pts",
                    "status": "SECTOR_ACCUMULATION"
                })
            elif res_sec_upper in lagging_sectors:
                score -= 3.0
                factors.append({
                    "name": f"Sector RRG Headwind (Lagging: {resolved_sector})",
                    "impact": "-3.0 pts",
                    "status": "SECTOR_HEADWIND"
                })

        # 4. Continuous Logistic Sigmoid Mapping to Dynamic Calibrated Probability (10% to 92%)
        # Score naturally centers at 50, standard deviation ~20 points.
        z = (score - 50.0) / 20.0
        prob = 1.0 / (1.0 + math.exp(-z))
        prob_pct = round(prob * 100.0, 1)
        prob_pct = max(10.0, min(92.0, prob_pct))

        # --- Macro Sentiment & Beta Drag Multiplier ---
        macro_multiplier = 1.0
        macro_drag_pct = 0.0
        if macro_context:
            cmmi = macro_context.get("cmmi_score")
            nifty_chg = float(macro_context.get("nifty_change_pct", 0.0) or 0.0)
            if cmmi is None:
                factors.append({
                    "name": "Macro Telemetry Offline (Neutral Baseline Applied)",
                    "impact": "x1.00",
                    "status": "OFFLINE"
                })
            else:
                cmmi = float(cmmi)
                # CMMI scale: 50 is neutral (range: -0.25 to +0.25)
                cmmi_delta = (cmmi - 50.0) / 100.0
                # Nifty scale: 0% is neutral (-1.5% is -0.15)
                nifty_delta = nifty_chg / 10.0
                raw_macro_factor = (cmmi_delta * 0.5) + (nifty_delta * 0.5)
                # High-beta stocks take bigger hits during macro risk-off
                beta_clamped = max(0.4, min(2.0, beta))
                macro_drag = raw_macro_factor * beta_clamped
                macro_multiplier = round(max(0.80, min(1.10, 1.0 + macro_drag)), 3)

                prob_pct = round(prob_pct * macro_multiplier, 1)
                prob_pct = max(10.0, min(92.0, prob_pct))

                macro_drag_pct = round((macro_multiplier - 1.0) * 100.0, 1)
                if macro_multiplier < 0.96:
                    factors.append({
                        "name": f"Macro Risk-Off Drag ({macro_drag_pct:+.1f}% via CMMI {cmmi:.0f} / Beta {beta:.2f})",
                        "impact": f"x{macro_multiplier:.2f}",
                        "status": "HEADWIND"
                    })
                elif macro_multiplier > 1.03:
                    factors.append({
                        "name": f"Macro Bullish Tailwind ({macro_drag_pct:+.1f}% via CMMI {cmmi:.0f})",
                        "impact": f"x{macro_multiplier:.2f}",
                        "status": "TAILWIND"
                    })

        # 5. Institutional Invariant Clamping (Truth in Advertising Firewall)
        # Rule A: Extreme retail churn (<18% delivery) cannot claim high probability
        if 0.0 < deliv_pct < 18.0:
            prob_pct = min(42.0, prob_pct)
            verdict = "RETAIL_TRAP_FADE_RISK"
            verdict_badge = f"⚠️ Retail Churn Trap (Deliv {deliv_pct:.1f}% < 18%)"
            verdict_color = "#ef4444"
        # Rule B: Massive overhead upper wick rejection (>35%) indicates supply overhead
        elif upper_wick >= 0.35:
            prob_pct = min(42.0, prob_pct)
            verdict = "RETAIL_TRAP_FADE_RISK"
            verdict_badge = f"⚠️ Supply Rejection Trap (Wick {upper_wick*100:.0f}%)"
            verdict_color = "#ef4444"
        # Rule C: Upper Circuit Lockout (Illiquid unfillable buyer queues)
        elif is_circuit_locked:
            verdict = "CIRCUIT_LOCKED_ILLIQUID"
            verdict_badge = f"🔒 Upper Circuit Locked (+{day_chg:.1f}% Illiquid)"
            verdict_color = "#eab308"
        # Rule D: Missing/unreported delivery bhavcopy cannot claim aggressive gap-and-go
        elif deliv_pct == 0.0:
            prob_pct = min(58.0, prob_pct)
            verdict = "PULLBACK_ACCUMULATION"
            verdict_badge = "⏳ Unconfirmed Delivery (Wait for EOD)"
            verdict_color = "#f59e0b"
        # Rule E: Severely stretched from 20-day mean (>4.5 ATR) cannot gap-and-go
        elif ier > 4.5:
            prob_pct = min(58.0, prob_pct)
            verdict = "PULLBACK_ACCUMULATION"
            verdict_badge = "📈 Overextended Mean (Buy Dip Only)"
            verdict_color = "#3b82f6"
        else:
            if prob_pct >= 75.0:
                verdict = "GAP_AND_GO_CANDIDATE"
                verdict_badge = "🚀 High Follow-Through (Gap & Go)"
                verdict_color = "#10b981"  # Emerald
            elif prob_pct >= 60.0:
                verdict = "PULLBACK_ACCUMULATION"
                verdict_badge = "📈 Continuation on Dips"
                verdict_color = "#3b82f6"  # Blue
            elif prob_pct >= 45.0:
                verdict = "RANGE_BOUND_DIGESTION"
                verdict_badge = "⏳ Digestion / Consolidation"
                verdict_color = "#f59e0b"  # Amber
            else:
                verdict = "RETAIL_TRAP_FADE_RISK"
                verdict_badge = "⚠️ Retail Fade / Bull Trap Risk"
                verdict_color = "#ef4444"  # Red

        # 6. Generate 9:15 AM ORB-15 Playbook
        playbook = cls._build_opening_playbook(cmp, high, low, vwap, atr, verdict, deliv_pct, clv, day_chg)

        # 7. Generate Actionable 2R/3R Execution Brackets
        entry, sl, t1, t2, risk, reward_2r = cls._build_execution_brackets(cmp, high, low, vwap, atr, verdict)

        # 8. Devil's Advocate & Tail Risk Invalidation
        devils_advocate = cls._build_devils_advocate(sym, cmp, vwap, atr, beta, deliv_pct, upper_wick, verdict)

        return {
            "symbol": sym,
            "horizon": horizon,
            "cmp": cmp,
            "day_change_pct": round(day_chg, 2),
            "perf_1w_pct": round(perf_w, 2),
            "perf_1m_pct": round(perf_1m, 2),
            "perf_1y_pct": round(perf_y, 2),
            "high": high,
            "low": low,
            "open": open_px,
            "vwap": vwap,
            "atr": round(atr, 2),
            "rvol": round(rvol, 2),
            "rsi": round(rsi, 1),
            "beta": round(beta, 2),
            "mcap_cr": mcap_cr,
            # Microstructure & Circuit Limits
            "clv": clv,
            "clv_pct": round(clv * 100.0, 1),
            "upper_wick_ratio": upper_wick,
            "ier_elasticity": ier,
            "is_circuit_locked": is_circuit_locked,
            "identified_nse_sector": resolved_sector,
            # Macro Telemetry
            "macro_multiplier": macro_multiplier,
            "macro_drag_pct": macro_drag_pct,
            # Authentic Delivery & Provenance
            "delivery_pct": round(deliv_pct, 2),
            "delivery_qty": deliv_qty,
            "delivery_velocity": deliv_velocity,
            "trajectory_label": trajectory_label,
            "fsar_pct": fsar,
            "bhavcopy_date": delivery_info.get("latest_bhavcopy_date") if delivery_info else None,
            "provenance_mode": delivery_info.get("provenance_mode", "UNAVAILABLE") if delivery_info else "UNAVAILABLE",
            "provenance_label": delivery_info.get("provenance_label", "Delivery Data Pending") if delivery_info else "Delivery Data Pending",
            "is_eod_confirmed": delivery_info.get("is_eod_confirmed", False) if delivery_info else False,
            "is_t1_baseline": is_t1_baseline,
            # DVM Scores
            "dvm_durability": durability,
            "dvm_valuation": valuation,
            "dvm_momentum": momentum,
            "dvm_composite": dvm_scores.get("composite", 60.0),
            # Follow-through probability & verdict
            "raw_score": round(score, 1),
            "continuation_probability_pct": prob_pct,
            "verdict": verdict,
            "verdict_badge": verdict_badge,
            "verdict_color": verdict_color,
            "factor_breakdown": factors,
            # Institutional Execution Rules
            "orb15_playbook": playbook,
            "trade_brackets": {
                "recommended_entry": entry,
                "stop_loss": sl,
                "target_1_2r": t1,
                "target_2_3r": t2,
                "risk_per_share": risk,
                "risk_reward": "1:2.0 / 1:3.0"
            },
            "devils_advocate_invalidation": devils_advocate,
            "tradingview_chart_url": f"https://in.tradingview.com/chart/?symbol=NSE:{sym}"
        }

    @classmethod
    def _build_opening_playbook(
        cls, cmp: float, high: float, low: float, vwap: float, atr: float, verdict: str, deliv_pct: float, clv: float, day_chg: float = 0.0
    ) -> Dict[str, str]:
        """Builds explicit 9:15–9:30 AM Opening Range instructions."""
        if verdict == "CIRCUIT_LOCKED_ILLIQUID":
            return {
                "gap_up_rule": f"⚠️ UPPER CIRCUIT FREEZE (+{day_chg:.1f}%): Closed at exchange upper limit (Rs. {cmp:.1f}). Buyer bids are frozen with zero sellers. Do NOT place market orders at 9:15 AM (unfillable). If circuit opens unexpectedly, high risk of trapped long liquidation.",
                "flat_open_rule": "Observe pre-open session (9:00-9:07 AM). If unfulfilled buy orders exceed 50k shares, momentum is genuine but orderbook is illiquid. Enter only after an active two-sided order book develops.",
                "pullback_rule": f"If circuit breaks open, key support is VWAP (Rs. {vwap:.1f}). A breakdown below Day-1 High (Rs. {high:.1f}) triggers immediate circuit-reversal risk."
            }
        elif verdict == "GAP_AND_GO_CANDIDATE":
            return {
                "gap_up_rule": f"If opening gap > 1.0%, wait for the 15-minute high (9:15-9:30 AM). Buy the 9:30 breakout above Day-1 High (Rs. {high:.1f}) with above-average opening volume.",
                "flat_open_rule": f"If flat (<0.6% gap), enter directly above Rs. {cmp:.1f} with tight stop at yesterday's VWAP (Rs. {vwap:.1f}).",
                "pullback_rule": f"If morning dip occurs, accumulate near VWAP (Rs. {vwap:.1f}). Invalidate if price breaks Rs. {low:.1f}."
            }
        elif verdict == "PULLBACK_ACCUMULATION":
            return {
                "gap_up_rule": f"Do NOT chase opening gap-up. Extended by elasticity. Wait for 10:00 AM pullback toward VWAP (Rs. {vwap:.1f}) or Day-1 High (Rs. {high:.1f}).",
                "flat_open_rule": f"Enter in 2 tranches: 50% at open, 50% on test of Rs. {vwap:.1f}.",
                "pullback_rule": f"Prime accumulation zone is Rs. {vwap:.1f} - Rs. {cmp * 0.985:.1f}."
            }
        elif verdict == "RETAIL_TRAP_FADE_RISK":
            return {
                "gap_up_rule": f"HIGH RISK OF GAP-FADE. Delivery was only {deliv_pct:.1f}%. If stock gaps up, expect immediate profit-taking from retail margin traders. Avoid buying open.",
                "flat_open_rule": "Do not enter. Observe order book depth. Only consider if delivery volume spikes > 2x yesterday's rate.",
                "pullback_rule": f"Wait for test and stabilization at Rs. {low:.1f}. If Rs. {low:.1f} breaks, sharp long liquidation likely."
            }
        else:
            return {
                "gap_up_rule": "Wait for 30-minute base formation before committing capital.",
                "flat_open_rule": f"Consolidation range is Rs. {low:.1f} to Rs. {high:.1f}.",
                "pullback_rule": f"Buy only near lower range boundary Rs. {low:.1f} with small sizing."
            }

    @classmethod
    def _build_execution_brackets(
        cls, cmp: float, high: float, low: float, vwap: float, atr: float, verdict: str
    ) -> Tuple[float, float, float, float, float, float]:
        """Calculates exact entry, stop loss, 2R target, and 3R target."""
        if verdict == "CIRCUIT_LOCKED_ILLIQUID":
            entry = round(cmp, 1)
            sl = round(min(vwap * 0.99, cmp - (1.0 * atr)), 1)
        elif verdict == "GAP_AND_GO_CANDIDATE":
            entry = round(max(cmp, high * 1.002), 1)
            sl = round(min(vwap * 0.995, cmp - (1.0 * atr)), 1)
        elif verdict == "PULLBACK_ACCUMULATION":
            entry = round(vwap * 1.002, 1)
            sl = round(low * 0.995, 1)
        else:
            entry = round(high * 1.005, 1)
            sl = round(cmp - (1.2 * atr), 1)

        if sl >= entry:
            sl = round(entry - max(entry * 0.015, atr), 1)
        risk = round(max(entry * 0.01, entry - sl), 1)
        t1 = round(entry + (2.0 * risk), 1)
        t2 = round(entry + (3.0 * risk), 1)

        return entry, sl, t1, t2, risk, round(2.0 * risk, 1)

    @classmethod
    def _build_devils_advocate(
        cls, sym: str, cmp: float, vwap: float, atr: float, beta: float, deliv_pct: float, upper_wick: float, verdict: str
    ) -> str:
        """Generates explicit tail-risk thesis invalidation conditions."""
        inval_price = round(min(vwap * 0.99, cmp - (1.2 * atr)), 1)

        warnings = []
        if deliv_pct < 20.0 and deliv_pct > 0:
            warnings.append(f"Extremely low delivery ({deliv_pct:.1f}%) signals >80% intraday churn. A morning market dip could trigger massive forced stop-loss cascades.")
        if upper_wick >= 0.30:
            warnings.append(f"Upper wick of {upper_wick*100:.0f}% proves overhead selling into the close. Trapped supply exists at yesterday's peak.")
        if beta > 1.4:
            warnings.append(f"High beta ({beta:.2f}) makes this stock vulnerable to broad market gap-downs.")

        inval_stmt = f"INVALIDATION TRIGGER: Exit or abort if stock opens or trades below Rs. {inval_price:.1f}"
        if beta > 1.2:
            inval_stmt += " or if Nifty breaches opening low with negative market breadth."
        else:
            inval_stmt += " regardless of market indices."

        if warnings:
            return f"{inval_stmt} | RISKS: {' '.join(warnings)}"
        return f"{inval_stmt} | Setup remains valid as long as physical delivery support holds above Rs. {inval_price:.1f}."
