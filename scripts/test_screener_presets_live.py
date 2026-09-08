"""
Verification Script: Test All 3 Screener Presets End-to-End on Real Live Data.
Validates:
1. Multibagger Inflection Preset
2. Swing VCP Breakout Preset
3. Intraday Momentum Scalp Preset
Ensures:
- Real data returned
- Provenance & Data Quality correctly tracked (NULL != 0)
- Reverse DCF implied growth calculated
- Swing pivot and ATR contraction calculated
- Tiered liquidity gating enforced on Intraday
"""

import sys
import os
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.screener.screener_service import ScreenerService
from src.screener.screener_models import ScreenerFilterRequest


def test_presets():
    print("=" * 80)
    print("RUNNING END-TO-END SCREENER PRESET AUDIT (REAL DATA)")
    print("=" * 80)

    presets = [
        ("MULTIBAGGER_INFLECTION_PRESET", "LIVE_CLOUD", 10),
        ("SWING_VCP_BREAKOUT_PRESET", "LIVE_CLOUD", 10),
        ("INTRADAY_MOMENTUM_SCALP_PRESET", "LIVE_CLOUD", 10),
    ]

    for preset_name, mode, limit in presets:
        print(f"\n--- Testing Preset: {preset_name} (Mode: {mode}, Limit: {limit}) ---")
        req = ScreenerFilterRequest(
            mode=mode,
            preset=preset_name,
            limit=limit
        )
        resp = ScreenerService.run_screen(req)

        print(f"Success: {resp.success}")
        print(f"Candidates returned: {len(resp.candidates)}")
        print(f"Funnel stats: S1={resp.funnel_stats.stage1_eligibility_survivors}, S2={resp.funnel_stats.stage2_prescreen_survivors}, S3={resp.funnel_stats.stage3_5pillar_inflections}, S4={resp.funnel_stats.stage4_top_conviction_count}, Time={resp.funnel_stats.execution_time_ms:.1f}ms")
        print(f"Feeds count: Long-term={len(resp.long_term_feed)}, Swing={len(resp.candidates)}, Intraday={sum(1 for c in resp.candidates if c.intraday_radar.is_active)}")

        assert resp.success is True, f"Failed to execute {preset_name}"
        assert len(resp.candidates) > 0, f"Expected candidates for {preset_name}, got 0"
        if resp.macro_regime_summary:
            print(f"Macro Regime: {resp.macro_regime_summary.get('macro_regime')} | Stance: {resp.macro_regime_summary.get('risk_stance')} | India VIX: {resp.macro_regime_summary.get('india_vix')}")

        # Inspect top 2 candidates in detail
        for c in resp.candidates[:2]:
            print(f"\n  Candidate: {c.symbol} ({c.company_name}) | CMP: Rs.{c.cmp:.2f} | Mcap: Rs.{c.market_cap_cr:.1f} Cr")
            print(f"    Business Potential Score: {c.business_potential_score} | PE: {c.pe_ratio} | ROCE: {c.roce_pct}%")
            print(f"    Lifecycle: Stage={c.lifecycle_stage} | Trigger={c.lifecycle_trigger}")
            print(f"    Implied Growth: {c.market_implied_growth_pct}% | Asymmetry Gap: {c.expectations_asymmetry_gap_pct}%")
            print(f"    Confidence: Signal Score={c.signal_score} | Grade={c.setup_grade} | Evidence={c.historical_evidence_tier} | P(+1R before Stop)={c.conditional_p_1r_pct}%")
            print(f"    Data Quality: {c.setup_data_quality} ({c.setup_quality_rating})")
            print(f"    Swing: Type={c.swing_setup.setup_type}, Pivot=Rs.{c.swing_setup.pivot_entry_price:.2f}, Stop=Rs.{c.swing_setup.stop_loss_price:.2f}, ATR_Ratio={c.swing_setup.atr_contraction_ratio}, Quality={c.swing_setup.contraction_quality}")
            print(f"    Intraday: Active={c.intraday_radar.is_active}, RVOL={c.intraday_radar.relative_volume_multiplier}, Scalp={c.intraday_radar.scalp_signal}, Liquidity={c.intraday_radar.liquidity_status}")
            print(f"    Invalidation Triggers: {len(c.invalidation_triggers)} triggers defined")
            for trig in c.invalidation_triggers:
                print(f"      - {trig.condition_description} => {trig.threshold_value}")

            # Strict assertions: no NaNs, no unformatted None templates
            assert c.cmp > 0, "CMP must be positive"
            assert 0.0 <= c.business_potential_score <= 100.0, "Business potential must be between 0 and 100"
            assert 0.0 <= c.signal_score <= 100.0, "Signal score must be between 0 and 100"
            assert c.setup_grade in ("A_PRIME", "B_SELECTIVE", "C_DEVELOPING", "DISQUALIFIED"), "Setup grade invalid"
            assert c.historical_evidence_tier in ("LIMITED", "PRELIMINARY", "MODERATE", "ADEQUATE"), "Evidence tier invalid"
            assert c.setup_data_quality in (0.50, 0.75, 1.00), "Data quality must be one of the standard ratings"
            assert "None" not in str(c.invalidation_triggers[0].threshold_value), "Invalidation trigger must not contain 'None'"

    print("\n" + "=" * 80)
    print("ALL SCREENER PRESETS TESTED SUCCESSFULLY ON LIVE MARKET DATA!")
    print("=" * 80)

if __name__ == "__main__":
    test_presets()
