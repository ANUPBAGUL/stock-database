"""
Institutional Test Suite: 5-Pillar Multibagger Discovery & Trajectory Inflection Architecture.

Validates:
1. Pillar 1: Trajectory Inflection & 2nd-Derivative EBITDA Acceleration
2. Pillar 2: Granular Capacity-Constrained TAM / SAM / SOM Funnel
3. Pillar 3: Working Capital & Debtor Days Forensic Sentinel (DSO Acceleration & CFO/EBITDA Traps)
4. Pillar 4: The Expectations Gap (Mauboussin Intrinsic Compounding vs Reverse-DCF Implied CAGR)
5. Pillar 5: Quantitative Price Structure (Weinstein Stage 2, Mansfield RS, VCP Contraction)
6. Synthesis: Hard Circuit Breaker Disqualifications & Multibagger Tier Assignments
"""

import pytest
from src.analytics.working_capital_sentinel import WorkingCapitalSentinel
from src.analytics.expectations_gap_engine import ExpectationsGapEngine
from src.analytics.price_structure_engine import PriceStructureEngine
from src.analytics.granular_tam_engine import GranularTAMEngine
from src.analytics.trajectory_inflection import TrajectoryInflectionEngine


# ==============================================================================
# Pillar 3: Working Capital Forensic Sentinel Tests
# ==============================================================================

def test_working_capital_sentinel_pristine():
    """Validates healthy company with strong CFO conversion and stable DSO."""
    res = WorkingCapitalSentinel.audit_forensic_risk(
        current_receivables_cr=100.0,
        current_revenue_cr=1000.0,
        current_inventories_cr=120.0,
        current_payables_cr=80.0,
        current_cfo_cr=180.0,
        current_ebitda_cr=200.0,
        revenue_growth_yoy_pct=25.0,
        receivables_growth_yoy_pct=20.0,
        dso_history=[38.0, 37.5, 36.5]
    )

    assert res["status"] == "HEALTHY"
    assert res["risk_score"] == 0
    assert not res["is_circuit_breaker_triggered"]
    assert res["dso"] == 36.5
    assert res["cfo_to_ebitda_pct"] == 90.0
    assert res["cfo_conversion_status"] == "EXCELLENT_CASH_CONVERSION"
    assert len(res["red_flags"]) == 0


def test_working_capital_sentinel_debtor_drift_trap():
    """Validates detection of severe debtor days acceleration and CFO shortfall."""
    res = WorkingCapitalSentinel.audit_forensic_risk(
        current_receivables_cr=450.0,
        current_revenue_cr=1000.0,
        current_inventories_cr=250.0,
        current_payables_cr=50.0,
        current_cfo_cr=40.0,
        current_ebitda_cr=200.0,
        revenue_growth_yoy_pct=15.0,
        receivables_growth_yoy_pct=45.0,  # +30% divergence
        dso_history=[90.0, 120.0, 164.25]  # d1=44.25, d2=14.25
    )

    assert res["status"] == "WORKING_CAPITAL_TRAP"
    assert res["is_circuit_breaker_triggered"] is True
    assert res["cfo_conversion_status"] == "SEVERE_EARNINGS_QUALITY_TRAP"
    assert res["cfo_to_ebitda_pct"] == 20.0
    assert len(res["red_flags"]) >= 3


# ==============================================================================
# Pillar 4: The Expectations Gap Engine Tests
# ==============================================================================

def test_expectations_gap_high_asymmetry():
    """Validates high positive expectations gap where intrinsic compounding beats market hurdle."""
    # ROIC = 30%, Reinvestment = 60% -> Base = 18.0%. Market Implied = 8.5%
    res = ExpectationsGapEngine.evaluate_expectations(
        economic_roic_pct=30.0,
        reinvestment_rate_pct=60.0,
        market_implied_growth_5y_pct=8.5,
        operating_leverage_multiplier=0.10
    )

    assert res["status"] == "HIGH_ASYMMETRY_UNDERVALUATION"
    assert res["intrinsic_compounding_rate_pct"] == 19.8  # 18.0 * 1.10
    assert res["expectations_gap_pct"] == 11.3  # 19.8 - 8.5
    assert "Exceptional asymmetry" in res["summary"]


def test_expectations_gap_priced_for_perfection():
    """Validates negative gap when market demands 35% growth but fundamental run-rate is 12%."""
    res = ExpectationsGapEngine.evaluate_expectations(
        economic_roic_pct=20.0,
        reinvestment_rate_pct=60.0,
        market_implied_growth_5y_pct=35.0
    )

    assert res["status"] == "PRICED_FOR_PERFECTION_ASYMMETRIC_RISK"
    assert res["intrinsic_compounding_rate_pct"] == 12.0
    assert res["expectations_gap_pct"] == -23.0


# ==============================================================================
# Pillar 5: Price Structure & Mansfield RS Tests
# ==============================================================================

def test_price_structure_stage2_and_mansfield_rs():
    """Validates Minervini Stage 2 uptrend and positive Mansfield Relative Strength."""
    # Create synthetic daily prices trending upwards over 250 sessions
    base_price = 100.0
    stock_closes = [base_price * (1.0 + 0.003 * i) for i in range(250)]  # Rises to ~175
    nifty_closes = [20000.0 * (1.0 + 0.001 * i) for i in range(250)]    # Outperforming Nifty

    highs = [p * 1.01 for p in stock_closes]
    lows = [p * 0.99 for p in stock_closes]
    volumes = [100000.0 for _ in range(250)]

    res = PriceStructureEngine.audit_price_structure(
        daily_closes=stock_closes,
        benchmark_closes=nifty_closes,
        daily_highs=highs,
        daily_lows=lows,
        daily_volumes=volumes,
        current_price=stock_closes[-1]
    )

    assert res["stage_analysis"]["stage"] == "STAGE_2_UPTREND"
    assert res["stage_analysis"]["is_stage2"] is True
    assert res["stage_analysis"]["sma_200_slope_positive"] is True
    assert res["mansfield_rs"]["score"] > 0.0
    assert res["mansfield_rs"]["status"] in ("STRONG_OUTPERFORMANCE", "POSITIVE_RELATIVE_STRENGTH")
    assert not res["is_stage4_circuit_breaker"]


def test_price_structure_stage4_decline():
    """Validates detection of Stage 4 decline when price breaks below moving averages."""
    # Declining price series
    stock_closes = [200.0 * (1.0 - 0.002 * i) for i in range(250)]  # Drops to ~100
    res = PriceStructureEngine.audit_price_structure(
        daily_closes=stock_closes,
        current_price=stock_closes[-1]
    )

    assert res["stage_analysis"]["stage"] == "STAGE_4_DECLINE"
    assert res["stage_analysis"]["is_stage2"] is False
    assert res["is_stage4_circuit_breaker"] is True


# ==============================================================================
# Pillar 2: Granular TAM & Capacity Engine Tests
# ==============================================================================

def test_granular_tam_capacity_ceiling():
    """Validates physical gross block capacity limits and growth runway."""
    res = GranularTAMEngine.evaluate_tam_capacity_funnel(
        symbol="MANORAMA",
        sector="Specialty Chemicals",
        current_revenue_cr=400.0,
        gross_block_cr=500.0,
        cwip_cr=100.0,
        asset_turnover=2.5,
        revenue_growth_cagr_pct=25.0
    )

    # Total block = 600 Cr * 2.5 = 1,500 Cr Capacity
    assert res["physical_capacity_ceiling_cr"] == 1500.0
    assert res["effective_som_cr"] == 1500.0
    assert res["primary_bottleneck"] == "PHYSICAL_ASSET_CAPACITY"
    assert res["growth_runway_years"] is not None
    assert res["growth_runway_years"] > 4.0
    assert res["confidence_bounds"]["p10_bear"]["som_cr"] == 900.0


# ==============================================================================
# Pillar 1 & Synthesis: Trajectory Inflection & Circuit Breakers
# ==============================================================================

def test_synthesis_tier1_asymmetric_inflection():
    """Validates Tier 1 classification for accelerating company with healthy WC and positive gap."""
    stock_closes = [100.0 * (1.0 + 0.003 * i) for i in range(250)]
    nifty_closes = [20000.0 * (1.0 + 0.001 * i) for i in range(250)]

    res = TrajectoryInflectionEngine.synthesize_5pillar_multibagger_matrix(
        symbol="MANORAMA",
        sector="Specialty Chemicals",
        current_revenue_cr=400.0,
        gross_block_cr=500.0,
        cwip_cr=100.0,
        asset_turnover=2.5,
        ebitda_history=[40.0, 55.0, 78.0],  # d1_prev=15, d1_curr=23 -> d2 = +8 (accelerating)
        margin_history=[18.0, 19.5, 21.0],
        current_receivables_cr=45.0,
        current_inventories_cr=60.0,
        current_payables_cr=35.0,
        current_cfo_cr=70.0,
        current_ebitda_cr=78.0,  # CFO/EBITDA ~ 90%
        revenue_growth_yoy_pct=30.0,
        receivables_growth_yoy_pct=22.0,
        dso_history=[45.0, 42.0, 41.0],
        economic_roic_pct=28.0,
        reinvestment_rate_pct=65.0,
        market_implied_growth_5y_pct=9.5,
        daily_closes=stock_closes,
        benchmark_closes=nifty_closes,
        current_price=stock_closes[-1]
    )

    assert res["tier"] == "TIER_1_ASYMMETRIC_INFLECTION"
    assert res["composite_5pillar_score"] >= 80.0
    assert not res["circuit_breaker_triggered"]
    assert res["pillar_1_inflection"]["acceleration"]["is_accelerating"] is True


def test_synthesis_circuit_breaker_working_capital_trap():
    """Validates hard disqualification when working capital deteriorates, regardless of score."""
    stock_closes = [100.0 * (1.0 + 0.003 * i) for i in range(250)]

    res = TrajectoryInflectionEngine.synthesize_5pillar_multibagger_matrix(
        symbol="TRAP_INC",
        sector="Manufacturing",
        current_revenue_cr=500.0,
        gross_block_cr=200.0,
        cwip_cr=0.0,
        asset_turnover=2.0,
        ebitda_history=[50.0, 70.0, 95.0],
        margin_history=[15.0, 16.0, 17.0],
        current_receivables_cr=350.0,  # DSO = 255 days
        current_inventories_cr=100.0,
        current_payables_cr=30.0,
        current_cfo_cr=10.0,  # Severe shortfall
        current_ebitda_cr=95.0,
        revenue_growth_yoy_pct=20.0,
        receivables_growth_yoy_pct=60.0,
        dso_history=[120.0, 180.0, 255.5],
        economic_roic_pct=25.0,
        reinvestment_rate_pct=50.0,
        market_implied_growth_5y_pct=10.0,
        daily_closes=stock_closes,
        current_price=stock_closes[-1]
    )

    assert res["tier"] == "DISQUALIFIED_BY_CIRCUIT_BREAKER"
    assert res["circuit_breaker_triggered"] is True
    assert "Working Capital Trap" in res["verdict_summary"]
