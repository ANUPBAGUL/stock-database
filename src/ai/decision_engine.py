"""
Unified Institutional Decision Engine.

Synthesizes Long-Term (M6), Swing (2-4W), and Intraday (1D) model outputs into
actionable, decision-grade institutional intelligence answering the 9 Fundamental Multibagger Discovery Questions:
1. Could this become a 2x?
2. Could this become a 5x?
3. Could this become a 10x?
4. Are we early?
5. Why could it happen?
6. What could invalidate it?
7. Is the market already pricing it?
8. Can I actually buy it? (Liquidity & Capacity)
9. What would make us wrong? (Explicit falsifiable conditions)
"""

import logging
from datetime import date
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from src.ai.longterm_engine import LongTermEngine
from src.ai.swing_engine import SwingEngine
from src.ai.intraday_engine import IntradayEngine
from src.ai.m6_frozen import M6FrozenResearchModel
from src.db.models import Company, DailyPriceRaw

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DecisionEngine:
    """
    Unified Multi-Horizon Institutional Decision Engine with 9-Question Multibagger Discovery Matrix.
    """

    @staticmethod
    def generate_full_stock_intelligence(
        db: Session,
        company_id: str,
        as_of_date: date,
        macro_regime: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generates deep 360-degree stock intelligence across all 3 horizons with multibagger discovery answers.

        Args:
            macro_regime: Optional dict from MacroRegimeClient.fetch_current_macro_regime().
                          When provided, verdict and sizing_guidance are adjusted for RISK_OFF conditions.
                          Keys used: macro_regime (str), india_vix (float), risk_stance (str).
        """
        longterm_data = LongTermEngine.evaluate_company(db, company_id, as_of_date)
        swing_data = SwingEngine.evaluate_company(db, company_id, as_of_date)
        intraday_data = IntradayEngine.evaluate_company(db, company_id, as_of_date)
        m6_frozen_data = M6FrozenResearchModel.evaluate_company(db, company_id, as_of_date)

        comp = db.query(Company).filter_by(company_id=company_id).first()
        symbol = comp.nse_symbol if comp else "UNKNOWN"
        name = comp.company_name if comp else "Unknown Company"
        sector_name = comp.sector.sector_name if (comp and comp.sector) else "General"

        # Calculate 20-day ADV & liquidity trade capacity
        prices = db.query(DailyPriceRaw).filter(
            DailyPriceRaw.company_id == company_id,
            DailyPriceRaw.trading_date <= as_of_date
        ).order_by(DailyPriceRaw.trading_date.desc()).limit(20).all()

        current_price = prices[0].close_price if prices else 0.0
        avg_vol_20 = sum(p.volume for p in prices) / max(1, len(prices)) if prices else 0.0
        daily_turnover_cr = round((avg_vol_20 * current_price) / 10000000.0, 2)
        max_position_size_cr = round(daily_turnover_cr * 0.05, 2)

        # Primary Horizon Recommendation
        lt_score = longterm_data.get("longterm_score", 50)
        sw_score = swing_data.get("swing_score", 50) if swing_data else 50
        intra_score = intraday_data.get("intraday_score", 50) if intraday_data else 50

        # Build "Why Buy?" Positive Catalysts
        why_buy = []
        if longterm_data.get("thesis_drivers"):
            why_buy.extend([f"[Long-Term] {t}" for t in longterm_data["thesis_drivers"][:2]])
        if swing_data and swing_data.get("thesis_drivers"):
            why_buy.extend([f"[Swing] {t}" for t in swing_data["thesis_drivers"][:2]])
        if intraday_data and intraday_data.get("thesis_drivers"):
            why_buy.extend([f"[Intraday] {t}" for t in intraday_data["thesis_drivers"][:1]])

        # Build "Why NOT Buy?" Structural Risks & Friction
        why_not_buy = []
        m = longterm_data.get("metrics", {})
        pe_val = m.get("trailing_pe")
        if pe_val and pe_val > 55.0:
            why_not_buy.append(f"Valuation Friction: Trailing P/E at {pe_val:.1f}x (Higher percentile valuation band)")
        
        if longterm_data.get("risk_factors"):
            why_not_buy.extend([f"[Fundamental Risk] {r}" for r in longterm_data["risk_factors"][:2]])

        if swing_data and swing_data.get("risk_invalidation"):
            why_not_buy.extend([f"[Technical Invalidation] {inv}" for inv in swing_data["risk_invalidation"][:1]])

        why_not_buy.append(f"[Liquidity Constraint] Max safe deployment capped at Rs.{max_position_size_cr:,.2f} Cr (<5% 20D ADV)")

        # Balanced Verdict & Position Sizing Guidance
        if lt_score >= 75 and sw_score >= 60:
            primary_verdict = "STRONG_MULTI_YEAR_BUY"
            horizon_recommendation = "Long-Term Compounder with Swing Tailwinds"
            sizing_guidance = "Full Position Size (100% Capital Allocation)"
        elif sw_score >= 70:
            primary_verdict = "BULLISH_SWING_BREAKOUT"
            horizon_recommendation = "2-4 Weeks Swing Setup"
            sizing_guidance = "Standard Swing Allocation (Trailing Stop Active)"
        elif intra_score >= 80:
            primary_verdict = "INTRADAY_MOMENTUM_PLAY"
            horizon_recommendation = "1-Day Breakout Scalp"
            sizing_guidance = "Day-Trade Risk Budget (1:2.0 RR Required)"
        elif lt_score >= 65:
            primary_verdict = "ACCUMULATE_ON_DIPS"
            horizon_recommendation = "Long-Term Quality Watchlist"
            sizing_guidance = "Partial Allocation (50% Size on Pullbacks)"
        else:
            primary_verdict = "NEUTRAL_WATCHLIST"
            horizon_recommendation = "Monitor for Catalyst / Setup"
            sizing_guidance = "Zero Capital Allocation (Wait for Setup Confirmation)"

        # ── Macro Regime Override ──
        # When MacroRegimeClient signals RISK_OFF_CORRECTION, downgrade verdicts and
        # cut position sizing regardless of individual stock scores. Markets in risk-off
        # mode render even high-conviction setups dangerous due to correlated drawdowns.
        regime_label = (macro_regime or {}).get("macro_regime", "NEUTRAL_CONSOLIDATION")
        india_vix = (macro_regime or {}).get("india_vix")
        regime_note = None

        if regime_label == "RISK_OFF_CORRECTION":
            regime_note = (
                f"⚠️ MACRO RISK-OFF: India VIX {india_vix:.1f} — "
                "Position sizing reduced. New entries not recommended until regime normalises."
            ) if india_vix else "⚠️ MACRO RISK-OFF: Defensive posture active."

            # Downgrade aggressive verdicts; preserve watchlist/neutral unchanged
            if primary_verdict == "STRONG_MULTI_YEAR_BUY":
                primary_verdict = "ACCUMULATE_ON_DIPS"
                sizing_guidance = "Reduced Allocation (25% Size — Risk-Off Regime Active)"
            elif primary_verdict in ("BULLISH_SWING_BREAKOUT", "INTRADAY_MOMENTUM_PLAY"):
                primary_verdict = "NEUTRAL_WATCHLIST"
                sizing_guidance = "Zero Capital Allocation (Risk-Off — Await Regime Normalisation)"
            elif primary_verdict == "ACCUMULATE_ON_DIPS":
                sizing_guidance = "Minimal Allocation (10% Size — Risk-Off Regime Active)"

            why_not_buy.append(f"[Macro Risk] {regime_note}")

        elif regime_label == "NEUTRAL_CONSOLIDATION":
            regime_note = (
                f"Macro: NEUTRAL — India VIX {india_vix:.1f}. Selective allocation only."
            ) if india_vix else "Macro: NEUTRAL — Selective allocation only."

        # 9 Fundamental Multibagger Discovery Questions Evaluation
        roce_val = m.get("ttm_roce_pct") or 15.0
        fcf_y = m.get("ttm_fcf_yield_pct") or 2.5
        pe_str = f"{pe_val:.1f}x" if pe_val else "Moderate"

        multibagger_discovery_matrix = {
            "q1_could_become_2x": {
                "question": "Could this become a 2×?",
                "assessment": f"High Probability ({lt_score}/100 Conviction Score)" if lt_score >= 75 else "Moderate Probability",
                "score": lt_score
            },
            "q2_could_become_5x": {
                "question": "Could this become a 5×?",
                "assessment": "Strong Tail Potential (ROCE > 20% + FCF Conversion)" if roce_val >= 20.0 and fcf_y > 2.0 else "Requires Sustained Growth Acceleration",
                "score": round(lt_score * 0.85, 1)
            },
            "q3_could_become_10x": {
                "question": "Could this become a 10×?",
                "assessment": "Extreme Outlier Candidate (Capital Reinvestment Runway)" if lt_score >= 85 and daily_turnover_cr < 100 else "Standard Quality Compounder (Not 10x Scale)",
                "score": round(lt_score * 0.65, 1)
            },
            "q4_are_we_early": {
                "question": "Are we early?",
                "assessment": "Early Entry (Valuation in Reasonable Band)" if (pe_val and pe_val <= 45.0) else "Mid-Stage Compounder (Rerating Underway)",
                "distance_from_t0_profile": "Optimal T0 Profile Match" if lt_score >= 80 else "Developing Pattern"
            },
            "q5_why_could_it_happen": {
                "question": "Why could it happen?",
                "drivers": why_buy[:3] if why_buy else ["Strong balance sheet and sustained reinvestment moat."]
            },
            "q6_what_could_invalidate_it": {
                "question": "What could invalidate it?",
                "friction_factors": why_not_buy[:2] if why_not_buy else ["Macro market correction or earnings slowdown."]
            },
            "q7_is_market_pricing_it": {
                "question": "Is the market already pricing it?",
                "valuation_verdict": f"Trailing P/E at {pe_str} - " + ("Expectations Elevated" if (pe_val and pe_val > 55) else "Fairly Valued for Growth Rate")
            },
            "q8_can_investor_buy_it": {
                "question": "Can I actually buy it?",
                "liquidity_verdict": f"Yes - Up to ₹{max_position_size_cr:,.2f} Cr deployable under 5% ADV participation limit ({avg_vol_20:,.0f} shares/day)."
            },
            "q9_what_would_make_us_wrong": {
                "question": "What would make us wrong?",
                "invalidation_criteria": [
                    "ROCE deteriorates below 15% across two consecutive quarters",
                    "CFO / PAT divergence exceeds 40% (working capital leakage)",
                    "Weekly close below the 200-day moving average"
                ]
            }
        }

        return {
            "company_id": company_id,
            "symbol": symbol,
            "company_name": name,
            "sector": sector_name,
            "current_price": current_price,
            "as_of_date": as_of_date.isoformat(),
            "primary_verdict": primary_verdict,
            "horizon_recommendation": horizon_recommendation,
            "sizing_guidance": sizing_guidance,
            "horizon_ratings": {
                "longterm": {
                    "score": lt_score,
                    "m6_frozen_score": m6_frozen_data["m6_conviction_score"],
                    "research_status": "HISTORICALLY_VALIDATED",
                    "evidence_tier": "🟢 Tier 1: Historically Validated (EXP-001/002) // Prospective Active (EXP-004)",
                    "confidence_level": "HIGH (90%)",
                    "grade": longterm_data.get("conviction_grade", "NEUTRAL"),
                    "roce_pct": m.get("ttm_roce_pct"),
                    "fcf_yield_pct": m.get("ttm_fcf_yield_pct"),
                    "pe_ratio": m.get("trailing_pe")
                },
                "swing": {
                    "score": sw_score,
                    "research_status": "WALK_FORWARD_TESTED",
                    "evidence_tier": "🟡 Tier 2: Walk-Forward Backtested (ATR Risk Managed)",
                    "confidence_level": "MODERATE (70%)",
                    "setup": swing_data.get("setup_type", "CONSOLIDATION") if swing_data else "N/A",
                    "stop_loss": swing_data.get("stop_loss") if swing_data else None,
                    "target_price": swing_data.get("target_price") if swing_data else None,
                    "expected_gain_pct": swing_data.get("expected_gain_pct") if swing_data else None,
                    "risk_reward": swing_data.get("risk_reward_ratio") if swing_data else None
                },
                "intraday": {
                    "score": intra_score,
                    "research_status": "HEURISTIC_RULE_BASED",
                    "evidence_tier": "🟠 Tier 3: Heuristic Rule-Based (Not Prospectively Validated)",
                    "confidence_level": "EXPERIMENTAL (50%)",
                    "setup": intraday_data.get("setup_name", "RANGE") if intraday_data else "N/A",
                    "stop_loss": intraday_data.get("stop_loss") if intraday_data else None,
                    "target_price": intraday_data.get("target_price") if intraday_data else None,
                    "risk_reward": intraday_data.get("risk_reward_ratio") if intraday_data else None
                }
            },
            "liquidity_capacity": {
                "avg_daily_volume_20": int(avg_vol_20),
                "avg_daily_turnover_cr": daily_turnover_cr,
                "max_safe_position_size_cr": max_position_size_cr,
                "capacity_note": f"Max recommended deployment: ₹{max_position_size_cr:,.2f} Cr (5% ADV participation)"
            },
            "dual_thesis": {
                "why_buy": why_buy if why_buy else ["Solid long-term business profile and steady momentum."],
                "why_not_buy": why_not_buy if why_not_buy else ["Standard equity market volatility and macro risk factors."]
            },
            "executive_thesis": why_buy if why_buy else ["Solid long-term business profile and steady momentum."],
            "risk_invalidation_triggers": why_not_buy if why_not_buy else ["Standard equity market volatility and macro risk factors."],
            "multibagger_discovery_matrix": multibagger_discovery_matrix,
            "macro_regime": {
                "regime": regime_label,
                "india_vix": india_vix,
                "risk_stance": (macro_regime or {}).get("risk_stance"),
                "brent_crude_usd": (macro_regime or {}).get("brent_crude_usd"),
                "usdinr_exchange_rate": (macro_regime or {}).get("usdinr_exchange_rate"),
                "regime_note": regime_note,
                "source": "MacroRegimeClient" if macro_regime else "NOT_FETCHED",
            },
            "m6_frozen_research_record": m6_frozen_data,
            "full_longterm_details": longterm_data,
            "full_swing_details": swing_data,
            "full_intraday_details": intraday_data
        }
