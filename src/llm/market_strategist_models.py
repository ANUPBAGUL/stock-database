"""
Pydantic Data Models for Adaptive Market Strategy & Actionable Trade Cards.
Enforces strict typing and zero-hallucination validation invariants.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class MarketRegime(str, Enum):
    BULLISH_EXPANSION = "BULLISH_EXPANSION"
    SELECTIVE_ROTATION = "SELECTIVE_ROTATION"
    DEFENSIVE_CONSOLIDATION = "DEFENSIVE_CONSOLIDATION"
    RISK_OFF_CAPITAL_PRESERVATION = "RISK_OFF_CAPITAL_PRESERVATION"


class HorizonType(str, Enum):
    INTRADAY = "INTRADAY"
    SWING = "SWING"
    LONG_TERM = "LONG_TERM"


class TradingViewFilterPredicate(BaseModel):
    left: str
    operation: str  # 'greater', 'less', 'in_range', 'equal', etc.
    right: Any


class ActionableTradeCard(BaseModel):
    symbol: str
    company_name: str
    sector: str
    industry: Optional[str] = None
    cmp: float
    setup_thesis: str
    
    # Trendlyne-Style DVM Scoring (0 - 100)
    dvm_durability_score: float = Field(ge=0.0, le=100.0)
    dvm_valuation_score: float = Field(ge=0.0, le=100.0)
    dvm_momentum_score: float = Field(ge=0.0, le=100.0)
    dvm_composite_score: float = Field(ge=0.0, le=100.0)
    
    # Execution Bracket
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_reward_ratio: float
    risk_pct: float
    target_1_pct: float
    target_2_pct: float
    position_sizing_verdict: str  # e.g. "FULL_ALLOCATION", "HALF_SIZE"


class AdaptiveStrategyAST(BaseModel):
    """
    Abstract Syntax Tree representing the complete, validated strategy packet
    compiled from market intelligence and optional user tactical intent.
    """
    horizon: HorizonType
    regime: MarketRegime
    tactical_posture: str
    user_intent_evaluated: Optional[str] = None
    
    # Sector Targets & TV Industry Clusters
    favored_sectors: List[str] = Field(default_factory=list)
    excluded_sectors: List[str] = Field(default_factory=list)
    target_tv_industry_clusters: List[str] = Field(default_factory=list)
    
    # Mathematical Corridors (Clamped to Institutional Bounds)
    min_rsi: float = Field(default=50.0, ge=30.0, le=65.0)
    max_rsi: float = Field(default=70.0, ge=60.0, le=80.0)
    min_relative_volume: float = Field(default=1.5, ge=1.0, le=5.0)
    max_debt_to_equity: float = Field(default=1.5, ge=0.0, le=4.0)
    max_pe_ratio: Optional[float] = Field(default=60.0, ge=10.0, le=120.0)
    min_turnover_cr: float = Field(default=5.0, ge=1.0, le=50.0)
    near_52w_high_pct: float = Field(default=6.0, ge=1.0, le=25.0)
    
    # Compiled Predicates for TradingView Scanner
    compiled_tv_predicates: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Executive Grounded CIO Strategy Memo
    cio_memo: Optional[str] = None
