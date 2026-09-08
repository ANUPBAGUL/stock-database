"""
Screener Request, Response, and Intelligence Card Models.
"""

from typing import Dict, Any, List, Optional
from datetime import date, datetime
from pydantic import BaseModel, Field


class ScreenerFilterRequest(BaseModel):
    """
    On-demand screening filter payload.
    """
    mode: str = Field(default="LIVE_CLOUD", description="LIVE_CLOUD or LOCAL_DB")
    preset: Optional[str] = Field(default=None, description="Preset name (e.g. MULTIBAGGER_INFLECTION_PRESET)")
    
    # Fundamental Criteria
    min_market_cap_cr: float = Field(default=250.0, description="Minimum Market Capitalization in ₹ Crores")
    max_market_cap_cr: Optional[float] = Field(default=None, description="Optional Maximum Market Cap (for Microcap screens)")
    min_roce_pct: float = Field(default=15.0, description="Minimum Return on Capital Employed (%)")
    min_sales_growth_3y_pct: float = Field(default=12.0, description="Minimum 3-Year Sales Growth (%)")
    min_pat_growth_3y_pct: float = Field(default=12.0, description="Minimum 3-Year PAT Growth (%)")
    max_debt_to_equity: float = Field(default=1.2, description="Maximum Debt/Equity Multiple")
    max_pe_ratio: Optional[float] = Field(default=None, description="Maximum P/E Multiple")
    min_cfo_to_pat_ratio: float = Field(default=0.70, description="Minimum Cash Flow Conversion (CFO/PAT)")
    max_promoter_pledge_pct: float = Field(default=15.0, description="Maximum Promoter Pledge %")
    
    # Technical & Momentum Criteria
    near_52w_high_pct: float = Field(default=35.0, description="Maximum distance from 52-Week High (%)")
    min_rs_rating: float = Field(default=60.0, description="Minimum Mansfield Relative Strength Rating (0-100)")
    require_stage_2_uptrend: bool = Field(default=True, description="Require Price > 50 EMA and 50 EMA > 200 EMA")
    min_daily_turnover_cr: float = Field(default=0.50, description="Minimum Daily Traded Turnover in ₹ Crores")
    
    # Execution options
    deep_5pillar_analysis: bool = Field(default=True, description="Run full 5-Pillar deep analysis on surviving candidates")
    limit: int = Field(default=30, description="Maximum candidates to return")


class InvalidationTrigger(BaseModel):
    trigger_id: str
    condition_description: str
    threshold_value: str
    severity: str = "CRITICAL"


class SwingSetupCard(BaseModel):
    is_active: bool = False
    setup_type: str = "VCP_CONTRACTION_BREAKOUT" # VCP_CONTRACTION_BREAKOUT, 50EMA_PULLBACK, 52W_HIGH_BREAKOUT, BASE_CONSOLIDATION
    pivot_entry_price: float = 0.0
    raw_pivot_price: float = 0.0
    adjusted_pivot_entry: float = 0.0
    adaptive_pivot_buffer: float = 0.0
    wick_rejection_detected: bool = False
    upper_wick_ratio: float = 0.0
    has_micro_handle: bool = False
    handle_quality: str = "INSUFFICIENT_DATA"
    handle_tightness_ratio: float = 1.0
    stop_loss_price: float = 0.0
    structural_stop_reason: str = ""              # e.g., "Contraction Trough Support", "50-Day EMA Baseline"
    risk_pct: float = 0.0                         # Structural distance to stop %
    suggested_position_size_pct: float = 10.0     # Recommended position allocation based on 1% portfolio risk budget
    tranche_1_probe_pct: float = 50.0
    tranche_1_trigger_price: float = 0.0
    tranche_2_pyramid_pct: float = 50.0
    tranche_2_trigger_price: float = 0.0
    breakeven_milestone_price: float = 0.0
    target_price: float = 0.0                     # Primary target (for backwards compatibility)
    target_price_t1: float = 0.0                  # Target 1 (Conservative Base Measured Move / 52W High)
    target_price_t2: float = 0.0                  # Target 2 (Extended 30-45 Day Trend Extension)
    risk_reward_ratio: float = 0.0                # Structural R:R based on T1
    expected_value_score: float = 0.0             # Probability-weighted EV index (0-100)
    timeframe: str = "2-6 Weeks (Positional Swing)"
    # Normalized Volatility & Volume Contraction Components
    atr_10d: float = 0.0
    atr_30d: float = 0.0
    atr_20d: float = 0.0                          # Preserved for backward compatibility
    atr_contraction_ratio: float = 1.0            # ATR10 / ATR30 (< 0.70 signifies tightening)
    volatility_contraction_delta_pct: float = 0.0 # (ATR10 / ATR30 - 1) * 100
    volume_5d_avg: float = 0.0
    volume_40d_avg: float = 0.0
    volume_dryup_ratio: float = 1.0               # Vol5 / Vol40 (< 0.70 signifies institutional dry-up)
    volume_dryup_delta_pct: float = 0.0           # (Vol5 / Vol40 - 1) * 100
    # Up/Down Accumulation Signature
    up_down_volume_ratio: float = 1.0             # Buying vs Selling volume over 20 sessions
    up_days_count: int = 10
    down_days_count: int = 10
    # Actionability & Regimes
    pivot_distance_pct: float = 0.0               # CMP distance from pivot (+% = above breakout, -% = below)
    actionability_status: str = "CONSTRUCTING_BASE" # CONSTRUCTING_BASE, TRIGGER_WATCH, ACTIONABLE_BUY, LATE_BUY_ZONE, EXTENDED, FAILED_SETUP
    contraction_quality: str = "HEALTHY_CONTRACTION" # HEALTHY_CONTRACTION, NEUTRAL_CONTRACTION, DANGEROUS_CONTRACTION
    vol_compression_percentile: float = 50.0      # Historical percentile of ATR10/ATR30 in 120-day window
    distribution_days_count: int = 0              # Trailing 20-session high-volume down days
    closing_range_location_pct: float = 50.0      # % location of close within high-low range (accumulation check)
    market_regime: str = "BULL_MOMENTUM"          # BULL_MOMENTUM, BULL_CORRECTION, BEAR_DEFENSIVE
    trailing_stop_guide: str = "10 EMA (Momentum) / 20 EMA (Positional)"
    sector_relative_strength: str = "NEUTRAL"     # LEADING, OUTPERFORMING, NEUTRAL, LAGGING
    # Empirical Calibration & Historical Replay Outcomes (Layer 3)
    empirical_win_rate_pct: float = 0.0           # Historical P(T1 before Stop Loss) from point-in-time replay
    wilson_ci_low_pct: float = 0.0                # Wilson Score 95% Confidence Interval Lower Bound
    wilson_ci_high_pct: float = 0.0               # Wilson Score 95% Confidence Interval Upper Bound
    sample_size_evidence: str = "LIMITED"         # Evidentiary sample size rating: LIMITED (n<15), MODERATE (15-49), ADEQUATE (n>=50)
    data_diversity: str = "LOW"                   # Cross-symbol and cross-regime diversity: LOW, MODERATE, HIGH
    empirical_profit_factor: float = 0.0          # Historical profit factor (Gross Gains / Gross Losses)
    empirical_avg_r: float = 0.0                  # Average realized R multiple per trade
    expected_r_multiple: float = 0.0              # E[R | X] conditional expected return
    empirical_sample_size: int = 0                # Number of historical setups in this calibration bin
    empirical_avg_days_to_target: float = 0.0     # Average trading sessions to reach Target 1
    mfe_pre_stop_avg_pct: float = 0.0             # Pre-stop average Maximum Favorable Excursion %
    execution_risk_spread_r: float = 0.0          # Ambiguity spread (Optimistic Expectancy - Conservative Expectancy)
    # Conditional R-multiple path metrics
    conditional_p_1r_pct: float = 0.0             # Empirical probability P(+1R before Stop)
    conditional_p_2r_pct: float = 0.0             # Empirical probability P(+2R before Stop)
    stopped_before_1r_pct: float = 0.0            # Empirical probability of stop before +1R
    setup_grade: str = "C_DEVELOPING"             # A_PRIME, B_SELECTIVE, C_DEVELOPING, DISQUALIFIED
    # Portfolio Risk Budgeting (Layer 4)
    trade_risk_pct: float = 0.0                   # Structural trade risk (|Entry - Stop| / Entry) %
    portfolio_risk_budget_pct: float = 1.0        # Strict 1.0% account equity risk budget
    status_notes: str = ""
    broker_order_ticket: Optional[Dict[str, Any]] = None # Pre-calculated 1-Click Zerodha/Upstox Execution Ticket


class IntradayRadarCard(BaseModel):
    is_active: bool = False
    relative_volume_multiplier: float = 1.0 # Current volume vs 20-DMA
    vwap_proximity_pct: float = 0.0
    atr_range_expansion_pct: float = 0.0
    scalp_signal: str = "NEUTRAL" # LONG_MOMENTUM_BREAKOUT, OPENING_RANGE_SURGE, NEUTRAL
    liquidity_status: str = "SUFFICIENT"
    gap_pct: float = 0.0
    gap_character: str = "FLAT_OPEN_SURGE" # GAP_AND_GO, FLAT_OPEN_SURGE, EXHAUSTION_GAP_WARNING
    session_phase: str = "OPENING_RANGE_WINDOW" # OPENING_RANGE_WINDOW, MIDDAY_CHOP_ZONE, AFTERNOON_TREND_RUN
    broker_order_ticket: Optional[Dict[str, Any]] = None # Pre-calculated 1-Click Zerodha/Upstox Execution Ticket


class ScreenerCandidateResult(BaseModel):
    """
    Complete Institutional Intelligence Card for a Screened Candidate with Decoupled 4-Vector Matrix.
    """
    symbol: str
    company_name: str
    cmp: float
    market_cap_cr: float
    pe_ratio: Optional[float] = None
    roce_pct: Optional[float] = None
    debt_to_equity: Optional[float] = None
    
    # 4 Decoupled Orthogonal Vectors (Mauboussin / Institutional Matrix)
    business_potential_score: float = 0.0      # Score A: Long-term business quality & compounding runway (0-100)
    expectations_asymmetry_gap_pct: float = 0.0 # Score B: Reverse DCF market expectations gap (%)
    tape_confirmation_score: float = 0.0       # Score C: Mansfield RS & Weinstein Stage 2 trend (0-100)
    entry_quality_score: float = 0.0           # Score D: Immediate VCP tightness & ATR Risk/Reward setup (0-100)
    thesis_category: str = "STRATEGIC_WATCHLIST" # CONVICTION_BUY, STRATEGIC_WATCHLIST, SWING_SETUP, INTRADAY_SCALP
    
    # Strategic Watchlist Graduation Telemetry (10/10 Upgrade)
    graduation_status: Optional[str] = None    # GRADUATION_IMMIGRATION_READY, ADVANCING_BASE_BUILDER, EARLY_STAGE_INCUBATION
    graduation_readiness_pct: float = 0.0      # 0 - 100% readiness to graduate to CONVICTION_BUY
    graduation_trigger: str = ""               # Specific catalyst: VCP_TIGHTNESS_GRADUATION, 50EMA_ACCUMULATION_GRADUATION, etc.
    graduation_target_pivot: Optional[float] = None # Key price level for capital deployment

    # Confidence Decomposition (Phase 5)
    signal_score: float = 0.0                  # Decoupled mathematical strength (0-100)
    historical_evidence_tier: str = "LIMITED"  # LIMITED (n<20), PRELIMINARY (20<=n<150), MODERATE (150<=n<400), ADEQUATE (n>=400)
    setup_grade: str = "C_DEVELOPING"          # A_PRIME, B_SELECTIVE, C_DEVELOPING, DISQUALIFIED
    conditional_p_1r_pct: float = 0.0          # Empirical probability P(+1R before stop)

    # 5-Pillar Scores (0-100)
    multibagger_conviction_score: float = 0.0
    economic_inflection_p1: float = 0.0
    reinvestment_runway_p2: float = 0.0
    working_capital_p3: float = 0.0
    expectations_gap_p4: float = 0.0
    price_structure_p5: float = 0.0
    
    # Reverse DCF & Expectations
    market_implied_growth_pct: Optional[float] = None
    sustainable_compounding_ceiling_pct: Optional[float] = None
    expectations_asymmetry_pct: Optional[float] = None
    
    # Statistically Honest Likelihood & Asymmetry Index
    m7_asymmetry_index: float = 0.0            # Composite M7 Asymmetry Score (0-100)
    multibagger_likelihood_rank: str = "HIGH"  # CONVICTION, HIGH, MEDIUM, EMERGING
    prob_2x_3y_pct: float = 0.0                # Model Estimated Likelihood Index (0-100)
    prob_5x_5y_pct: float = 0.0                # Model Estimated Likelihood Index (0-100)
    prob_10x_5y_pct: float = 0.0               # Model Estimated Likelihood Index (0-100)
    failure_risk_rating: str = "LOW"
    
    # Multi-Horizon Feeds
    long_term_verdict: str = "WATCHLIST"
    swing_setup: SwingSetupCard = Field(default_factory=SwingSetupCard)
    intraday_radar: IntradayRadarCard = Field(default_factory=IntradayRadarCard)
    
    # Data Quality & Provenance (Phase 0.5)
    setup_data_quality: float = 0.75
    setup_quality_rating: str = "CLOUD_PROXY"
    metric_provenance: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    
    # Lifecycle & Structural Stage
    lifecycle_stage: Optional[str] = None
    lifecycle_trigger: Optional[str] = None

    # Falsification Triggers
    invalidation_triggers: List[InvalidationTrigger] = Field(default_factory=list)

    # On-Demand LLM Dossier & Institutional Memo
    llm_dossier_available: bool = True
    llm_analysis: Optional[Dict[str, Any]] = None


class FunnelAttritionStats(BaseModel):
    total_universe_screened: int = 5200
    stage1_eligibility_survivors: int = 2450
    stage1_attrition_pct: float = 52.88
    stage2_prescreen_survivors: int = 380
    stage2_attrition_pct: float = 84.49
    stage3_5pillar_inflections: int = 62
    stage3_attrition_pct: float = 83.68
    stage4_top_conviction_count: int = 18
    stage4_attrition_pct: float = 70.97
    execution_time_ms: float = 0.0


class ScreenerResponse(BaseModel):
    success: bool = True
    mode: str = "LIVE_CLOUD"
    preset_used: Optional[str] = None
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    funnel_stats: FunnelAttritionStats = Field(default_factory=FunnelAttritionStats)
    macro_regime_summary: Optional[Dict[str, Any]] = None
    candidates: List[ScreenerCandidateResult] = Field(default_factory=list)
    long_term_feed: List[ScreenerCandidateResult] = Field(default_factory=list)
    strategic_watchlist_feed: List[ScreenerCandidateResult] = Field(default_factory=list)
    swing_feed: List[ScreenerCandidateResult] = Field(default_factory=list)
    intraday_feed: List[ScreenerCandidateResult] = Field(default_factory=list)
    error_message: Optional[str] = None
