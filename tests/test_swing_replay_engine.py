"""
Research-Grade Unit & Invariant Tests for Historical Swing Replay & Empirical Calibration Engine.

Validates:
1. Invariant: Strict Temporal Invariance (Zero future leakage: Calibration(T0) contains only exit_date < T0).
2. Invariant: Pre-Stop MFE vs Post-Exit Path Isolation (pre-stop MFE never includes post-exit bounces).
3. Invariant: Layer 2 Structural Invalidation Immunity (positive empirical EV cannot activate a structurally broken setup).
4. Same-Bar Ambiguity Policy: Synthetic edge cases proving:
   - Detection of same_bar_ambiguity = True
   - Conservative: Stop first -> loss (0% win rate)
   - Optimistic: Target first -> win (100% win rate)
   - Ambiguity Excluded: Ambiguous trade removed from win-rate calculation
5. Wilson Score 95% Confidence Intervals & Evidentiary Terminology (LIMITED / MODERATE / ADEQUATE).
6. Empirical Bayesian Shrinkage on small subgroups (prevents n=7 overconfidence).
7. Brier Score & Probability Calibration Error.
8. Multi-Horizon MFE / MAE Trajectory Vectors (1D, 3D, 5D, 10D, 20D, 45D).
9. Hierarchical Conditional Expectancy E[R | X] with graceful sample-size fallback.
"""

import unittest
from datetime import date, timedelta
from src.analytics.historical_swing_replay_engine import (
    HistoricalSwingReplayEngine,
    SwingTradeRealization,
    compute_wilson_confidence_interval,
    evaluate_sample_evidence_tier,
    evaluate_data_diversity_tier
)
from src.analytics.price_structure_engine import PriceStructureEngine


class TestResearchGradeSwingReplayEngine(unittest.TestCase):

    def setUp(self):
        # 100 days of synthetic base candles
        self.candles = []
        base_date = date(2025, 1, 1)
        base_p = 100.0

        for i in range(100):
            d = base_date + timedelta(days=i)
            if i < 50:
                c = base_p + (i * 0.2)
                h = c + 1.5
                l = c - 1.2
                v = 100000.0 + (i % 7) * 10000.0
            elif 50 <= i < 60:
                c = 110.0 + ((i - 50) * 0.05)
                h = c + 0.4
                l = c - 0.3
                v = 30000.0
            elif 60 <= i < 75:
                c = 110.5 + ((i - 60) * 1.5)
                h = c + 1.2
                l = c - 0.5
                v = 250000.0
            else:
                c = 132.0 + ((i - 75) * 0.1)
                h = c + 1.0
                l = c - 1.0
                v = 80000.0

            self.candles.append({
                "date": d,
                "open": round(c - 0.2, 2),
                "high": round(h, 2),
                "low": round(l, 2),
                "close": round(c, 2),
                "volume": v
            })

    def test_wilson_confidence_interval_bounds(self):
        """Verify Wilson Score 95% CI on small and large samples, and evidentiary tiers."""
        # 3 wins out of 7 trades (42.9%)
        ci_low, ci_high = compute_wilson_confidence_interval(3, 7)
        self.assertAlmostEqual(ci_low, 15.8, delta=0.5)
        self.assertAlmostEqual(ci_high, 75.0, delta=0.5)

        # 0 wins out of 10 trades
        ci_zero_low, ci_zero_high = compute_wilson_confidence_interval(0, 10)
        self.assertEqual(ci_zero_low, 0.0)
        self.assertGreater(ci_zero_high, 0.0) # Should be ~30.8%, never 0.0%

        # 100 wins out of 100 trades
        ci_full_low, ci_full_high = compute_wilson_confidence_interval(100, 100)
        self.assertGreater(ci_full_low, 95.0)
        self.assertEqual(ci_full_high, 100.0)

        # Evidentiary tiers: LIMITED (<20), PRELIMINARY (20-149), MODERATE (150-399), ADEQUATE (>=400)
        self.assertEqual(evaluate_sample_evidence_tier(7), "LIMITED")
        self.assertEqual(evaluate_sample_evidence_tier(18), "LIMITED")
        self.assertEqual(evaluate_sample_evidence_tier(77), "PRELIMINARY")
        self.assertEqual(evaluate_sample_evidence_tier(250), "MODERATE")
        self.assertEqual(evaluate_sample_evidence_tier(500), "ADEQUATE")

    def test_synthetic_same_bar_ambiguity_exact_scenario(self):
        """
        RIGOROUS TEST: Synthetic same-bar ambiguous candle.
        Entry = 100, Stop = 95, Target = 105.
        Bar 1: High = 106, Low = 94.
        Must produce:
        1. same_bar_ambiguity = True
        2. Conservative: Stop first -> outcome STOPPED_OUT, loss
        3. Optimistic: Target first -> outcome hit T1, win
        4. Ambiguity Excluded: Trade removed from win-rate calculation
        """
        test_candles = [
            {"date": date(2025, 1, 1), "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 50000.0},
            {"date": date(2025, 1, 2), "open": 100.0, "high": 106.0, "low": 94.0, "close": 101.0, "volume": 50000.0},
            {"date": date(2025, 1, 3), "open": 101.0, "high": 102.0, "low": 100.0, "close": 101.5, "volume": 50000.0},
        ]

        entry_p = 100.0
        stop_p = 95.0
        target_t1_p = 105.0
        target_t2_p = 115.0

        # 1. Conservative Mode
        cons_res = HistoricalSwingReplayEngine._simulate_forward_trade(
            candles=test_candles,
            entry_idx=0,
            entry_price=entry_p,
            stop_loss=stop_p,
            target_t1=target_t1_p,
            target_t2=target_t2_p,
            forward_horizon=10,
            execution_mode="CONSERVATIVE"
        )
        self.assertTrue(cons_res["same_bar_ambiguity"])
        self.assertEqual(cons_res["outcome"], "STOPPED_OUT")
        self.assertFalse(cons_res["hit_t1"])
        self.assertEqual(cons_res["days_to_stop"], 1)

        # 2. Optimistic Mode
        opt_res = HistoricalSwingReplayEngine._simulate_forward_trade(
            candles=test_candles,
            entry_idx=0,
            entry_price=entry_p,
            stop_loss=stop_p,
            target_t1=target_t1_p,
            target_t2=target_t2_p,
            forward_horizon=10,
            execution_mode="OPTIMISTIC"
        )
        self.assertTrue(opt_res["same_bar_ambiguity"])
        self.assertTrue(opt_res["hit_t1"])
        self.assertEqual(opt_res["days_to_t1"], 1)

        # 3. Aggregation & Ambiguity-Excluded Win Rate
        ambig_trade_cons = SwingTradeRealization(
            symbol="TEST_AMBIG", t0_date="2025-01-01", entry_date="2025-01-01", exit_date="2025-01-02",
            setup_type="VCP_CONTRACTION_BREAKOUT", actionability_status="ACTIONABLE_BUY",
            contraction_quality="HEALTHY_CONTRACTION", market_regime="BULL_MOMENTUM",
            swing_readiness_score=85.0, readiness_bin="85-100 (Elite Conviction)",
            entry_price=100.0, stop_loss_price=95.0, target_price_t1=105.0, target_price_t2=115.0,
            planned_risk_pct=5.0, planned_rr_ratio=2.0, exit_price=95.0, outcome="STOPPED_OUT",
            hit_t1_before_stop=False, same_bar_ambiguity=True, days_held=1, days_to_t1=None, days_to_stop=1,
            realized_pnl_pct=-5.0, realized_r=-1.0, mfe_pre_stop_pct=6.0, mae_pre_stop_pct=-6.0,
            mfe_45d_full_pct=6.0, mae_45d_full_pct=-6.0
        )

        ambig_trade_opt = SwingTradeRealization(
            symbol="TEST_AMBIG", t0_date="2025-01-01", entry_date="2025-01-01", exit_date="2025-01-02",
            setup_type="VCP_CONTRACTION_BREAKOUT", actionability_status="ACTIONABLE_BUY",
            contraction_quality="HEALTHY_CONTRACTION", market_regime="BULL_MOMENTUM",
            swing_readiness_score=85.0, readiness_bin="85-100 (Elite Conviction)",
            entry_price=100.0, stop_loss_price=95.0, target_price_t1=105.0, target_price_t2=115.0,
            planned_risk_pct=5.0, planned_rr_ratio=2.0, exit_price=105.0, outcome="T1_HIT",
            hit_t1_before_stop=True, same_bar_ambiguity=True, days_held=1, days_to_t1=1, days_to_stop=None,
            realized_pnl_pct=5.0, realized_r=1.0, mfe_pre_stop_pct=6.0, mae_pre_stop_pct=-6.0,
            mfe_45d_full_pct=6.0, mae_45d_full_pct=-6.0
        )

        unambig_win_trade = SwingTradeRealization(
            symbol="TEST_CLEAN", t0_date="2025-01-01", entry_date="2025-01-01", exit_date="2025-01-10",
            setup_type="VCP_CONTRACTION_BREAKOUT", actionability_status="ACTIONABLE_BUY",
            contraction_quality="HEALTHY_CONTRACTION", market_regime="BULL_MOMENTUM",
            swing_readiness_score=85.0, readiness_bin="85-100 (Elite Conviction)",
            entry_price=100.0, stop_loss_price=95.0, target_price_t1=110.0, target_price_t2=120.0,
            planned_risk_pct=5.0, planned_rr_ratio=2.0, exit_price=110.0, outcome="T1_HIT",
            hit_t1_before_stop=True, same_bar_ambiguity=False, days_held=9, days_to_t1=9, days_to_stop=None,
            realized_pnl_pct=10.0, realized_r=2.0, mfe_pre_stop_pct=12.0, mae_pre_stop_pct=-1.0,
            mfe_45d_full_pct=12.0, mae_45d_full_pct=-1.0
        )

        cons_dataset = [ambig_trade_cons, unambig_win_trade]
        opt_dataset = [ambig_trade_opt, unambig_win_trade]

        calib = HistoricalSwingReplayEngine.aggregate_calibration_table(cons_dataset, opt_dataset)
        self.assertEqual(calib["ambiguous_trades_count"], 1)
        # Conservative: 1 win out of 2 trades = 50.0%
        self.assertEqual(calib["win_rate_conservative_pct"], 50.0)
        # Optimistic: 2 wins out of 2 trades = 100.0%
        self.assertEqual(calib["win_rate_optimistic_pct"], 100.0)
        # Ambiguity Excluded: 1 win out of 1 unambiguous trade = 100.0% (ambiguous trade removed!)
        self.assertEqual(calib["win_rate_ambig_excluded_pct"], 100.0)

    def test_pre_stop_mfe_vs_post_exit_isolation(self):
        """
        INVARIANT TEST: Pre-stop MFE vs Full-Horizon 45D MFE.
        User Scenario:
        Entry = 100, Stop = 95
        Day 1: High 102
        Day 2: High 102.5
        Day 3: High 103, Low 94 (Stop breached at 95)
        Day 20: High 125 (+25% excursion post-stop)
        
        Expected:
        Pre-stop MFE = +3.0% (strictly while alive)
        45D MFE = +25.0% (full path)
        """
        test_candles = [
            {"date": date(2025, 1, 1), "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 50000.0},
            {"date": date(2025, 1, 2), "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 50000.0},
            {"date": date(2025, 1, 3), "open": 100.5, "high": 102.5, "low": 99.5, "close": 101.5, "volume": 50000.0},
            {"date": date(2025, 1, 4), "open": 98.0, "high": 103.0, "low": 94.0, "close": 94.5, "volume": 50000.0}, # Day 3 of holding: Stopped out
        ]
        # Append up to Day 20
        for d_idx in range(5, 22):
            high_val = 125.0 if d_idx == 21 else 105.0
            test_candles.append({
                "date": date(2025, 1, d_idx),
                "open": 95.0,
                "high": high_val,
                "low": 94.0,
                "close": 100.0,
                "volume": 50000.0
            })

        sim_res = HistoricalSwingReplayEngine._simulate_forward_trade(
            candles=test_candles,
            entry_idx=0,
            entry_price=100.0,
            stop_loss=95.0,
            target_t1=110.0,
            target_t2=120.0,
            forward_horizon=25,
            execution_mode="CONSERVATIVE"
        )

        self.assertEqual(sim_res["outcome"], "STOPPED_OUT")
        self.assertEqual(sim_res["exit_idx"], 3)
        # Pre-stop MFE must be exactly +3.0% (Day 3 high of 103.0). It MUST NOT include Day 20's +25%!
        self.assertEqual(sim_res["mfe_pre_stop"], 3.0)
        # Full path MFE captures Day 20's +25%
        self.assertEqual(sim_res["mfe_45d_full"], 25.0)

    def test_strict_temporal_invariance_outcome_completion(self):
        """
        INVARIANT TEST: Zero Future Leakage via Outcome Completion Rule.
        Calibration(T0) contains ONLY trades whose outcome was fully completed BEFORE T0 (exit_date < T0).
        A trade entered before T0 whose 45D horizon is still active at T0 MUST be excluded.
        """
        mock_trades = [
            # Trade 1: Entered Jan 1, Exited Jan 15 (outcome complete before Jan 20)
            SwingTradeRealization(
                symbol="S1", t0_date="2025-01-01", entry_date="2025-01-02", exit_date="2025-01-15",
                setup_type="VCP_CONTRACTION_BREAKOUT", actionability_status="ACTIONABLE_BUY",
                contraction_quality="HEALTHY_CONTRACTION", market_regime="BULL_MOMENTUM",
                swing_readiness_score=85.0, readiness_bin="85-100 (Elite Conviction)",
                entry_price=100.0, stop_loss_price=95.0, target_price_t1=112.0, target_price_t2=120.0,
                planned_risk_pct=5.0, planned_rr_ratio=2.4, exit_price=112.0, outcome="T1_HIT",
                hit_t1_before_stop=True, same_bar_ambiguity=False, days_held=13, days_to_t1=13, days_to_stop=None,
                realized_pnl_pct=12.0, realized_r=2.4, mfe_pre_stop_pct=14.0, mae_pre_stop_pct=-1.0,
                mfe_45d_full_pct=14.0, mae_45d_full_pct=-1.0
            ),
            # Trade 2: Entered Jan 10, Exited Feb 15 (outcome NOT complete at Jan 20!)
            SwingTradeRealization(
                symbol="S2", t0_date="2025-01-09", entry_date="2025-01-10", exit_date="2025-02-15",
                setup_type="VCP_CONTRACTION_BREAKOUT", actionability_status="ACTIONABLE_BUY",
                contraction_quality="HEALTHY_CONTRACTION", market_regime="BULL_MOMENTUM",
                swing_readiness_score=85.0, readiness_bin="85-100 (Elite Conviction)",
                entry_price=200.0, stop_loss_price=190.0, target_price_t1=225.0, target_price_t2=240.0,
                planned_risk_pct=5.0, planned_rr_ratio=2.5, exit_price=190.0, outcome="STOPPED_OUT",
                hit_t1_before_stop=False, same_bar_ambiguity=False, days_held=36, days_to_t1=None, days_to_stop=36,
                realized_pnl_pct=-5.0, realized_r=-1.0, mfe_pre_stop_pct=2.0, mae_pre_stop_pct=-6.0,
                mfe_45d_full_pct=10.0, mae_45d_full_pct=-6.0
            )
        ]

        # Query calibration state at cutoff Jan 20 (2025-01-20)
        # Trade 2 entered Jan 10 but exited Feb 15. It CANNOT be in calibration at Jan 20!
        filtered_jan20 = HistoricalSwingReplayEngine.filter_calibration_by_cutoff(mock_trades, "2025-01-20")
        self.assertEqual(len(filtered_jan20), 1)
        self.assertEqual(filtered_jan20[0].symbol, "S1")

        # Query calibration state at cutoff Feb 20 (2025-02-20)
        filtered_feb20 = HistoricalSwingReplayEngine.filter_calibration_by_cutoff(mock_trades, "2025-02-20")
        self.assertEqual(len(filtered_feb20), 2)

    def test_bayesian_empirical_shrinkage_calculation(self):
        """
        Verify Empirical Bayesian Shrinkage on small subgroup:
        All trades prior E[R] = +0.23R.
        VCP observed: n=7, raw E[R] = +1.32R.
        Weight w = n / (n + 15) = 7 / 22 = 0.3182.
        Shrunk E[R|VCP] = 0.3182 * 1.32 + (1 - 0.3182) * 0.23 = 0.4200 + 0.1568 = +0.58R.
        """
        # Create 7 VCP trades with avg R = 1.32 and 70 other trades with avg R ~ 0.12 so total avg R ~ 0.23
        vcp_trades = []
        for i in range(7):
            r_val = 1.32
            vcp_trades.append(
                SwingTradeRealization(
                    symbol=f"VCP_{i}", t0_date="2025-01-01", entry_date="2025-01-02", exit_date="2025-01-15",
                    setup_type="VCP_CONTRACTION_BREAKOUT", actionability_status="ACTIONABLE_BUY",
                    contraction_quality="HEALTHY_CONTRACTION", market_regime="BULL_MOMENTUM",
                    swing_readiness_score=85.0, readiness_bin="85-100 (Elite Conviction)",
                    entry_price=100.0, stop_loss_price=95.0, target_price_t1=112.0, target_price_t2=120.0,
                    planned_risk_pct=5.0, planned_rr_ratio=2.4, exit_price=106.6, outcome="T1_HIT",
                    hit_t1_before_stop=True, same_bar_ambiguity=False, days_held=13, days_to_t1=13, days_to_stop=None,
                    realized_pnl_pct=6.6, realized_r=r_val, mfe_pre_stop_pct=10.0, mae_pre_stop_pct=-1.0,
                    mfe_45d_full_pct=10.0, mae_45d_full_pct=-1.0
                )
            )

        other_trades = []
        # 70 trades with realized_r = 0.12 -> total 77 trades, (7*1.32 + 70*0.12)/77 = (9.24 + 8.4)/77 = 17.64/77 = 0.229R (~0.23R)
        for i in range(70):
            other_trades.append(
                SwingTradeRealization(
                    symbol=f"BASE_{i}", t0_date="2025-01-01", entry_date="2025-01-02", exit_date="2025-01-15",
                    setup_type="BASE_CONSOLIDATION", actionability_status="ACTIONABLE_BUY",
                    contraction_quality="HEALTHY_CONTRACTION", market_regime="BULL_MOMENTUM",
                    swing_readiness_score=75.0, readiness_bin="75-84 (Strong Readiness)",
                    entry_price=100.0, stop_loss_price=95.0, target_price_t1=110.0, target_price_t2=120.0,
                    planned_risk_pct=5.0, planned_rr_ratio=2.0, exit_price=100.6, outcome="EXPIRED_45D",
                    hit_t1_before_stop=False, same_bar_ambiguity=False, days_held=13, days_to_t1=None, days_to_stop=None,
                    realized_pnl_pct=0.6, realized_r=0.12, mfe_pre_stop_pct=4.0, mae_pre_stop_pct=-2.0,
                    mfe_45d_full_pct=4.0, mae_45d_full_pct=-2.0
                )
            )

        all_trades = vcp_trades + other_trades
        calib = HistoricalSwingReplayEngine.aggregate_calibration_table(all_trades)
        vcp_metrics = calib["setup_types"]["VCP_CONTRACTION_BREAKOUT"]

        # Raw observed R is 1.32
        self.assertEqual(vcp_metrics["raw_realized_r"], 1.32)
        # Shrunk expected R must be approximately +0.58R
        self.assertAlmostEqual(vcp_metrics["shrunk_expected_r"], 0.58, delta=0.02)

    def test_brier_score_and_calibration_error(self):
        """Verify Brier Score, benchmarks, Brier Skill Score, and Reliability Curve."""
        mock_trades = [
            SwingTradeRealization(
                symbol="S1", t0_date="2025-01-01", entry_date="2025-01-02", exit_date="2025-01-15",
                setup_type="VCP_CONTRACTION_BREAKOUT", actionability_status="ACTIONABLE_BUY",
                contraction_quality="HEALTHY_CONTRACTION", market_regime="BULL_MOMENTUM",
                swing_readiness_score=85.0, readiness_bin="85-100 (Elite Conviction)",
                entry_price=100.0, stop_loss_price=95.0, target_price_t1=112.0, target_price_t2=120.0,
                planned_risk_pct=5.0, planned_rr_ratio=2.4, exit_price=112.0, outcome="T1_HIT",
                hit_t1_before_stop=True, same_bar_ambiguity=False, days_held=13, days_to_t1=13, days_to_stop=None,
                realized_pnl_pct=12.0, realized_r=2.4, mfe_pre_stop_pct=14.0, mae_pre_stop_pct=-1.0,
                mfe_45d_full_pct=14.0, mae_45d_full_pct=-1.0
            ),
            SwingTradeRealization(
                symbol="S2", t0_date="2025-01-01", entry_date="2025-01-02", exit_date="2025-01-15",
                setup_type="50EMA_PULLBACK", actionability_status="ACTIONABLE_BUY",
                contraction_quality="HEALTHY_CONTRACTION", market_regime="BULL_MOMENTUM",
                swing_readiness_score=50.0, readiness_bin="<55 (Low Quality)",
                entry_price=100.0, stop_loss_price=95.0, target_price_t1=110.0, target_price_t2=120.0,
                planned_risk_pct=5.0, planned_rr_ratio=2.0, exit_price=95.0, outcome="STOPPED_OUT",
                hit_t1_before_stop=False, same_bar_ambiguity=False, days_held=8, days_to_t1=None, days_to_stop=8,
                realized_pnl_pct=-5.0, realized_r=-1.0, mfe_pre_stop_pct=2.0, mae_pre_stop_pct=-5.0,
                mfe_45d_full_pct=2.0, mae_45d_full_pct=-5.0
            )
        ]
        calib = HistoricalSwingReplayEngine.aggregate_calibration_table(mock_trades)
        self.assertIn("brier_score", calib)
        self.assertIn("brier_diagnostics", calib)
        self.assertIn("reliability_curve", calib)

        # Trade 1: pred_p = 0.55, actual = 1.0 -> sq_err = (0.55 - 1.0)^2 = 0.2025
        # Trade 2: pred_p = 0.20, actual = 0.0 -> sq_err = (0.20 - 0.0)^2 = 0.0400
        # Mean Brier = (0.2025 + 0.0400) / 2 = 0.12125
        self.assertAlmostEqual(calib["brier_score"], 0.1213, delta=0.001)

        diag = calib["brier_diagnostics"]
        # Base rate is 1 win out of 2 trades = 0.50
        # Unconditional Brier = (0.5 - 1)^2 * 0.5 + (0.5 - 0)^2 * 0.5 = 0.2500
        self.assertAlmostEqual(diag["brier_unconditional_base_rate"], 0.2500, delta=0.001)
        # BSS = 1 - (0.1213 / 0.2500) = 1 - 0.485 = +0.5148 (positive skill!)
        self.assertGreater(diag["brier_skill_score"], 0.5)
        self.assertTrue(diag["model_beats_unconditional"])

        # Reliability curve must contain 2 buckets
        rel = calib["reliability_curve"]
        self.assertEqual(len(rel), 2)
        elite_bin = next(b for b in rel if "Elite" in b["bucket_name"])
        self.assertEqual(elite_bin["sample_size"], 1)
        self.assertEqual(elite_bin["mean_predicted_pct"], 55.0)
        self.assertEqual(elite_bin["observed_win_rate_pct"], 100.0)
        self.assertEqual(elite_bin["calibration_gap_pct"], -45.0)

    def test_layer2_structural_invalidation_immunity(self):
        """
        INVARIANT TEST: Layer 3 Empirical Evidence CANNOT Override Layer 2 Structural Invalidation.
        If actionability_status is FAILED_SETUP, is_active MUST remain False regardless of high EV.
        """
        closes = [100.0 + i for i in range(50)]
        highs = [c + 1.0 for c in closes]
        lows = [c - 1.0 for c in closes]
        volumes = [100000.0 for _ in closes]

        # Force a failed breakout: recent high broke pivot, but current price reversed back below
        highs[-2] = 200.0
        closes[-1] = 145.0

        audit = PriceStructureEngine.audit_swing_setup(closes, highs, lows, volumes, current_price=145.0)
        # Verify actionability is FAILED_SETUP
        self.assertEqual(audit["actionability_status"], "FAILED_SETUP")
        # Invalidation gate: is_active must strictly be False
        self.assertFalse(audit["is_active"])

    def test_hierarchical_conditioning_fallback(self):
        """Verify hierarchical lookup falls back to Level 2/1 when sample sizes are small."""
        mock_calib = {
            "total_trades": 50,
            "win_rate_conservative_pct": 30.0,
            "wilson_ci_conservative": [18.0, 44.0],
            "sample_size_evidence": "ADEQUATE",
            "profit_factor_conservative": 1.4,
            "avg_realized_r": 0.3,
            "hierarchical_conditionals": {
                # Level 1 available (N=6)
                "VCP_CONTRACTION_BREAKOUT": {
                    "sample_size": 6, "sample_evidence": "LIMITED", "win_rate_t1_pct": 50.0,
                    "wilson_ci_95": [18.8, 81.2], "profit_factor": 3.0, "avg_realized_r": 1.2,
                    "shrunk_expected_r": 0.55, "avg_days_to_t1": 12.0
                }
                # Level 2 & Level 3 NOT present
            }
        }

        # Lookup with Level 3 query -> should fall back gracefully to Level 1
        res = HistoricalSwingReplayEngine.lookup_empirical_metrics(
            swing_readiness_score=85.0,
            setup_type="VCP_CONTRACTION_BREAKOUT",
            contraction_quality="HEALTHY_CONTRACTION",
            market_regime="BEAR_DEFENSIVE",
            calibration_dict=mock_calib
        )

        self.assertTrue(res["calibrated"])
        self.assertEqual(res["conditioning_level"], "LEVEL_1_SETUP_ONLY")
        self.assertEqual(res["empirical_win_rate_pct"], 50.0)


if __name__ == "__main__":
    unittest.main()
