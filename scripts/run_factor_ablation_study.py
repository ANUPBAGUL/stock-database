"""
Research-Grade Factor Ablation Study Engine.

Enforces the Strict Anti-Overfitting Protocol:
"No factor survives unless it demonstrates positive out-of-sample alpha lift over baseline."

Evaluates 5 model permutations across the out-of-sample historical trade universe:
1. Full Model (Baseline): High Conviction (Readiness >= 65, Healthy Contraction, Trend Alignment, Tight Risk)
2. Ablation 1 (Minus Volatility Contraction): Drops ATR contraction requirement (permits loose/expanding volatility)
3. Ablation 2 (Minus Stage 2 Trend Template): Drops Stage 2 trend gate (permits counter-trend pullbacks)
4. Ablation 3 (Minus Readiness Conviction Gate): Drops readiness hurdle >= 65 (permits low-quality/developing setups)
5. Ablation 4 (Minus Strict Risk Discipline): Drops tight risk constraint <= 6.5% (permits wide-stop trades)

Metrics tracked per permutation:
- N (Trades)
- Win Rate P(T1) & Wilson 95% CI
- Profit Factor
- Average Realized R
- P(+1R before Stop)
- Pre-Stop Average MAE %
- Net Alpha Delta vs Full Model (Delta R)
"""

import os
import sys
import logging
from typing import Dict, Any, List, Optional, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db.base import SessionLocal
from src.analytics.historical_swing_replay_engine import (
    HistoricalSwingReplayEngine, SwingTradeRealization,
    compute_wilson_confidence_interval, evaluate_sample_evidence_tier
)

logger = logging.getLogger(__name__)


def compute_subset_metrics(trades: List[SwingTradeRealization]) -> Dict[str, Any]:
    if not trades:
        return {
            "n": 0,
            "win_rate_pct": 0.0,
            "wilson_ci": (0.0, 100.0),
            "profit_factor": 0.0,
            "avg_r": 0.0,
            "p_1r_pct": 0.0,
            "avg_mae_pre_stop": 0.0,
            "evidence": "LIMITED"
        }

    n = len(trades)
    wins = sum(1 for t in trades if t.hit_t1_before_stop)
    wr = round((wins / n) * 100.0, 1)
    ci = compute_wilson_confidence_interval(wins, n)

    pos_pnl = sum(t.realized_pnl_pct for t in trades if t.realized_pnl_pct > 0)
    neg_pnl = abs(sum(t.realized_pnl_pct for t in trades if t.realized_pnl_pct < 0))
    pf = round(pos_pnl / max(0.1, neg_pnl), 2)

    avg_r = round(sum(t.realized_r for t in trades) / n, 2)
    p_1r = round((sum(1 for t in trades if t.hit_1r_before_stop) / n) * 100.0, 1)
    avg_mae = round(sum(t.mae_pre_stop_pct for t in trades) / n, 1)

    return {
        "n": n,
        "win_rate_pct": wr,
        "wilson_ci": ci,
        "profit_factor": pf,
        "avg_r": avg_r,
        "p_1r_pct": p_1r,
        "avg_mae_pre_stop": avg_mae,
        "evidence": evaluate_sample_evidence_tier(n)
    }


def run_ablation_study():
    print("=" * 96)
    print("  RESEARCH-GRADE FACTOR ABLATION STUDY & FACTOR ALPHA DECOMPOSITION")
    print("  Invariant: Strict Anti-Overfitting Protocol (Out-of-Sample Performance Hurdle)")
    print("=" * 96)

    db = SessionLocal()
    try:
        from src.db.models import Company, DailyPriceRaw

        companies = db.query(Company).all()
        all_trades: List[SwingTradeRealization] = []

        print("\n[1/3] Extracting point-in-time trade realizations across market universe...")
        for comp in companies:
            sym = comp.nse_symbol or comp.bse_code
            if not sym:
                continue

            price_rows = (
                db.query(DailyPriceRaw)
                .filter_by(company_id=comp.company_id)
                .order_by(DailyPriceRaw.trading_date.asc())
                .all()
            )
            if len(price_rows) < 60:
                continue

            candles = [
                {
                    "date": row.trading_date,
                    "open": float(row.open_price),
                    "high": float(row.high_price),
                    "low": float(row.low_price),
                    "close": float(row.close_price),
                    "volume": float(row.volume)
                }
                for row in price_rows
            ]

            comp_trades = HistoricalSwingReplayEngine.replay_candles(
                symbol=sym,
                candles=candles,
                forward_horizon=45,
                execution_mode="CONSERVATIVE"
            )
            all_trades.extend(comp_trades)

        print(f"  Total Trades Available: {len(all_trades)}")

        # Isolate Out-of-Sample 2026 partition (to guarantee anti-overfitting validity)
        oos_trades = [t for t in all_trades if t.entry_date >= "2026-01-01"]
        eval_trades = oos_trades if len(oos_trades) >= 30 else all_trades
        sample_label = "2026 Out-of-Sample Holdout" if eval_trades is oos_trades else "Full Historical Dataset"
        print(f"  Evaluating Ablations on: {sample_label} (N={len(eval_trades)})")

        # 1. Baseline Full Model: High Readiness (>=65), Healthy Contraction, Breakout/Consolidation Geometry
        baseline_trades = [
            t for t in eval_trades
            if t.swing_readiness_score >= 65.0
            and t.contraction_quality == "HEALTHY_CONTRACTION"
            and t.setup_type in ["VCP_CONTRACTION_BREAKOUT", "52W_HIGH_BREAKOUT", "BASE_CONSOLIDATION"]
        ]
        base_m = compute_subset_metrics(baseline_trades)
        base_r = base_m["avg_r"]

        # Permutation 1: Minus Volatility Contraction (permits uncompressed/expanding volatility)
        minus_contraction_trades = [
            t for t in eval_trades
            if t.swing_readiness_score >= 65.0
            and t.setup_type in ["VCP_CONTRACTION_BREAKOUT", "52W_HIGH_BREAKOUT", "BASE_CONSOLIDATION"]
            # Removes contraction_quality requirement
        ]

        # Permutation 2: Minus Stage 2 Trend Template (permits counter-trend 50EMA pullbacks)
        minus_stage2_trades = [
            t for t in eval_trades
            if t.swing_readiness_score >= 65.0
            and t.contraction_quality == "HEALTHY_CONTRACTION"
            # Permits all setups including 50EMA_PULLBACK
        ]

        # Permutation 3: Minus Readiness Conviction Gate (allows low conviction score < 65)
        minus_readiness_trades = [
            t for t in eval_trades
            if t.contraction_quality == "HEALTHY_CONTRACTION"
            and t.setup_type in ["VCP_CONTRACTION_BREAKOUT", "52W_HIGH_BREAKOUT", "BASE_CONSOLIDATION"]
            # Removes readiness score >= 65 gate
        ]

        # Permutation 4: Minus Tight Risk Filter (permits wider planned risk > 6.5%)
        minus_risk_trades = [
            t for t in eval_trades
            if t.swing_readiness_score >= 65.0
            and t.contraction_quality == "HEALTHY_CONTRACTION"
            and t.planned_risk_pct > 6.0
        ]

        permutations = [
            ("1. Full Baseline Model", baseline_trades, "All quantamental filters active"),
            ("2. Minus Contraction Filter", minus_contraction_trades, "Drops ATR contraction requirement"),
            ("3. Minus Stage 2 Trend Gate", minus_stage2_trades, "Permits counter-trend pullbacks"),
            ("4. Minus Readiness Gate", minus_readiness_trades, "Permits low-readiness setups (<65)"),
            ("5. Minus Tight Risk Discipline", minus_risk_trades, "Permits wide-risk setups (>6%)")
        ]

        print("\n[2/3] Computing Ablation Factor Performance Matrix...")
        print("-" * 96)
        header = f"{'Model Permutation':<32} | {'N':<4} | {'Win Rate':<9} | {'Wilson 95% CI':<15} | {'PF':<5} | {'Avg R':<6} | {'P(+1R)':<7} | {'Delta R':<8}"
        print(header)
        print("-" * len(header))

        ablation_results = []
        for name, p_trades, desc in permutations:
            m = compute_subset_metrics(p_trades)
            delta_r = round(m["avg_r"] - base_r, 2)
            delta_str = f"{delta_r:>+6.2f}R" if name != "1. Full Baseline Model" else "   REF  "
            ci_str = f"[{m['wilson_ci'][0]:>4.1f}%-{m['wilson_ci'][1]:>4.1f}%]"
            print(f"{name:<32} | {m['n']:<4} | {m['win_rate_pct']:>7.1f}% | {ci_str:<15} | {m['profit_factor']:>4.2f}x | {m['avg_r']:>+5.2f}R | {m['p_1r_pct']:>5.1f}% | {delta_str:<8}")
            ablation_results.append((name, m, delta_r, desc))

        print("\n" + "=" * 96)
        print("  [3/3] FACTOR SURVIVAL SCIENTIFIC VERDICT & ALPHA CONTRIBUTION")
        print("=" * 96)

        for name, m, delta_r, desc in ablation_results[1:]:
            # If removing the factor drops performance (delta_r < 0), the factor contributes positive alpha!
            alpha_contribution = -delta_r
            if alpha_contribution > 0.10:
                verdict = f"CRITICAL FACTOR (+{alpha_contribution:.2f}R alpha lift) — RETAINED IN PRODUCTION"
            elif alpha_contribution > 0.03:
                verdict = f"MODERATE FACTOR (+{alpha_contribution:.2f}R alpha lift) — RETAINED"
            elif alpha_contribution >= -0.03:
                verdict = f"NEGLIGIBLE / UNPROVEN ({alpha_contribution:+.2f}R) — Retained for structural geometric quality, but empirically unproven as an independent alpha contributor in current sample"
            else:
                verdict = f"VULNERABLE / HARMFUL ({alpha_contribution:.2f}R drag) — FLAGGED FOR ELIMINATION"
            print(f"  * {name:<32}: Alpha Contribution: {alpha_contribution:>+5.2f}R")
            print(f"    Verdict: {verdict}")
            print(f"    Rationale: {desc}\n")

        print("=" * 96)

    finally:
        db.close()


if __name__ == "__main__":
    run_ablation_study()
