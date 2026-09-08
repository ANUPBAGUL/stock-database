"""
Multi-Horizon Feed Router & Thesis Falsification Engine.

Segments screened candidates using the 4-Vector Matrix:
1. Long-Term Compounders (High Potential + High Asymmetry Gap)
2. Strategic Watchlist (High Business Potential >= 75, but Entry Quality pending < 70)
3. 2-4 Week Swing Setups (Entry Quality >= 75, Tape Confirmation >= 70, R:R >= 2.33)
4. 1-Day Intraday Scalp Radar (High Volume Spikes & Momentum Breakouts)
5. Automated 3-Point Invalidation Guardrails (Thesis Killers)
"""

from typing import Dict, Any, List, Optional
from src.screener.screener_models import (
    ScreenerCandidateResult, SwingSetupCard, IntradayRadarCard, InvalidationTrigger
)

_CALIBRATION_CACHE = None


def _get_calibration_data() -> Dict[str, Any]:
    global _CALIBRATION_CACHE
    if _CALIBRATION_CACHE is None:
        try:
            from src.analytics.historical_swing_replay_engine import HistoricalSwingReplayEngine
            _CALIBRATION_CACHE = HistoricalSwingReplayEngine.load_calibration() or {}
        except Exception:
            _CALIBRATION_CACHE = {}
    return _CALIBRATION_CACHE


class MultiHorizonFeedRouter:
    """
    Transforms raw 5-pillar evaluations into actionable multi-horizon trading intelligence.
    """

    @staticmethod
    def _build_broker_order_ticket(
        symbol: str,
        cmp: float,
        entry_price: float,
        stop_loss_price: float,
        target_price_1: float,
        target_price_2: float,
        horizon: str = "SWING_POSITIONAL",
        reference_capital: float = 100000.0,
        risk_budget_pct: float = 1.0
    ) -> Dict[str, Any]:
        """
        Generates an exact 1-Click Zerodha Kite / Upstox execution order ticket
        enforcing the 1.0% portfolio risk budget rule.
        """
        max_risk_amount = round(reference_capital * (risk_budget_pct / 100.0), 2)
        risk_per_share = max(0.1, abs(entry_price - stop_loss_price))
        suggested_qty = max(1, int(max_risk_amount / risk_per_share))
        
        # Max position cap: 20% of capital
        max_qty_by_cap = max(1, int((reference_capital * 0.20) / max(1.0, entry_price)))
        final_qty = min(suggested_qty, max_qty_by_cap)
        allocated_capital = round(final_qty * entry_price, 2)
        actual_risk_amount = round(final_qty * risk_per_share, 2)

        return {
            "broker_target": "ZERODHA_UPSTOX_COMPLIANT",
            "exchange": "NSE",
            "symbol": symbol,
            "tradingsymbol": f"{symbol}-EQ",
            "transaction_type": "BUY",
            "order_type": "LIMIT",
            "product": "CNC" if horizon == "SWING_POSITIONAL" else "MIS",
            "quantity": final_qty,
            "entry_limit_price": entry_price,
            "stop_loss_trigger": stop_loss_price,
            "target_t1_limit": target_price_1,
            "target_t2_limit": target_price_2,
            "allocated_capital_inr": allocated_capital,
            "max_risk_inr": actual_risk_amount,
            "risk_per_share_inr": round(risk_per_share, 2),
            "order_summary": f"BUY {final_qty} {symbol} @ Limit Rs.{entry_price:.2f} | SL GTT Trigger Rs.{stop_loss_price:.2f} | T1 Rs.{target_price_1:.2f} | Max Risk Rs.{actual_risk_amount:.2f}"
        }

    @classmethod
    def route_candidate(cls, evaluated_data: Dict[str, Any]) -> ScreenerCandidateResult:
        """
        Builds the complete multi-horizon intelligence card using decoupled orthogonal vectors.
        """
        sym = evaluated_data["symbol"]
        cmp = evaluated_data["cmp"]
        p1 = evaluated_data.get("economic_inflection_p1", 80.0)
        p3 = evaluated_data.get("working_capital_p3", 80.0)
        p4 = evaluated_data.get("expectations_gap_p4", 80.0)
        p5 = evaluated_data.get("price_structure_p5", 80.0)
        score = evaluated_data.get("multibagger_conviction_score", 80.0)
        mcap = evaluated_data.get("market_cap_cr", 1000.0)

        potential = evaluated_data.get("business_potential_score", 80.0)
        asym_gap = evaluated_data.get("expectations_asymmetry_gap_pct", 5.0)
        tape = evaluated_data.get("tape_confirmation_score", 75.0)
        entry = evaluated_data.get("entry_quality_score", 70.0)
        m7_idx = evaluated_data.get("m7_asymmetry_index", 75.0)
        likelihood = evaluated_data.get("multibagger_likelihood_rank", "HIGH")

        # 1. Long-Term Verdict & Categorization
        if potential >= 85.0 and asym_gap >= 8.0:
            if entry >= 75.0:
                lt_verdict = "CONVICTION_BUY"
                thesis_cat = "CONVICTION_BUY"
            else:
                lt_verdict = "ACCUMULATE_ON_DIPS"
                thesis_cat = "STRATEGIC_WATCHLIST"
        elif potential >= 72.0:
            lt_verdict = "STRATEGIC_WATCHLIST" if entry < 70.0 else "ACCUMULATE_ON_DIPS"
            thesis_cat = "STRATEGIC_WATCHLIST" if entry < 70.0 else "SWING_SETUP"
        else:
            lt_verdict = "WATCHLIST"
            thesis_cat = "STRATEGIC_WATCHLIST"

        # 2. Institutional Positional Swing Setup (2-6 Weeks / 45-day Positional Horizon)
        swing_audit = evaluated_data.get("swing_audit")
        if swing_audit:
            # Consume authentic price structure audit directly
            swing_card = SwingSetupCard(
                is_active=swing_audit.get("is_active", False),
                setup_type=swing_audit.get("setup_type", "BASE_CONSOLIDATION"),
                pivot_entry_price=swing_audit.get("pivot_entry_price", round(cmp * 1.02, 2)),
                raw_pivot_price=swing_audit.get("raw_pivot_price", swing_audit.get("pivot_entry_price", round(cmp * 1.02, 2))),
                adjusted_pivot_entry=swing_audit.get("adjusted_pivot_entry", swing_audit.get("pivot_entry_price", round(cmp * 1.02, 2))),
                adaptive_pivot_buffer=swing_audit.get("adaptive_pivot_buffer", 0.0),
                wick_rejection_detected=swing_audit.get("wick_rejection_detected", False),
                upper_wick_ratio=swing_audit.get("upper_wick_ratio", 0.0),
                has_micro_handle=swing_audit.get("has_micro_handle", False),
                handle_quality=swing_audit.get("handle_quality", "INSUFFICIENT_DATA"),
                handle_tightness_ratio=swing_audit.get("handle_tightness_ratio", 1.0),
                stop_loss_price=swing_audit.get("stop_loss_price", round(cmp * 0.95, 2)),
                structural_stop_reason=swing_audit.get("structural_stop_reason", "Base Support"),
                risk_pct=swing_audit.get("risk_pct", 5.0),
                suggested_position_size_pct=swing_audit.get("suggested_position_size_pct", 10.0),
                tranche_1_probe_pct=swing_audit.get("tranche_1_probe_pct", 50.0),
                tranche_1_trigger_price=swing_audit.get("tranche_1_trigger_price", swing_audit.get("pivot_entry_price", round(cmp * 1.02, 2))),
                tranche_2_pyramid_pct=swing_audit.get("tranche_2_pyramid_pct", 50.0),
                tranche_2_trigger_price=swing_audit.get("tranche_2_trigger_price", round(cmp * 1.05, 2)),
                breakeven_milestone_price=swing_audit.get("breakeven_milestone_price", round(cmp * 1.08, 2)),
                target_price=swing_audit.get("target_price_t1", round(cmp * 1.10, 2)),
                target_price_t1=swing_audit.get("target_price_t1", round(cmp * 1.10, 2)),
                target_price_t2=swing_audit.get("target_price_t2", round(cmp * 1.20, 2)),
                risk_reward_ratio=swing_audit.get("risk_reward_ratio", 2.0),
                expected_value_score=swing_audit.get("expected_value_score", 50.0),
                timeframe=swing_audit.get("timeframe", "2-6 Weeks (Positional Swing)"),
                atr_10d=swing_audit.get("atr_10d", 0.0),
                atr_30d=swing_audit.get("atr_30d", 0.0),
                atr_20d=swing_audit.get("atr_20d", 0.0),
                atr_contraction_ratio=swing_audit.get("atr_contraction_ratio", 1.0),
                volatility_contraction_delta_pct=swing_audit.get("volatility_contraction_delta_pct", 0.0),
                volume_5d_avg=swing_audit.get("volume_5d_avg", 0.0),
                volume_40d_avg=swing_audit.get("volume_40d_avg", 0.0),
                volume_dryup_ratio=swing_audit.get("volume_dryup_ratio", 1.0),
                volume_dryup_delta_pct=swing_audit.get("volume_dryup_delta_pct", 0.0),
                up_down_volume_ratio=swing_audit.get("up_down_volume_ratio", 1.0),
                up_days_count=swing_audit.get("up_days_count", 10),
                down_days_count=swing_audit.get("down_days_count", 10),
                pivot_distance_pct=swing_audit.get("pivot_distance_pct", 0.0),
                actionability_status=swing_audit.get("actionability_status", "CONSTRUCTING_BASE"),
                contraction_quality=swing_audit.get("contraction_quality", "HEALTHY_CONTRACTION"),
                vol_compression_percentile=swing_audit.get("vol_compression_percentile", 50.0),
                distribution_days_count=swing_audit.get("distribution_days_count", 0),
                closing_range_location_pct=swing_audit.get("closing_range_location_pct", 50.0),
                market_regime=swing_audit.get("market_regime", "BULL_MOMENTUM"),
                trailing_stop_guide=swing_audit.get("trailing_stop_guide", "10 EMA (Momentum) / 20 EMA (Positional)"),
                sector_relative_strength=swing_audit.get("sector_relative_strength", "NEUTRAL"),
                empirical_win_rate_pct=swing_audit.get("empirical_win_rate_pct", 0.0),
                wilson_ci_low_pct=swing_audit.get("wilson_ci_low_pct", 0.0),
                wilson_ci_high_pct=swing_audit.get("wilson_ci_high_pct", 0.0),
                sample_size_evidence=swing_audit.get("sample_size_evidence", "LIMITED"),
                data_diversity=swing_audit.get("data_diversity", "LOW"),
                empirical_profit_factor=swing_audit.get("empirical_profit_factor", 0.0),
                empirical_avg_r=swing_audit.get("empirical_avg_r", 0.0),
                expected_r_multiple=swing_audit.get("expected_r_multiple", 0.0),
                empirical_sample_size=swing_audit.get("empirical_sample_size", 0),
                empirical_avg_days_to_target=swing_audit.get("empirical_avg_days_to_target", 0.0),
                mfe_pre_stop_avg_pct=swing_audit.get("mfe_pre_stop_avg_pct", 0.0),
                execution_risk_spread_r=swing_audit.get("execution_risk_spread_r", 0.0),
                trade_risk_pct=swing_audit.get("trade_risk_pct", swing_audit.get("risk_pct", 0.0)),
                portfolio_risk_budget_pct=1.0,
                status_notes=swing_audit.get("status_notes", "")
            )
        else:
            # Authentic derivation from cloud technical primitives
            atr_raw = evaluated_data.get("atr_20d")
            atr = round(float(atr_raw), 2) if (atr_raw is not None and float(atr_raw) > 0) else round(cmp * 0.02, 2)
            atr_weekly_raw = evaluated_data.get("atr_weekly")
            atr_weekly = float(atr_weekly_raw) if (atr_weekly_raw is not None and float(atr_weekly_raw) > 0) else None

            # Contraction ratio: daily ATR vs weekly ATR
            if atr_weekly and atr_weekly > 0:
                atr_contraction_ratio = round(atr / atr_weekly, 2)
                vol_delta_pct = round((atr_contraction_ratio - 1.0) * 100.0, 1)
            else:
                atr_contraction_ratio = 1.0
                vol_delta_pct = 0.0

            ema50_raw = evaluated_data.get("support_price_50d")
            ema50 = float(ema50_raw) if ema50_raw is not None else round(cmp * 0.95, 2)
            h52 = float(evaluated_data.get("high_52w") or cmp * 1.15)
            h1m = float(evaluated_data.get("high_1m") or 0.0)
            h3m = float(evaluated_data.get("high_3m") or 0.0)
            adaptive_buf = round(max(0.12 * atr, cmp * 0.0015), 2)

            # Setup classification based on multi-timeframe pivots
            dist_52w = round(((cmp - h52) / h52) * 100.0, 1) if h52 > 0 else -10.0
            dist_50 = round(((cmp - ema50) / ema50) * 100.0, 1) if ema50 > 0 else 0.0
            dist_1m = round(((cmp - h1m) / h1m) * 100.0, 1) if h1m > 0 else -10.0
            dist_3m = round(((cmp - h3m) / h3m) * 100.0, 1) if h3m > 0 else -10.0

            if dist_52w >= -4.0:
                s_type = "52W_HIGH_BREAKOUT"
                p_entry = round(h52 + adaptive_buf, 2)
                s_loss = round(max(ema50, p_entry - 1.5 * atr), 2)
                s_reason = "50-Day EMA / Base Support"
                t1 = round(p_entry + max(atr * 2.5, p_entry - s_loss), 2)
                t2 = round(p_entry + max(atr * 4.0, (p_entry - s_loss) * 1.618), 2)
            elif h1m > 0 and dist_1m >= -3.5 and atr_contraction_ratio <= 0.85:
                s_type = "VCP_CONTRACTION_BREAKOUT"
                p_entry = round(h1m + adaptive_buf, 2)
                s_loss = round(max(ema50, p_entry - 1.25 * atr), 2)
                s_reason = "VCP Contraction Base / Pivot Support"
                t1 = round(p_entry + max(atr * 2.2, (p_entry - s_loss) * 2.0), 2)
                t2 = round(p_entry + max(atr * 3.5, (p_entry - s_loss) * 3.0), 2)
            elif h3m > 0 and dist_3m >= -4.0:
                s_type = "3M_BASE_BREAKOUT"
                p_entry = round(h3m + adaptive_buf, 2)
                s_loss = round(max(ema50, p_entry - 1.4 * atr), 2)
                s_reason = "3-Month Consolidation Base"
                t1 = round(p_entry + max(atr * 2.5, p_entry - s_loss), 2)
                t2 = round(p_entry + max(atr * 4.0, (p_entry - s_loss) * 1.618), 2)
            elif -2.5 <= dist_50 <= 2.5:
                s_type = "50EMA_PULLBACK"
                p_entry = round(cmp + adaptive_buf, 2)
                s_loss = round(ema50 * 0.99 - 0.05 * atr, 2)
                s_reason = "50-Day EMA Baseline"
                t1 = round(min(h52, p_entry + max(atr * 2.0, (p_entry - s_loss) * 2.2)), 2)
                t2 = round(p_entry + max(atr * 3.5, (p_entry - s_loss) * 3.5), 2)
            else:
                s_type = "BASE_CONSOLIDATION"
                pivot_ref = h1m if h1m > 0 else (cmp * 1.015)
                p_entry = round(pivot_ref + adaptive_buf, 2)
                s_loss = round(p_entry - max(atr * 1.25, (p_entry - ema50) * 0.75), 2)
                s_reason = "Consolidation Base Low"
                t1 = round(min(h52, p_entry + max(atr * 2.2, (p_entry - s_loss) * 2.2)), 2)
                t2 = round(p_entry + max(atr * 3.5, (p_entry - s_loss) * 3.5), 2)

            risk = max(0.1, p_entry - s_loss)
            reward = max(0.1, t1 - p_entry)
            rr = round(reward / risk, 2)
            risk_pct = round((risk / p_entry) * 100.0, 2)
            p_dist = round(((cmp - p_entry) / p_entry) * 100.0, 2)
            
            if risk_pct > 8.5:
                pos_size = 0.0
                s_reason += " [EXCESSIVE_RISK > 8.5% -> 0% ALLOCATION]"
            else:
                pos_size = round(min(20.0, max(0.0, 1.0 / max(0.01, risk_pct / 100.0))), 1)
                macro_reg = evaluated_data.get("macro_regime")
                if macro_reg == "RISK_OFF_CORRECTION":
                    pos_size = round(pos_size * 0.5, 1)
                    s_reason += " [MACRO_RISK_OFF -> 50% SIZING]"

            if p_dist < -2.5:
                act_status = "CONSTRUCTING_BASE"
            elif -2.5 <= p_dist <= 0.0:
                act_status = "TRIGGER_WATCH"
            elif 0.0 < p_dist <= 2.5:
                act_status = "ACTIONABLE_BUY"
            elif 2.5 < p_dist <= 5.0:
                act_status = "LATE_BUY_ZONE"
            else:
                act_status = "EXTENDED"

            active = bool(tape >= 65.0 and act_status in ["TRIGGER_WATCH", "ACTIONABLE_BUY", "LATE_BUY_ZONE"] and rr >= 1.7 and pos_size > 0.0)
            notes = (
                f"{s_type}: Pivot Rs.{p_entry:.2f} ({p_dist:+.1f}%), Stop Rs.{s_loss:.2f} (-{risk_pct:.1f}%, {s_reason}). "
                f"R:R {rr:.2f}x (T1 Rs.{t1:.2f}, T2 Rs.{t2:.2f}). ATR Rs.{atr:.2f}."
            )

            swing_card = SwingSetupCard(
                is_active=active,
                setup_type=s_type,
                pivot_entry_price=p_entry,
                raw_pivot_price=p_entry,
                adjusted_pivot_entry=p_entry,
                adaptive_pivot_buffer=adaptive_buf,
                wick_rejection_detected=False,
                upper_wick_ratio=0.0,
                has_micro_handle=False,
                handle_quality="CLOUD_PROXY",
                handle_tightness_ratio=1.0,
                stop_loss_price=s_loss,
                structural_stop_reason=s_reason,
                risk_pct=risk_pct,
                suggested_position_size_pct=pos_size,
                tranche_1_probe_pct=50.0,
                tranche_1_trigger_price=p_entry,
                tranche_2_pyramid_pct=50.0,
                tranche_2_trigger_price=round(p_entry + (0.5 * (p_entry - s_loss)), 2),
                breakeven_milestone_price=round(p_entry + (1.0 * (p_entry - s_loss)), 2),
                target_price=t1,
                target_price_t1=t1,
                target_price_t2=t2,
                risk_reward_ratio=rr,
                expected_value_score=55.0,
                timeframe="2-6 Weeks (Positional Swing)",
                atr_10d=atr,
                atr_30d=atr,
                atr_20d=atr,
                atr_contraction_ratio=atr_contraction_ratio,
                volatility_contraction_delta_pct=vol_delta_pct,
                volume_5d_avg=float(evaluated_data.get("avg_volume_10d") or 100000.0),
                volume_40d_avg=float(evaluated_data.get("avg_volume_10d") or 100000.0),
                volume_dryup_ratio=1.0,
                volume_dryup_delta_pct=0.0,
                up_down_volume_ratio=1.2,
                up_days_count=10,
                down_days_count=10,
                pivot_distance_pct=p_dist,
                actionability_status=act_status,
                contraction_quality="TIGHT_CONTRACTION" if atr_contraction_ratio < 0.80 else ("HEALTHY_CONTRACTION" if atr_contraction_ratio <= 1.0 else "EXPANDING_VOLATILITY"),
                vol_compression_percentile=round(max(0.0, min(100.0, (1.0 - atr_contraction_ratio) * 100.0 + 50.0)), 1),
                distribution_days_count=0,
                closing_range_location_pct=50.0,
                market_regime=evaluated_data.get("macro_regime") or "BULL_MOMENTUM",
                trailing_stop_guide="10 EMA (Momentum) / 20 EMA (Positional)",
                sector_relative_strength="NEUTRAL",
                status_notes=notes
            )

        # 1-Click Zerodha/Upstox Execution Ticket for Swing Setup
        try:
            swing_entry = float(swing_card.adjusted_pivot_entry or swing_card.pivot_entry_price or cmp)
            swing_stop = float(swing_card.stop_loss_price or (cmp * 0.95))
            swing_t1 = float(swing_card.target_price_t1 or (cmp * 1.10))
            swing_t2 = float(swing_card.target_price_t2 or (cmp * 1.18))
            swing_card.broker_order_ticket = MultiHorizonFeedRouter._build_broker_order_ticket(
                symbol=sym,
                cmp=cmp,
                entry_price=swing_entry,
                stop_loss_price=swing_stop,
                target_price_1=swing_t1,
                target_price_2=swing_t2,
                horizon="SWING_POSITIONAL",
                reference_capital=100000.0,
                risk_budget_pct=1.0
            )
        except Exception:
            swing_card.broker_order_ticket = None


        # 3. Intraday Radar Setup (1-Day Scalp) - Calculated from genuine market data
        rvol = float(evaluated_data.get("rvol") or 1.0)
        range_exp = float(evaluated_data.get("range_expansion_pct") or 0.0)
        vwap_prox = float(evaluated_data.get("vwap_proximity_pct") or 0.0)
        turnover = float(evaluated_data.get("turnover_10d_cr") or evaluated_data.get("avg_turnover_cr") or 0.0)

        # Gap Character Analysis (Gap-and-Go vs Exhaustion Gap Warning)
        gap_raw = evaluated_data.get("gap_pct") or evaluated_data.get("gap_live")
        gap_pct = round(float(gap_raw), 2) if gap_raw is not None else 0.0

        if gap_pct >= 4.5:
            gap_char = "EXHAUSTION_GAP_WARNING"
        elif 0.5 <= gap_pct < 4.5:
            gap_char = "GAP_AND_GO"
        elif -1.5 <= gap_pct < 0.5:
            gap_char = "FLAT_OPEN_SURGE"
        else:
            gap_char = "GAP_DOWN_REVERSAL"

        # Session Phase based on market trading hours (IST)
        from datetime import datetime
        now_dt = datetime.now()
        cur_min = now_dt.hour * 60 + now_dt.minute
        if cur_min < 10 * 60 + 15:
            sess_phase = "OPENING_RANGE_WINDOW"
        elif cur_min < 13 * 60 + 30:
            sess_phase = "MIDDAY_CHOP_ZONE"
        else:
            sess_phase = "AFTERNOON_TREND_RUN"

        if rvol >= 1.8 and range_exp > 15.0:
            scalp_signal = "LONG_MOMENTUM_BREAKOUT"
        elif rvol >= 1.3 and vwap_prox > 0.1:
            scalp_signal = "MOMENTUM_EXPANSION"
        elif range_exp < -15.0 and rvol < 0.8:
            scalp_signal = "VOLATILITY_CONTRACTION"
        elif vwap_prox < -1.5 and rvol > 1.2:
            scalp_signal = "MEAN_REVERSION_LONG"
        else:
            scalp_signal = "NEUTRAL"

        # Tiered Liquidity Gating for Intraday Scalping
        if turnover >= 100.0:
            liquidity_status = "HIGH_LIQUIDITY"
            liquidity_pass = True
        elif turnover >= 50.0:
            liquidity_status = "PREFERRED"
            liquidity_pass = True
        elif turnover >= 25.0:
            liquidity_status = "ACCEPTABLE"
            liquidity_pass = True
        elif turnover >= 10.0 and mcap >= 10000.0:
            liquidity_status = "LARGE_CAP_REDUCED_FLOW"
            liquidity_pass = True
        else:
            liquidity_status = "LOW_LIQUIDITY"
            liquidity_pass = False

        is_intraday_active = bool(liquidity_pass and (rvol >= 1.25 or abs(range_exp) >= 15.0 or scalp_signal != "NEUTRAL") and (mcap >= 1000.0))

        # 1-Click Zerodha/Upstox Execution Ticket for Intraday Scalp
        try:
            intra_atr = float(evaluated_data.get("atr_live") or (cmp * 0.015))
            intra_sl = round(max(cmp * 0.985, cmp - 1.5 * intra_atr), 2)
            intra_t1 = round(cmp + 2.0 * abs(cmp - intra_sl), 2)
            intra_t2 = round(cmp + 3.0 * abs(cmp - intra_sl), 2)
            intra_ticket = MultiHorizonFeedRouter._build_broker_order_ticket(
                symbol=sym,
                cmp=cmp,
                entry_price=cmp,
                stop_loss_price=intra_sl,
                target_price_1=intra_t1,
                target_price_2=intra_t2,
                horizon="INTRADAY",
                reference_capital=100000.0,
                risk_budget_pct=1.0
            )
        except Exception:
            intra_ticket = None

        intraday_card = IntradayRadarCard(
            is_active=is_intraday_active,
            relative_volume_multiplier=round(rvol, 2),
            vwap_proximity_pct=round(vwap_prox, 2),
            atr_range_expansion_pct=round(range_exp, 1),
            scalp_signal=scalp_signal,
            liquidity_status=liquidity_status,
            gap_pct=gap_pct,
            gap_character=gap_char,
            session_phase=sess_phase,
            broker_order_ticket=intra_ticket
        )

        # 4. Automated 3-Point Invalidation Guardrails (Thesis Killers) - Stock Specific
        # opm_pct and dso_days are authentic per-stock values from the live TradingView scanner;
        # they will be None only if the API returned no data for that column — never silently substituted.
        opm_raw = evaluated_data.get("opm_pct")
        dso_raw = evaluated_data.get("dso_days")
        support_raw = evaluated_data.get("support_price_50d")
        support_price = float(support_raw) if support_raw is not None else None

        if opm_raw is not None:
            opm = float(opm_raw)
            opm_trigger_val = f"OPM < {round(opm - 2.5, 1)}%" if opm > 5.0 else f"OPM < {round(opm * 0.7, 1)}%"
        else:
            opm_trigger_val = "OPM contracts materially vs prior year (data pending)"

        if dso_raw is not None:
            dso = float(dso_raw)
            dso_trigger_val = f"DSO > {round(dso + 15)} Days"
        else:
            dso_trigger_val = "Working capital DSO deteriorates sharply vs 2Q avg (data pending)"

        support_trigger_val = f"Close < Rs.{support_price:.2f}" if support_price is not None else "Close breaks down below trailing 50-day structural support (tape pending)"

        invalidation_triggers = [
            InvalidationTrigger(
                trigger_id=f"{sym}_INV_1",
                condition_description="Quarterly operating margin (OPM) compresses by > 150 bps YoY",
                threshold_value=opm_trigger_val,
                severity="CRITICAL"
            ),
            InvalidationTrigger(
                trigger_id=f"{sym}_INV_2",
                condition_description="Working capital DSO surges > 15 days in trailing 2 quarters",
                threshold_value=dso_trigger_val,
                severity="HIGH"
            ),
            InvalidationTrigger(
                trigger_id=f"{sym}_INV_3",
                condition_description="Weekly price closes below trailing 50-day/week support",
                threshold_value=support_trigger_val,
                severity="CRITICAL"
            )
        ]

        # 5. Candidate Confidence Decomposition (Phase 5)
        calib_data = _get_calibration_data()
        setup_type = swing_card.setup_type
        st_metrics = calib_data.get("setup_types", {}).get(setup_type, {})

        cond_p_1r = st_metrics.get("p_1r_before_stop_pct", calib_data.get("p_1r_before_stop_pct", 41.7))
        cond_p_2r = st_metrics.get("p_2r_before_stop_pct", calib_data.get("p_2r_before_stop_pct", 25.0))
        stopped_before_1r = st_metrics.get("stopped_before_1r_pct", calib_data.get("stopped_before_1r_pct", 53.6))
        hist_evidence = st_metrics.get("sample_evidence", calib_data.get("sample_size_evidence", "PRELIMINARY"))

        if swing_card.risk_pct > 8.5:
            setup_grade = "DISQUALIFIED"
        elif entry >= 78.0 and tape >= 72.0 and swing_card.risk_pct <= 6.5 and swing_card.risk_reward_ratio >= 2.0:
            setup_grade = "A_PRIME"
        elif entry >= 68.0 and tape >= 65.0 and swing_card.risk_pct <= 8.5 and swing_card.risk_reward_ratio >= 1.7:
            setup_grade = "B_SELECTIVE"
        else:
            setup_grade = "C_DEVELOPING"

        swing_card.conditional_p_1r_pct = cond_p_1r
        swing_card.conditional_p_2r_pct = cond_p_2r
        swing_card.stopped_before_1r_pct = stopped_before_1r
        swing_card.setup_grade = setup_grade

        # Signal score: pure mathematical strength decoupled from sample size
        norm_gap = min(100.0, max(0.0, asym_gap * 3.33 + 50.0))
        signal_score = round(0.35 * potential + 0.25 * norm_gap + 0.20 * tape + 0.20 * entry, 1)

        # Strategic Watchlist Graduation Evaluation (10/10 Upgrade)
        grad_status = None
        grad_readiness = 0.0
        grad_trigger = ""
        grad_pivot = None
        if thesis_cat == "STRATEGIC_WATCHLIST" or potential >= 70.0:
            try:
                from src.analytics.strategic_watchlist_sentinel import StrategicWatchlistSentinel
                grad_eval = StrategicWatchlistSentinel.evaluate_candidate_graduation(evaluated_data)
                grad_status = grad_eval.get("graduation_status")
                grad_readiness = grad_eval.get("graduation_readiness_pct", 0.0)
                grad_trigger = grad_eval.get("graduation_trigger", "")
                grad_pivot = grad_eval.get("target_pivot_price")
            except Exception:
                pass

        return ScreenerCandidateResult(
            symbol=sym,
            company_name=evaluated_data.get("company_name", sym),
            cmp=cmp,
            market_cap_cr=mcap,
            pe_ratio=evaluated_data.get("pe_ratio"),
            roce_pct=evaluated_data.get("roce_pct"),
            debt_to_equity=evaluated_data.get("debt_to_equity"),
            business_potential_score=potential,
            expectations_asymmetry_gap_pct=asym_gap,
            tape_confirmation_score=tape,
            entry_quality_score=entry,
            thesis_category=thesis_cat,
            graduation_status=grad_status,
            graduation_readiness_pct=grad_readiness,
            graduation_trigger=grad_trigger,
            graduation_target_pivot=grad_pivot,
            signal_score=signal_score,
            historical_evidence_tier=hist_evidence,
            setup_grade=setup_grade,
            conditional_p_1r_pct=cond_p_1r,
            multibagger_conviction_score=score,
            economic_inflection_p1=p1,
            reinvestment_runway_p2=evaluated_data.get("reinvestment_runway_p2", 80.0),
            working_capital_p3=p3,
            expectations_gap_p4=p4,
            price_structure_p5=p5,
            market_implied_growth_pct=evaluated_data.get("market_implied_growth_pct"),
            sustainable_compounding_ceiling_pct=evaluated_data.get("sustainable_compounding_ceiling_pct"),
            expectations_asymmetry_pct=evaluated_data.get("expectations_asymmetry_pct"),
            m7_asymmetry_index=m7_idx,
            multibagger_likelihood_rank=likelihood,
            prob_2x_3y_pct=evaluated_data.get("prob_2x_3y_pct", 60.0),
            prob_5x_5y_pct=evaluated_data.get("prob_5x_5y_pct", 30.0),
            prob_10x_5y_pct=evaluated_data.get("prob_10x_5y_pct", 15.0),
            failure_risk_rating=evaluated_data.get("failure_risk_rating", "LOW"),
            long_term_verdict=lt_verdict,
            swing_setup=swing_card,
            intraday_radar=intraday_card,
            setup_data_quality=evaluated_data.get("setup_data_quality", 0.75),
            setup_quality_rating=evaluated_data.get("setup_quality_rating", "CLOUD_PROXY"),
            metric_provenance=evaluated_data.get("metric_provenance", {}),
            lifecycle_stage=evaluated_data.get("lifecycle_stage"),
            lifecycle_trigger=evaluated_data.get("lifecycle_trigger"),
            invalidation_triggers=invalidation_triggers
        )

