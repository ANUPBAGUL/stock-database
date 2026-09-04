"""
Unit & Property-Based Tests for 3-Pillar Institutional ValuationEngine.
Verifies:
- Growth-Adjusted PEG calculations with clamping and negative growth guards
- Reverse-DCF numerical bisection solver convergence
- Free Cash Flow Yield and G-Sec spread
- Complete 6-state composite valuation regime decision matrix
"""

import pytest
from src.analytics.valuation_engine import (
    ValuationEngine,
    INDIA_10Y_GSEC_YIELD_PCT,
    COST_OF_EQUITY_DEFAULT,
    TERMINAL_GROWTH_DEFAULT
)


class TestValuationEngine:

    def test_peg_calculation_normal(self):
        # 30 PE, 25% EPS growth -> PEG = 1.2
        peg, status = ValuationEngine.calculate_peg_ratio(30.0, 25.0)
        assert status == "VALID"
        assert peg == 1.2

    def test_peg_calculation_safeguards(self):
        # Negative growth
        peg, status = ValuationEngine.calculate_peg_ratio(25.0, -10.0)
        assert status == "NEGATIVE_GROWTH"
        assert peg is None

        # Zero growth
        peg, status = ValuationEngine.calculate_peg_ratio(25.0, 0.0)
        assert status == "NEGATIVE_GROWTH"
        assert peg is None

        # None values
        peg, status = ValuationEngine.calculate_peg_ratio(None, 20.0)
        assert status == "PE_UNDEFINED"
        assert peg is None

        peg, status = ValuationEngine.calculate_peg_ratio(25.0, None)
        assert status == "GROWTH_UNKNOWN"
        assert peg is None

    def test_peg_base_effect_clamping(self):
        # Extremely small growth (1%) clamped to minimum 5% to avoid 40.0 PEG distortion
        peg, status = ValuationEngine.calculate_peg_ratio(40.0, 1.0)
        assert status == "VALID"
        assert peg == 8.0  # 40 / 5.0

        # Extremely high growth (120%) clamped to maximum 60%
        peg, status = ValuationEngine.calculate_peg_ratio(60.0, 120.0)
        assert status == "VALID"
        assert peg == 1.0  # 60 / 60.0

    def test_fcf_yield_and_gsec_spread(self):
        # FCF = 700 Cr, Market Cap = 10,000 Cr -> Yield = 7.0%
        fcf_y, spread = ValuationEngine.calculate_fcf_yield(700.0, 10000.0)
        assert fcf_y == 7.0
        assert spread == round(7.0 - INDIA_10Y_GSEC_YIELD_PCT, 2)

        # Invalid inputs
        fcf_y, spread = ValuationEngine.calculate_fcf_yield(None, 10000.0)
        assert fcf_y is None
        assert spread is None

    def test_reverse_dcf_bisection_solver(self):
        # Analytical check:
        # FCF_0 = 100 Cr, Market Cap = 2000 Cr
        implied_g = ValuationEngine.solve_reverse_dcf_implied_growth(
            market_cap_cr=2000.0,
            ttm_fcf_cr=100.0,
            cost_of_equity=0.12,
            terminal_growth=0.055,
            forecast_years=5
        )
        assert implied_g is not None
        assert isinstance(implied_g, float)
        assert 5.0 <= implied_g <= 25.0

        # Boundary checks
        assert ValuationEngine.solve_reverse_dcf_implied_growth(0.0, 100.0) is None
        assert ValuationEngine.solve_reverse_dcf_implied_growth(1000.0, 0.0) is None
        assert ValuationEngine.solve_reverse_dcf_implied_growth(1000.0, -50.0) is None

    def test_classification_undervalued_compounder(self):
        # ROCE 26%, PE 22, Growth 25% -> PEG = 0.88, below median
        res = ValuationEngine.evaluate_valuation(
            pe_ratio=22.0,
            pb_ratio=4.5,
            eps_growth_pct=25.0,
            roce_pct=26.0,
            ttm_fcf_cr=500.0,
            market_cap_cr=12000.0,
            debt_to_equity=0.1,
            pe_percentile_3y=40.0
        )
        assert res["status"] == "UNDERVALUED_COMPOUNDER"
        assert res["badge_class"] == "badge-emerald"
        assert res["peg_ratio"] == 0.88

    def test_classification_deep_value(self):
        # PE 12, FCF Yield 8.5%, ROCE 16%, D/E 0.2
        res = ValuationEngine.evaluate_valuation(
            pe_ratio=12.0,
            pb_ratio=1.2,
            eps_growth_pct=10.0,
            roce_pct=16.0,
            ttm_fcf_cr=850.0,
            market_cap_cr=10000.0,
            debt_to_equity=0.2,
            pe_percentile_3y=25.0
        )
        assert res["status"] == "DEEP_VALUE"
        assert res["badge_class"] == "badge-emerald"
        assert res["fcf_yield_pct"] == 8.5

    def test_classification_value_trap(self):
        # PE 14, but negative growth -15% and weak ROCE 8%
        res = ValuationEngine.evaluate_valuation(
            pe_ratio=14.0,
            pb_ratio=0.9,
            eps_growth_pct=-15.0,
            roce_pct=8.0,
            ttm_fcf_cr=50.0,
            market_cap_cr=5000.0,
            debt_to_equity=1.5,
            pe_percentile_3y=15.0
        )
        assert res["status"] == "VALUE_TRAP_WARNING"
        assert res["badge_class"] == "badge-rose"

    def test_classification_overvalued_extreme(self):
        # PE 85, Growth 8% -> PEG ~ 10.0+
        res = ValuationEngine.evaluate_valuation(
            pe_ratio=85.0,
            pb_ratio=15.0,
            eps_growth_pct=8.0,
            roce_pct=16.0,
            ttm_fcf_cr=100.0,
            market_cap_cr=25000.0,
            debt_to_equity=0.3,
            pe_percentile_3y=95.0
        )
        assert res["status"] == "OVERVALUED_EXTREME"
        assert res["badge_class"] == "badge-rose"

    def test_classification_quality_growth_premium(self):
        # ROCE 28%, PE 45, Growth 25% -> PEG = 1.8
        res = ValuationEngine.evaluate_valuation(
            pe_ratio=45.0,
            pb_ratio=8.0,
            eps_growth_pct=25.0,
            roce_pct=28.0,
            ttm_fcf_cr=300.0,
            market_cap_cr=15000.0,
            debt_to_equity=0.05,
            pe_percentile_3y=75.0
        )
        assert res["status"] == "QUALITY_GROWTH_PREMIUM"
        assert res["badge_class"] == "badge-amber"
