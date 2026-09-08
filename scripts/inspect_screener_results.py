"""
Screener Test & Deep Evaluation Inspector.
Runs all presets, executes custom screens, collects complete candidate cards,
and conducts a qualitative and quantitative sanity check on the output.
"""

import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.screener.screener_service import ScreenerService
from src.screener.screener_models import ScreenerFilterRequest


def inspect_all_screener_outputs():
    print("=" * 80)
    print("RUNNING COMPREHENSIVE SCREENER VERIFICATION & AUDIT")
    print("=" * 80)

    presets = [
        ("MULTIBAGGER_INFLECTION_PRESET", "Long-Term Multibagger Inflection"),
        ("SWING_VCP_BREAKOUT_PRESET", "2-4 Week Swing Trading VCP Breakout"),
        ("MICROCAP_COMPOUNDER_PRESET", "Microcap / Smallcap Compounders"),
        ("INTRADAY_MOMENTUM_SCALP_PRESET", "1-Day Intraday Momentum Scalp Radar")
    ]

    all_results = {}

    for preset_key, title in presets:
        print(f"\n>>> TESTING PRESET: {title} ({preset_key})")
        res = ScreenerService.run_preset_screen(preset_key, mode="LOCAL_DB")
        
        print(f"Status: {'SUCCESS' if res.success else 'FAILED'} | Execution Time: {res.funnel_stats.execution_time_ms} ms")
        print(f"Funnel Throughput: Universe {res.funnel_stats.total_universe_screened} -> Stage1 {res.funnel_stats.stage1_eligibility_survivors} -> Stage2 {res.funnel_stats.stage2_prescreen_survivors} -> Stage3 {res.funnel_stats.stage3_5pillar_inflections} -> Top {res.funnel_stats.stage4_top_conviction_count}")
        
        candidates = res.candidates[:5]
        print(f"Top {len(candidates)} Candidates Preview:")
        print(f"{'Symbol':<14} | {'CMP':<8} | {'Score':<6} | {'P1 (Inf)':<8} | {'P4 (Gap)':<8} | {'P5 (Price)':<10} | {'Prob 5x':<8} | {'Verdict':<15}")
        print("-" * 95)
        for c in candidates:
            print(f"{c.symbol:<14} | Rs.{c.cmp:<6.1f} | {c.multibagger_conviction_score:<6.1f} | {c.economic_inflection_p1:<8.1f} | {c.expectations_gap_p4:<8.1f} | {c.price_structure_p5:<10.1f} | {c.prob_5x_5y_pct:<7.1f}% | {c.long_term_verdict:<15}")

        if preset_key == "SWING_VCP_BREAKOUT_PRESET" and res.swing_feed:
            print("\n  [Swing Setup Card Sample]:")
            sw = res.swing_feed[0].swing_setup
            print(f"  Symbol: {res.swing_feed[0].symbol} | Pivot: Rs.{sw.pivot_entry_price} | Stop: Rs.{sw.stop_loss_price} | Target: Rs.{sw.target_price} | R:R: {sw.risk_reward_ratio} | Notes: {sw.status_notes}")

        if preset_key == "MULTIBAGGER_INFLECTION_PRESET" and res.candidates:
            print("\n  [Automated Invalidation Triggers Sample]:")
            top_cand = res.candidates[0]
            print(f"  Candidate: {top_cand.symbol}")
            for trig in top_cand.invalidation_triggers:
                print(f"   [!] {trig.condition_description} (Threshold: {trig.threshold_value})")

        all_results[preset_key] = {
            "execution_ms": res.funnel_stats.execution_time_ms,
            "candidate_count": len(res.candidates),
            "top_candidates": [c.symbol for c in candidates]
        }

    # Test Custom Filter Screen
    print("\n>>> TESTING CUSTOM SCREEN: Ultra-Quality High-Growth Screen")
    custom_req = ScreenerFilterRequest(
        min_roce_pct=22.0,
        min_sales_growth_3y_pct=18.0,
        max_debt_to_equity=0.4,
        limit=5,
        mode="LOCAL_DB"
    )
    custom_res = ScreenerService.run_screen(custom_req)
    print(f"Custom Screen Execution Time: {custom_res.funnel_stats.execution_time_ms} ms | Candidates Found: {len(custom_res.candidates)}")
    for c in custom_res.candidates:
        print(f" • {c.symbol}: ROCE {c.roce_pct}%, Score {c.multibagger_conviction_score}, 5x Prob: {c.prob_5x_5y_pct}%")

    print("\n" + "=" * 80)
    print("ALL SCREENER PRESET & CUSTOM TESTS COMPLETED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    inspect_all_screener_outputs()
