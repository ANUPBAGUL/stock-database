"""
Historical Swing Setup Replay & Research-Grade Empirical Calibration Engine.

Simulates point-in-time swing trading executions across historical market candles,
tracking forward 45 trading sessions (2-6 weeks / 45-day positional swing horizon).

Architecture:
- Layer 1: Setup Detection (VCP, 52W Breakout, Base Consolidation, 50EMA Pullback, Failed Setup)
- Layer 2: Setup Quality (Normalized ATR & Volume Contraction, Volume Asymmetry, Structural Readiness)
- Layer 3: Empirical Conditional Probability & Uncertainty:
    * Wilson Score 95% Confidence Intervals for binomial probabilities
    * Sample Size Evidence Rating (LOW < 15, MODERATE 15-49, HIGH >= 50) and Data Diversity
    * Multi-horizon MFE/MAE Trajectory Vectors (1D, 3D, 5D, 10D, 20D, 45D)
    * Pre-Stop MFE vs Full-Horizon MFE Isolation
    * Same-Bar Ambiguity Policy (Conservative vs Optimistic vs Ambiguity-Excluded)
    * Hierarchical Conditional Expectancy E[R | X] (Setup x Contraction x Regime)
    * Strict Temporal Invariance (Zero future leakage: Calibration(T0) uses only exits < T0)
- Layer 4: Portfolio Decision (Trade Risk, Position Risk, Portfolio 1% Budget, Regime Sizing)
"""

import os
import math
import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import date, datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from src.db.models import Company, DailyPriceRaw
from src.analytics.price_structure_engine import PriceStructureEngine

logger = logging.getLogger(__name__)

DEFAULT_CALIBRATION_PATH = os.path.join(
    os.path.dirname(__file__), "swing_calibration_data.json"
)


def compute_wilson_confidence_interval(
    successes: int,
    trials: int,
    confidence: float = 0.95
) -> Tuple[float, float]:
    """
    Computes Wilson Score 95% Confidence Interval for a binomial proportion.
    Handles small sample sizes gracefully without degenerating to zero width.
    Returns (ci_low_pct, ci_high_pct) as percentages in [0.0, 100.0].
    """
    if trials <= 0:
        return (0.0, 100.0)

    p_hat = successes / float(trials)
    z = 1.95996  # 95% two-tailed standard normal critical value

    denominator = 1.0 + (z ** 2) / trials
    center_adjusted = p_hat + (z ** 2) / (2.0 * trials)
    spread = z * math.sqrt((p_hat * (1.0 - p_hat) / trials) + ((z ** 2) / (4.0 * (trials ** 2))))

    ci_low = max(0.0, (center_adjusted - spread) / denominator)
    ci_high = min(1.0, (center_adjusted + spread) / denominator)

    return (round(ci_low * 100.0, 1), round(ci_high * 100.0, 1))


def evaluate_sample_evidence_tier(sample_size: int) -> str:
    """
    Evaluates sample size evidence strength.
    Uses neutral evidentiary framing:
    - LIMITED (n < 20): Small subgroup cluster, wide Wilson CI, extreme uncertainty.
    - PRELIMINARY (20 <= n < 150): Modest historical sample, preliminary observations.
    - MODERATE (150 <= n < 400): Substantial sample across multiple market phases.
    - ADEQUATE (n >= 400): Robust statistical sample capable of supporting high empirical confidence.
    """
    if sample_size < 20:
        return "LIMITED"
    elif sample_size < 150:
        return "PRELIMINARY"
    elif sample_size < 400:
        return "MODERATE"
    else:
        return "ADEQUATE"


def evaluate_data_diversity_tier(unique_symbols: int, unique_regimes: int) -> str:
    """Evaluates cross-asset and cross-regime data diversity."""
    if unique_symbols >= 15 and unique_regimes >= 2:
        return "HIGH"
    elif unique_symbols >= 6:
        return "MODERATE"
    else:
        return "LOW"


@dataclass
class SwingSetupEvent:
    """Represents a point-in-time swing candidate detected at session T0."""
    symbol: str
    t0_date: str
    setup_type: str
    actionability_status: str
    contraction_quality: str
    current_price: float
    pivot_entry_price: float
    stop_loss_price: float
    target_price_t1: float
    target_price_t2: float
    planned_risk_pct: float
    planned_rr_ratio: float
    swing_readiness_score: float
    entry_quality_score: float
    tape_confirmation_score: float
    volume_structure_score: float
    atr_contraction_ratio: float
    volume_dryup_ratio: float
    up_down_volume_ratio: float
    distribution_days_count: int
    vol_compression_percentile: float
    market_regime: str


@dataclass
class SwingTradeRealization:
    """
    Represents the empirical forward realization of a triggered swing trade.
    Contains granular MFE/MAE vectors, same-bar ambiguity flags, and exact holding metrics.
    """
    symbol: str
    t0_date: str
    entry_date: str
    exit_date: str
    setup_type: str
    actionability_status: str
    contraction_quality: str
    market_regime: str
    swing_readiness_score: float
    readiness_bin: str
    entry_price: float
    stop_loss_price: float
    target_price_t1: float
    target_price_t2: float
    planned_risk_pct: float
    planned_rr_ratio: float
    exit_price: float
    outcome: str               # T1_HIT, T2_HIT, T1_HIT_TRAILED_OUT, STOPPED_OUT, EXPIRED_45D
    hit_t1_before_stop: bool
    same_bar_ambiguity: bool    # True if both stop and target touched on same bar
    days_held: int
    days_to_t1: Optional[int]
    days_to_stop: Optional[int]
    realized_pnl_pct: float
    realized_r: float
    # Excursion metrics:
    mfe_pre_stop_pct: float     # Maximum Favorable Excursion achieved strictly BEFORE or at exit
    mae_pre_stop_pct: float     # Maximum Adverse Excursion achieved strictly BEFORE or at exit
    mfe_45d_full_pct: float = 0.0
    mae_45d_full_pct: float = 0.0
    mfe_by_horizon: Dict[str, float] = field(default_factory=dict)
    mae_by_horizon: Dict[str, float] = field(default_factory=dict)
    up_down_volume_ratio: float = 1.0
    atr_contraction_ratio: float = 1.0
    volume_dryup_ratio: float = 1.0
    # Conditional R-multiple path metrics
    hit_1r_before_stop: bool = False
    hit_2r_before_stop: bool = False
    hit_3r_before_stop: bool = False
    days_to_1r: Optional[int] = None
    days_to_2r: Optional[int] = None
    days_to_3r: Optional[int] = None
    mae_prior_to_1r_pct: Optional[float] = None


class HistoricalSwingReplayEngine:
    """
    Executes historical point-in-time swing setup discovery, multi-mode forward tracking,
    same-bar ambiguity resolution, and hierarchical conditional calibration.
    """

    HORIZON_KEYS = ["1d", "3d", "5d", "10d", "20d", "45d"]
    HORIZON_DAYS = [1, 3, 5, 10, 20, 45]

    @classmethod
    def replay_candles(
        cls,
        symbol: str,
        candles: List[Dict[str, Any]],
        forward_horizon: int = 45,
        cooldown_days: int = 5,
        lookback_warmup: int = 40,
        benchmark_closes: Optional[List[float]] = None,
        execution_mode: str = "CONSERVATIVE" # CONSERVATIVE (stop first), OPTIMISTIC (target first)
    ) -> List[SwingTradeRealization]:
        """
        Replays a single stock's chronological candle history.
        Evaluates setup conditions strictly at each historical T0 and tracks forward up to forward_horizon sessions.
        """
        if not candles or len(candles) < (lookback_warmup + 10):
            return []

        realizations: List[SwingTradeRealization] = []
        n_candles = len(candles)
        last_exit_idx = -1

        i = lookback_warmup
        while i < n_candles - 5:
            # Enforce cooldown from prior trade in this symbol
            if i <= last_exit_idx + cooldown_days:
                i += 1
                continue

            # 1. Point-in-Time candle slice up to session i (T0)
            sub_closes = [float(c["close"]) for c in candles[:i + 1]]
            sub_highs = [float(c["high"]) for c in candles[:i + 1]]
            sub_lows = [float(c["low"]) for c in candles[:i + 1]]
            sub_vols = [float(c.get("volume", 0)) for c in candles[:i + 1]]
            t0_candle = candles[i]
            t0_date_str = str(t0_candle["date"])
            cmp_t0 = sub_closes[-1]

            sub_bench = benchmark_closes[:i + 1] if benchmark_closes and len(benchmark_closes) >= i + 1 else None

            # 2. Audit swing setup at T0
            audit = PriceStructureEngine.audit_swing_setup(
                daily_closes=sub_closes,
                daily_highs=sub_highs,
                daily_lows=sub_lows,
                daily_volumes=sub_vols,
                current_price=cmp_t0,
                benchmark_closes=sub_bench
            )

            act_status = audit.get("actionability_status", "CONSTRUCTING_BASE")
            setup_type = audit.get("setup_type", "BASE_CONSOLIDATION")
            pivot_entry = audit["pivot_entry_price"]
            stop_loss = audit["stop_loss_price"]
            target_t1 = audit["target_price_t1"]
            target_t2 = audit["target_price_t2"]
            risk_pct = audit["risk_pct"]
            rr_ratio = audit["risk_reward_ratio"]
            readiness_score = audit["swing_readiness_score"]
            contraction_quality = audit.get("contraction_quality", "HEALTHY_CONTRACTION")
            market_regime = audit.get("market_regime", "BULL_MOMENTUM")

            # Layer 2 Invalidation & Risk Gates:
            # - Acceptable structural risk (<= 8.5%)
            # - Organic R:R >= 1.7
            # - Actionable state
            if risk_pct > 8.5 or rr_ratio < 1.7:
                i += 1
                continue

            entry_idx: Optional[int] = None
            entry_price: Optional[float] = None
            entry_date_str: Optional[str] = None

            if act_status == "ACTIONABLE_BUY":
                entry_idx = i
                entry_price = min(cmp_t0, round(pivot_entry * 1.01, 2))
                entry_date_str = t0_date_str

            elif act_status == "TRIGGER_WATCH":
                look_ahead_limit = min(i + 4, n_candles)
                for k in range(i + 1, look_ahead_limit):
                    k_candle = candles[k]
                    k_high = float(k_candle["high"])
                    k_open = float(k_candle["open"])
                    k_low = float(k_candle["low"])

                    if k_low <= stop_loss:
                        break

                    if k_high >= pivot_entry:
                        entry_idx = k
                        entry_price = max(pivot_entry, k_open)
                        entry_date_str = str(k_candle["date"])
                        break

            if entry_idx is None or entry_price is None or entry_date_str is None:
                i += 1
                continue

            # 3. Forward Multi-Horizon Simulation
            sim_res = cls._simulate_forward_trade(
                candles=candles,
                entry_idx=entry_idx,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_t1=target_t1,
                target_t2=target_t2,
                forward_horizon=forward_horizon,
                execution_mode=execution_mode
            )

            exit_idx = sim_res["exit_idx"]
            exit_price = sim_res["exit_price"]
            exit_date_str = str(candles[exit_idx]["date"])
            days_held = max(1, exit_idx - entry_idx)

            realized_pnl_pct = round(((exit_price - entry_price) / entry_price) * 100.0, 2)
            denom_risk = max(0.1, entry_price - stop_loss)
            realized_r = round((exit_price - entry_price) / denom_risk, 2)
            readiness_bin = cls._get_readiness_bin(readiness_score)

            realization = SwingTradeRealization(
                symbol=symbol,
                t0_date=t0_date_str,
                entry_date=entry_date_str,
                exit_date=exit_date_str,
                setup_type=setup_type,
                actionability_status=act_status,
                contraction_quality=contraction_quality,
                market_regime=market_regime,
                swing_readiness_score=readiness_score,
                readiness_bin=readiness_bin,
                entry_price=round(entry_price, 2),
                stop_loss_price=round(stop_loss, 2),
                target_price_t1=round(target_t1, 2),
                target_price_t2=round(target_t2, 2),
                planned_risk_pct=risk_pct,
                planned_rr_ratio=rr_ratio,
                exit_price=round(exit_price, 2),
                outcome=sim_res["outcome"],
                hit_t1_before_stop=sim_res["hit_t1"],
                same_bar_ambiguity=sim_res["same_bar_ambiguity"],
                days_held=days_held,
                days_to_t1=sim_res["days_to_t1"],
                days_to_stop=sim_res["days_to_stop"],
                realized_pnl_pct=realized_pnl_pct,
                realized_r=realized_r,
                mfe_pre_stop_pct=round(sim_res["mfe_pre_stop"], 2),
                mae_pre_stop_pct=round(sim_res["mae_pre_stop"], 2),
                mfe_45d_full_pct=round(sim_res["mfe_45d_full"], 2),
                mae_45d_full_pct=round(sim_res["mae_45d_full"], 2),
                mfe_by_horizon=sim_res["mfe_by_horizon"],
                mae_by_horizon=sim_res["mae_by_horizon"],
                up_down_volume_ratio=audit.get("up_down_volume_ratio", 1.0),
                atr_contraction_ratio=audit.get("atr_contraction_ratio", 1.0),
                volume_dryup_ratio=audit.get("volume_dryup_ratio", 1.0),
                hit_1r_before_stop=sim_res.get("hit_1r", False),
                hit_2r_before_stop=sim_res.get("hit_2r", False),
                hit_3r_before_stop=sim_res.get("hit_3r", False),
                days_to_1r=sim_res.get("days_to_1r"),
                days_to_2r=sim_res.get("days_to_2r"),
                days_to_3r=sim_res.get("days_to_3r"),
                mae_prior_to_1r_pct=sim_res.get("mae_prior_to_1r")
            )

            realizations.append(realization)
            last_exit_idx = exit_idx
            i = exit_idx + 1

        return realizations

    @classmethod
    def _simulate_forward_trade(
        cls,
        candles: List[Dict[str, Any]],
        entry_idx: int,
        entry_price: float,
        stop_loss: float,
        target_t1: float,
        target_t2: float,
        forward_horizon: int = 45,
        execution_mode: str = "CONSERVATIVE"
    ) -> Dict[str, Any]:
        """
        Simulates forward execution session by session from entry session.
        Calculates:
        - Multi-horizon MFE/MAE vectors across 1D, 3D, 5D, 10D, 20D, 45D
        - Strict pre-stop MFE (excursion strictly prior to or at exit session)
        - Full-horizon path MFE
        - Same-bar ambiguity flag and mode handling (CONSERVATIVE vs OPTIMISTIC)
        """
        n_candles = len(candles)
        hit_t1 = False
        days_to_t1 = None
        days_to_stop = None
        active_stop = stop_loss
        same_bar_ambiguity = False

        # Fixed horizon trackers for full path
        mfe_by_horizon = {}
        mae_by_horizon = {}
        running_full_mfe = 0.0
        running_full_mae = 0.0

        # Pre-stop trackers
        mfe_pre_stop = 0.0
        mae_pre_stop = 0.0
        is_exited = False
        exit_idx = entry_idx
        exit_price = entry_price
        outcome = "EXPIRED_45D"

        # Structural R unit and R-multiple path tracking
        r_unit = max(0.01, entry_price - stop_loss)
        target_1r = round(entry_price + 1.0 * r_unit, 2)
        target_2r = round(entry_price + 2.0 * r_unit, 2)
        target_3r = round(entry_price + 3.0 * r_unit, 2)

        hit_1r = False
        hit_2r = False
        hit_3r = False
        days_to_1r = None
        days_to_2r = None
        days_to_3r = None
        mae_prior_to_1r = None

        max_idx = min(entry_idx + forward_horizon, n_candles - 1)

        for d in range(1, forward_horizon + 1):
            curr_idx = entry_idx + d
            if curr_idx >= n_candles:
                break

            c = candles[curr_idx]
            c_high = float(c["high"])
            c_low = float(c["low"])
            c_open = float(c["open"])
            c_close = float(c["close"])

            # 1. Full-horizon Excursions
            cur_fav = ((c_high - entry_price) / entry_price) * 100.0
            cur_adv = ((c_low - entry_price) / entry_price) * 100.0
            running_full_mfe = max(running_full_mfe, cur_fav)
            running_full_mae = min(running_full_mae, cur_adv)

            # Record fixed-horizon snapshots
            for h_days, h_key in zip(cls.HORIZON_DAYS, cls.HORIZON_KEYS):
                if d == h_days:
                    mfe_by_horizon[h_key] = round(running_full_mfe, 2)
                    mae_by_horizon[h_key] = round(running_full_mae, 2)

            # 2. Pre-stop Excursions & Trade Lifecycle
            if not is_exited:
                mfe_pre_stop = max(mfe_pre_stop, cur_fav)
                mae_pre_stop = min(mae_pre_stop, cur_adv)

                # Track progressive R-multiples strictly before exit/stop
                if not hit_1r and c_high >= target_1r:
                    hit_1r = True
                    days_to_1r = d
                    mae_prior_to_1r = round(mae_pre_stop, 2)
                if not hit_2r and c_high >= target_2r:
                    hit_2r = True
                    days_to_2r = d
                if not hit_3r and c_high >= target_3r:
                    hit_3r = True
                    days_to_3r = d

                # Check same-bar ambiguity (both stop and target breached on same candle)
                touches_stop = (c_low <= active_stop)
                touches_t1 = (c_high >= target_t1 and not hit_t1)

                if touches_stop and touches_t1:
                    same_bar_ambiguity = True
                    if execution_mode == "OPTIMISTIC":
                        # Optimistic: Target 1 assumed first
                        hit_t1 = True
                        days_to_t1 = d
                        active_stop = max(active_stop, round(entry_price * 1.002, 2))
                    else:
                        # Conservative (Default): Stop assumed first
                        days_to_stop = d
                        exit_price = min(active_stop, c_open)
                        exit_idx = curr_idx
                        outcome = "STOPPED_OUT"
                        is_exited = True

                elif touches_stop:
                    days_to_stop = d
                    exit_price = min(active_stop, c_open)
                    exit_idx = curr_idx
                    outcome = "T1_HIT_TRAILED_OUT" if hit_t1 else "STOPPED_OUT"
                    is_exited = True

                elif touches_t1:
                    hit_t1 = True
                    days_to_t1 = d
                    active_stop = max(active_stop, round(entry_price * 1.002, 2))

                # Check Target 2 capture (Positional Trend Extension)
                if hit_t1 and c_high >= target_t2 and not is_exited:
                    exit_price = target_t2
                    exit_idx = curr_idx
                    outcome = "T2_HIT"
                    is_exited = True

        # End of forward horizon reached
        if not is_exited:
            end_idx = min(entry_idx + forward_horizon, n_candles - 1)
            exit_idx = end_idx
            exit_price = float(candles[end_idx]["close"])
            outcome = "T1_HIT_EXPIRED_45D" if hit_t1 else "EXPIRED_45D"

        # Fill remaining horizons if horizon exceeded series length
        for h_days, h_key in zip(cls.HORIZON_DAYS, cls.HORIZON_KEYS):
            if h_key not in mfe_by_horizon:
                mfe_by_horizon[h_key] = round(running_full_mfe, 2)
                mae_by_horizon[h_key] = round(running_full_mae, 2)

        return {
            "exit_idx": exit_idx,
            "exit_price": exit_price,
            "outcome": outcome,
            "hit_t1": hit_t1,
            "days_to_t1": days_to_t1,
            "days_to_stop": days_to_stop,
            "same_bar_ambiguity": same_bar_ambiguity,
            "mfe_pre_stop": mfe_pre_stop,
            "mae_pre_stop": mae_pre_stop,
            "mfe_45d_full": running_full_mfe,
            "mae_45d_full": running_full_mae,
            "mfe_by_horizon": mfe_by_horizon,
            "mae_by_horizon": mae_by_horizon,
            "hit_1r": hit_1r,
            "hit_2r": hit_2r,
            "hit_3r": hit_3r,
            "days_to_1r": days_to_1r,
            "days_to_2r": days_to_2r,
            "days_to_3r": days_to_3r,
            "mae_prior_to_1r": mae_prior_to_1r
        }

    @staticmethod
    def _get_readiness_bin(score: float) -> str:
        """Categorizes swing readiness score into decile/quintile bins."""
        if score >= 85.0:
            return "85-100 (Elite Conviction)"
        elif score >= 75.0:
            return "75-84 (Strong Readiness)"
        elif score >= 65.0:
            return "65-74 (Moderate Readiness)"
        elif score >= 55.0:
            return "55-64 (Emerging / Developing)"
        else:
            return "<55 (Low Quality)"

    @classmethod
    def aggregate_calibration_table(
        cls,
        trades: List[SwingTradeRealization],
        optimistic_trades: Optional[List[SwingTradeRealization]] = None
    ) -> Dict[str, Any]:
        """
        Aggregates realized trade outcomes into empirical calibration tables:
        - By Readiness Tier with Wilson 95% Confidence Intervals
        - By Setup Type, Contraction Quality, and Hierarchical Conditionals
        - Dual reporting: Conservative vs Ambiguity-Excluded vs Optimistic
        - Multi-horizon MFE/MAE trajectories
        """
        if not trades:
            return {
                "total_trades": 0,
                "ambiguous_trades_count": 0,
                "overall_win_rate_pct": 0.0,
                "overall_wilson_ci": [0.0, 100.0],
                "sample_size_evidence": "LOW",
                "data_diversity": "LOW",
                "p_1r_before_stop_pct": 0.0,
                "p_2r_before_stop_pct": 0.0,
                "p_3r_before_stop_pct": 0.0,
                "stopped_before_1r_pct": 0.0,
                "readiness_bins": {},
                "setup_types": {},
                "contraction_qualities": {},
                "hierarchical_conditionals": {},
                "mfe_mae_trajectories": {}
            }

        total = len(trades)
        unique_syms = len(set(t.symbol for t in trades))
        unique_regs = len(set(t.market_regime for t in trades))

        sample_evidence = evaluate_sample_evidence_tier(total)
        data_diversity = evaluate_data_diversity_tier(unique_syms, unique_regs)

        # 1. Ambiguity Audit & Dual Win Rates
        ambiguous_trades = [t for t in trades if t.same_bar_ambiguity]
        ambig_count = len(ambiguous_trades)

        wins_conservative = sum(1 for t in trades if t.hit_t1_before_stop)
        win_rate_conservative = round((wins_conservative / total) * 100.0, 1)
        wilson_ci_conservative = compute_wilson_confidence_interval(wins_conservative, total)

        # Ambiguity-excluded subset (removing same-bar touches)
        unambiguous_trades = [t for t in trades if not t.same_bar_ambiguity]
        if unambiguous_trades:
            w_excl = sum(1 for t in unambiguous_trades if t.hit_t1_before_stop)
            win_rate_ambig_excluded = round((w_excl / len(unambiguous_trades)) * 100.0, 1)
            wilson_ci_ambig_excluded = compute_wilson_confidence_interval(w_excl, len(unambiguous_trades))
        else:
            win_rate_ambig_excluded = win_rate_conservative
            wilson_ci_ambig_excluded = wilson_ci_conservative

        # Optimistic expectancy comparison
        if optimistic_trades and len(optimistic_trades) == total:
            w_opt = sum(1 for t in optimistic_trades if t.hit_t1_before_stop)
            win_rate_optimistic = round((w_opt / total) * 100.0, 1)
            pos_opt = sum(t.realized_pnl_pct for t in optimistic_trades if t.realized_pnl_pct > 0)
            neg_opt = abs(sum(t.realized_pnl_pct for t in optimistic_trades if t.realized_pnl_pct < 0))
            pf_optimistic = round(pos_opt / max(0.1, neg_opt), 2)
            avg_r_opt = round(sum(t.realized_r for t in optimistic_trades) / total, 2)
        else:
            win_rate_optimistic = win_rate_conservative
            pf_optimistic = 0.0
            avg_r_opt = 0.0

        pos_pnl = sum(t.realized_pnl_pct for t in trades if t.realized_pnl_pct > 0)
        neg_pnl = abs(sum(t.realized_pnl_pct for t in trades if t.realized_pnl_pct < 0))
        profit_factor = round(pos_pnl / max(0.1, neg_pnl), 2)
        avg_r = round(sum(t.realized_r for t in trades) / total, 2)

        # Execution risk spread
        execution_risk_spread = round(max(0.0, avg_r_opt - avg_r), 2) if avg_r_opt > 0 else 0.0

        # Multi-horizon trajectory averages
        trajectory_summary = {}
        for h_key in cls.HORIZON_KEYS:
            mfes = [t.mfe_by_horizon.get(h_key, 0.0) for t in trades]
            maes = [t.mae_by_horizon.get(h_key, 0.0) for t in trades]
            trajectory_summary[h_key] = {
                "avg_mfe_pct": round(sum(mfes) / total, 1),
                "avg_mae_pct": round(sum(maes) / total, 1)
            }

        def _calc_subset_metrics(subset: List[SwingTradeRealization]) -> Dict[str, Any]:
            if not subset:
                return {}
            n = len(subset)
            w = sum(1 for t in subset if t.hit_t1_before_stop)
            t2 = sum(1 for t in subset if t.outcome == "T2_HIT")
            st = sum(1 for t in subset if "STOPPED_OUT" in t.outcome)
            wr = round((w / n) * 100.0, 1)
            t2_r = round((t2 / n) * 100.0, 1)
            st_r = round((st / n) * 100.0, 1)
            ci = compute_wilson_confidence_interval(w, n)

            pos = sum(t.realized_pnl_pct for t in subset if t.realized_pnl_pct > 0)
            neg = abs(sum(t.realized_pnl_pct for t in subset if t.realized_pnl_pct < 0))
            pf = round(pos / max(0.1, neg), 2)

            r_vals = [t.realized_r for t in subset]
            m_r = round(sum(r_vals) / n, 2)

            win_rs = [t.realized_r for t in subset if t.realized_r > 0]
            loss_rs = [abs(t.realized_r) for t in subset if t.realized_r <= 0]
            avg_win_r = (sum(win_rs) / len(win_rs)) if win_rs else 1.8
            avg_loss_r = (sum(loss_rs) / len(loss_rs)) if loss_rs else 1.0

            p_win = wr / 100.0
            p_loss = 1.0 - p_win
            ev_r = (p_win * avg_win_r) - (p_loss * avg_loss_r)
            ev_score = round(min(100.0, max(10.0, 50.0 + (ev_r * 20.0))), 1)

            w_days = [t.days_to_t1 for t in subset if t.days_to_t1 is not None]
            avg_days = round(sum(w_days) / len(w_days), 1) if w_days else 0.0

            # Bayesian Empirical Shrinkage (Prevents small-sample overconfidence):
            # E[R|X]_shrunk = w * E[R|X]_observed + (1 - w) * E[R|Parent]
            # w = n / (n + k_shrink), with k_shrink = 15.0
            k_shrink = 15.0
            w_shrink = n / (n + k_shrink)
            shrunk_r = round((w_shrink * m_r) + ((1.0 - w_shrink) * avg_r), 2)

            # Distinction between pre-stop MFE and full-horizon MFE
            avg_mfe_pre_stop = round(sum(t.mfe_pre_stop_pct for t in subset) / n, 1)
            avg_mae_pre_stop = round(sum(t.mae_pre_stop_pct for t in subset) / n, 1)
            avg_mfe_45d_full = round(sum(t.mfe_45d_full_pct for t in subset) / n, 1)

            # Conditional path metrics
            p_1r = round((sum(1 for t in subset if t.hit_1r_before_stop) / n) * 100.0, 1)
            p_2r = round((sum(1 for t in subset if t.hit_2r_before_stop) / n) * 100.0, 1)
            p_3r = round((sum(1 for t in subset if t.hit_3r_before_stop) / n) * 100.0, 1)
            stopped_before_1r = round((sum(1 for t in subset if not t.hit_1r_before_stop and 'STOPPED_OUT' in t.outcome) / n) * 100.0, 1)
            days_to_stop_vals = [t.days_to_stop for t in subset if t.days_to_stop is not None]
            avg_days_to_stop = round(sum(days_to_stop_vals) / len(days_to_stop_vals), 1) if days_to_stop_vals else 0.0
            days_to_1r_vals = [t.days_to_1r for t in subset if t.days_to_1r is not None]
            avg_days_to_1r = round(sum(days_to_1r_vals) / len(days_to_1r_vals), 1) if days_to_1r_vals else 0.0
            mae_1r_vals = [t.mae_prior_to_1r_pct for t in subset if t.mae_prior_to_1r_pct is not None]
            avg_mae_prior_to_1r = round(sum(mae_1r_vals) / len(mae_1r_vals), 1) if mae_1r_vals else 0.0

            return {
                "sample_size": n,
                "sample_evidence": evaluate_sample_evidence_tier(n),
                "win_rate_t1_pct": wr,
                "wilson_ci_95": ci,
                "target_t2_rate_pct": t2_r,
                "stop_rate_pct": st_r,
                "p_1r_before_stop_pct": p_1r,
                "p_2r_before_stop_pct": p_2r,
                "p_3r_before_stop_pct": p_3r,
                "stopped_before_1r_pct": stopped_before_1r,
                "avg_days_to_1r": avg_days_to_1r,
                "avg_days_to_stop": avg_days_to_stop,
                "avg_mae_prior_to_1r": avg_mae_prior_to_1r,
                "profit_factor": pf,
                "avg_realized_r": m_r,
                "raw_realized_r": m_r,
                "shrunk_expected_r": shrunk_r,
                "empirical_ev_r": round(ev_r, 2),
                "empirical_ev_score": ev_score,
                "avg_mfe_pre_stop_pct": avg_mfe_pre_stop,
                "avg_mae_pre_stop_pct": avg_mae_pre_stop,
                "avg_mfe_45d_full_pct": avg_mfe_45d_full,
                "avg_days_to_t1": avg_days
            }

        # Bins
        bin_names = [
            "85-100 (Elite Conviction)",
            "75-84 (Strong Readiness)",
            "65-74 (Moderate Readiness)",
            "55-64 (Emerging / Developing)",
            "<55 (Low Quality)"
        ]
        readiness_bins = {}
        for b in bin_names:
            sub = [t for t in trades if t.readiness_bin == b]
            if sub:
                readiness_bins[b] = _calc_subset_metrics(sub)

        # Setup Types
        setup_types = {}
        for st_name in ["VCP_CONTRACTION_BREAKOUT", "50EMA_PULLBACK", "52W_HIGH_BREAKOUT", "BASE_CONSOLIDATION"]:
            sub = [t for t in trades if t.setup_type == st_name]
            if sub:
                setup_types[st_name] = _calc_subset_metrics(sub)

        # Contraction Qualities
        contraction_qualities = {}
        for cq in ["HEALTHY_CONTRACTION", "NEUTRAL_CONTRACTION", "DANGEROUS_CONTRACTION"]:
            sub = [t for t in trades if t.contraction_quality == cq]
            if sub:
                contraction_qualities[cq] = _calc_subset_metrics(sub)

        # Hierarchical Conditionals (Setup x Contraction x Regime)
        hierarchical_conditionals = {}
        for st in ["VCP_CONTRACTION_BREAKOUT", "52W_HIGH_BREAKOUT", "BASE_CONSOLIDATION", "50EMA_PULLBACK"]:
            # Level 1: Setup alone
            st_sub = [t for t in trades if t.setup_type == st]
            if len(st_sub) >= 3:
                hierarchical_conditionals[st] = _calc_subset_metrics(st_sub)

            # Level 2: Setup + Contraction
            for cq in ["HEALTHY_CONTRACTION", "NEUTRAL_CONTRACTION"]:
                st_cq_sub = [t for t in st_sub if t.contraction_quality == cq]
                if len(st_cq_sub) >= 4:
                    hierarchical_conditionals[f"{st}::{cq}"] = _calc_subset_metrics(st_cq_sub)

                # Level 3: Setup + Contraction + Regime
                for reg in ["BULL_MOMENTUM", "BULL_CORRECTION", "BEAR_DEFENSIVE"]:
                    st_cq_reg_sub = [t for t in st_cq_sub if t.market_regime == reg]
                    if len(st_cq_reg_sub) >= 5: # Enforce min hurdle of 5 trades before exposing subgroup
                        hierarchical_conditionals[f"{st}::{cq}::{reg}"] = _calc_subset_metrics(st_cq_reg_sub)

        # Calibration Reliability / Brier Score & Benchmark Diagnostics
        # Evaluates whether the probability model beats naive climatological base rates:
        # Brier = (1/N) * sum((P_pred - Y_actual)^2)
        # Benchmark 1: Unconditional Base Rate (Climatology): P_uncond = wins / total
        # Benchmark 2: Setup-Type Empirical Win Rate
        uncond_base_rate = (wins_conservative / float(total)) if total > 0 else 0.0

        setup_win_rates = {}
        for st_name, st_metrics in setup_types.items():
            setup_win_rates[st_name] = st_metrics.get("win_rate_t1_pct", 0.0) / 100.0

        brier_model_sq_errors = []
        brier_uncond_sq_errors = []
        brier_setup_sq_errors = []

        reliability_buckets = {
            "85-100 (Elite Conviction)": {"pred": 0.55, "preds": [], "actuals": []},
            "75-84 (Strong Readiness)": {"pred": 0.45, "preds": [], "actuals": []},
            "65-74 (Moderate Readiness)": {"pred": 0.35, "preds": [], "actuals": []},
            "55-64 (Developing Quality)": {"pred": 0.30, "preds": [], "actuals": []},
            "<55 (Low Conviction)": {"pred": 0.20, "preds": [], "actuals": []},
        }

        for t in trades:
            actual_y = 1.0 if t.hit_t1_before_stop else 0.0

            if t.swing_readiness_score >= 85:
                pred_p = 0.55
                b_key = "85-100 (Elite Conviction)"
            elif t.swing_readiness_score >= 75:
                pred_p = 0.45
                b_key = "75-84 (Strong Readiness)"
            elif t.swing_readiness_score >= 65:
                pred_p = 0.35
                b_key = "65-74 (Moderate Readiness)"
            elif t.swing_readiness_score >= 55:
                pred_p = 0.30
                b_key = "55-64 (Developing Quality)"
            else:
                pred_p = 0.20
                b_key = "<55 (Low Conviction)"

            reliability_buckets[b_key]["preds"].append(pred_p)
            reliability_buckets[b_key]["actuals"].append(actual_y)

            uncond_p = uncond_base_rate
            setup_p = setup_win_rates.get(t.setup_type, uncond_base_rate)

            brier_model_sq_errors.append((pred_p - actual_y) ** 2)
            brier_uncond_sq_errors.append((uncond_p - actual_y) ** 2)
            brier_setup_sq_errors.append((setup_p - actual_y) ** 2)

        brier_model = round(sum(brier_model_sq_errors) / max(1, total), 4)
        brier_uncond = round(sum(brier_uncond_sq_errors) / max(1, total), 4)
        brier_setup = round(sum(brier_setup_sq_errors) / max(1, total), 4)

        # Brier Skill Score: BSS = 1 - (Brier_model / Brier_unconditional)
        # BSS > 0 means the model beats the naive climatological base rate.
        bss = round(1.0 - (brier_model / max(0.0001, brier_uncond)), 4) if brier_uncond > 0 else 0.0

        # Reliability / Calibration Curve Breakdown
        reliability_curve = []
        for b_name, b_info in reliability_buckets.items():
            n_b = len(b_info["actuals"])
            if n_b > 0:
                mean_pred = round((sum(b_info["preds"]) / n_b) * 100.0, 1)
                obs_win = round((sum(b_info["actuals"]) / n_b) * 100.0, 1)
                gap = round(mean_pred - obs_win, 1) # > 0: overconfident, < 0: underconfident
                reliability_curve.append({
                    "bucket_name": b_name,
                    "sample_size": n_b,
                    "mean_predicted_pct": mean_pred,
                    "observed_win_rate_pct": obs_win,
                    "calibration_gap_pct": gap,
                    "evidence": evaluate_sample_evidence_tier(n_b)
                })

        brier_diagnostics = {
            "brier_model": brier_model,
            "brier_unconditional_base_rate": brier_uncond,
            "brier_setup_type_base_rate": brier_setup,
            "brier_skill_score": bss,
            "brier_skill_score_pct": round(bss * 100.0, 2),
            "model_beats_unconditional": brier_model < brier_uncond,
            "model_beats_setup_base_rate": brier_model < brier_setup
        }

        return {
            "total_trades": total,
            "unique_symbols": unique_syms,
            "overall_evidence": "PRELIMINARY",
            "sample_size_evidence": sample_evidence,
            "data_diversity": data_diversity,
            "ambiguous_trades_count": ambig_count,
            "win_rate_conservative_pct": win_rate_conservative,
            "wilson_ci_conservative": wilson_ci_conservative,
            "win_rate_ambig_excluded_pct": win_rate_ambig_excluded,
            "wilson_ci_ambig_excluded": wilson_ci_ambig_excluded,
            "win_rate_optimistic_pct": win_rate_optimistic,
            "profit_factor_conservative": profit_factor,
            "profit_factor_optimistic": pf_optimistic,
            "avg_realized_r": avg_r,
            "execution_risk_spread_r": execution_risk_spread,
            "brier_score": brier_model,
            "brier_diagnostics": brier_diagnostics,
            "reliability_curve": reliability_curve,
            "overall_avg_mfe_pre_stop_pct": round(sum(t.mfe_pre_stop_pct for t in trades) / total, 1),
            "overall_avg_mae_pre_stop_pct": round(sum(t.mae_pre_stop_pct for t in trades) / total, 1),
            "overall_avg_mfe_45d_full_pct": round(sum(t.mfe_45d_full_pct for t in trades) / total, 1),
            "p_1r_before_stop_pct": round((sum(1 for t in trades if t.hit_1r_before_stop) / total) * 100.0, 1),
            "p_2r_before_stop_pct": round((sum(1 for t in trades if t.hit_2r_before_stop) / total) * 100.0, 1),
            "p_3r_before_stop_pct": round((sum(1 for t in trades if t.hit_3r_before_stop) / total) * 100.0, 1),
            "stopped_before_1r_pct": round((sum(1 for t in trades if not t.hit_1r_before_stop and 'STOPPED_OUT' in t.outcome) / total) * 100.0, 1),
            "mfe_mae_trajectories": trajectory_summary,
            "readiness_bins": readiness_bins,
            "setup_types": setup_types,
            "contraction_qualities": contraction_qualities,
            "hierarchical_conditionals": hierarchical_conditionals,
            "calibrated_at": datetime.now().isoformat()
        }

    @classmethod
    def filter_calibration_by_cutoff(
        cls,
        trades: List[SwingTradeRealization],
        cutoff_date: str
    ) -> List[SwingTradeRealization]:
        """
        STRICT TEMPORAL INVARIANCE FILTER:
        Ensures Calibration(T0) contains ONLY trades whose realization exit_date < cutoff_date.
        Completely eliminates lookahead bias and circular leakage.
        """
        return [t for t in trades if t.exit_date < cutoff_date]

    @classmethod
    def run_universe_replay(
        cls,
        db: Session,
        forward_horizon: int = 45,
        min_candles: int = 90,
        symbols: Optional[List[str]] = None,
        cutoff_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes point-in-time swing replay across all companies in the database.
        Runs both Conservative and Optimistic passes to compute execution risk spread.
        """
        q = db.query(Company)
        if symbols:
            q = q.filter(Company.nse_symbol.in_([s.upper() for s in symbols]))
        companies = q.all()

        conservative_trades: List[SwingTradeRealization] = []
        optimistic_trades: List[SwingTradeRealization] = []
        symbols_evaluated = 0

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

            if len(price_rows) < min_candles:
                continue

            symbols_evaluated += 1
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

            # Mode A: Conservative (Default, stop first)
            comp_cons = cls.replay_candles(
                symbol=sym,
                candles=candles,
                forward_horizon=forward_horizon,
                execution_mode="CONSERVATIVE"
            )
            conservative_trades.extend(comp_cons)

            # Mode B: Optimistic (Target first)
            comp_opt = cls.replay_candles(
                symbol=sym,
                candles=candles,
                forward_horizon=forward_horizon,
                execution_mode="OPTIMISTIC"
            )
            optimistic_trades.extend(comp_opt)

        if cutoff_date:
            conservative_trades = cls.filter_calibration_by_cutoff(conservative_trades, cutoff_date)
            optimistic_trades = cls.filter_calibration_by_cutoff(optimistic_trades, cutoff_date)

        calib = cls.aggregate_calibration_table(conservative_trades, optimistic_trades)
        calib["symbols_evaluated"] = symbols_evaluated
        calib["forward_horizon_days"] = forward_horizon

        cls.save_calibration(calib)

        return {
            "calibration": calib,
            "trades_count": len(conservative_trades),
            "trades_sample": [asdict(t) for t in conservative_trades[:25]]
        }

    @classmethod
    def save_calibration(
        cls,
        calibration_dict: Dict[str, Any],
        filepath: Optional[str] = None
    ) -> str:
        """Saves calibration statistics to persistent JSON."""
        target_path = filepath or DEFAULT_CALIBRATION_PATH
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(calibration_dict, f, indent=2, default=str)
        return target_path

    @classmethod
    def load_calibration(
        cls,
        filepath: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Loads cached calibration statistics if available."""
        target_path = filepath or DEFAULT_CALIBRATION_PATH
        if not os.path.exists(target_path):
            return None
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load swing calibration from {target_path}: {e}")
            return None

    @classmethod
    def lookup_empirical_metrics(
        cls,
        swing_readiness_score: float,
        setup_type: str = "VCP_CONTRACTION_BREAKOUT",
        contraction_quality: str = "HEALTHY_CONTRACTION",
        market_regime: str = "BULL_MOMENTUM",
        calibration_dict: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fast hierarchical lookup of empirical probabilities, Wilson CIs, and E[R | X].
        Hierarchy:
          Level 3: Setup + Contraction + Regime (if n >= 5)
          Level 2: Setup + Contraction (if n >= 4)
          Level 1: Setup alone (if n >= 3)
          Fallback: Readiness Tier or Universe Baseline
        """
        calib = calibration_dict or cls.load_calibration()
        if not calib or calib.get("total_trades", 0) < 5:
            return {
                "empirical_win_rate_pct": 50.0,
                "wilson_ci_95": [25.0, 75.0],
                "sample_size_evidence": "LOW",
                "empirical_profit_factor": 1.5,
                "empirical_avg_r": 0.8,
                "empirical_sample_size": 0,
                "empirical_avg_days_to_target": 15.0,
                "conditioning_level": "PRIOR_UNTESTED",
                "calibrated": False
            }

        hier = calib.get("hierarchical_conditionals", {})

        # Level 3: Setup x Contraction x Regime
        k3 = f"{setup_type}::{contraction_quality}::{market_regime}"
        if k3 in hier and hier[k3].get("sample_size", 0) >= 5:
            m = hier[k3]
            shrunk = m.get("shrunk_expected_r", m["avg_realized_r"])
            return {
                "empirical_win_rate_pct": m["win_rate_t1_pct"],
                "wilson_ci_95": m["wilson_ci_95"],
                "sample_size_evidence": m.get("sample_evidence", "LIMITED"),
                "empirical_profit_factor": m["profit_factor"],
                "empirical_avg_r": shrunk,
                "expected_r_multiple": shrunk,
                "raw_realized_r": m["avg_realized_r"],
                "empirical_sample_size": m["sample_size"],
                "empirical_avg_days_to_target": m["avg_days_to_t1"],
                "avg_mfe_pre_stop_pct": m.get("avg_mfe_pre_stop_pct", 0.0),
                "conditioning_level": "LEVEL_3_SETUP_CONTRACTION_REGIME",
                "calibrated": True
            }

        # Level 2: Setup x Contraction
        k2 = f"{setup_type}::{contraction_quality}"
        if k2 in hier and hier[k2].get("sample_size", 0) >= 4:
            m = hier[k2]
            shrunk = m.get("shrunk_expected_r", m["avg_realized_r"])
            return {
                "empirical_win_rate_pct": m["win_rate_t1_pct"],
                "wilson_ci_95": m["wilson_ci_95"],
                "sample_size_evidence": m.get("sample_evidence", "LIMITED"),
                "empirical_profit_factor": m["profit_factor"],
                "empirical_avg_r": shrunk,
                "expected_r_multiple": shrunk,
                "raw_realized_r": m["avg_realized_r"],
                "empirical_sample_size": m["sample_size"],
                "empirical_avg_days_to_target": m["avg_days_to_t1"],
                "avg_mfe_pre_stop_pct": m.get("avg_mfe_pre_stop_pct", 0.0),
                "conditioning_level": "LEVEL_2_SETUP_CONTRACTION",
                "calibrated": True
            }

        # Level 1: Setup alone
        if setup_type in hier and hier[setup_type].get("sample_size", 0) >= 3:
            m = hier[setup_type]
            shrunk = m.get("shrunk_expected_r", m["avg_realized_r"])
            return {
                "empirical_win_rate_pct": m["win_rate_t1_pct"],
                "wilson_ci_95": m["wilson_ci_95"],
                "sample_size_evidence": m.get("sample_evidence", "LIMITED"),
                "empirical_profit_factor": m["profit_factor"],
                "empirical_avg_r": shrunk,
                "expected_r_multiple": shrunk,
                "raw_realized_r": m["avg_realized_r"],
                "empirical_sample_size": m["sample_size"],
                "empirical_avg_days_to_target": m["avg_days_to_t1"],
                "avg_mfe_pre_stop_pct": m.get("avg_mfe_pre_stop_pct", 0.0),
                "conditioning_level": "LEVEL_1_SETUP_ONLY",
                "calibrated": True
            }

        # Fallback: Readiness Tier
        bin_name = cls._get_readiness_bin(swing_readiness_score)
        bin_metrics = calib.get("readiness_bins", {}).get(bin_name)
        if bin_metrics and bin_metrics.get("sample_size", 0) >= 3:
            shrunk = bin_metrics.get("shrunk_expected_r", bin_metrics["avg_realized_r"])
            return {
                "empirical_win_rate_pct": bin_metrics["win_rate_t1_pct"],
                "wilson_ci_95": bin_metrics["wilson_ci_95"],
                "sample_size_evidence": bin_metrics.get("sample_evidence", "LIMITED"),
                "empirical_profit_factor": bin_metrics["profit_factor"],
                "empirical_avg_r": shrunk,
                "expected_r_multiple": shrunk,
                "raw_realized_r": bin_metrics["avg_realized_r"],
                "empirical_sample_size": bin_metrics["sample_size"],
                "empirical_avg_days_to_target": bin_metrics["avg_days_to_t1"],
                "avg_mfe_pre_stop_pct": bin_metrics.get("avg_mfe_pre_stop_pct", 0.0),
                "conditioning_level": "FALLBACK_READINESS_TIER",
                "calibrated": True
            }

        # Universe Baseline Fallback
        return {
            "empirical_win_rate_pct": calib.get("win_rate_conservative_pct", 50.0),
            "wilson_ci_95": calib.get("wilson_ci_conservative", [20.0, 80.0]),
            "sample_size_evidence": calib.get("sample_size_evidence", "LIMITED"),
            "empirical_profit_factor": calib.get("profit_factor_conservative", 1.3),
            "empirical_avg_r": calib.get("avg_realized_r", 0.5),
            "expected_r_multiple": calib.get("avg_realized_r", 0.5),
            "raw_realized_r": calib.get("avg_realized_r", 0.5),
            "empirical_sample_size": calib.get("total_trades", 0),
            "empirical_avg_days_to_target": 14.5,
            "avg_mfe_pre_stop_pct": calib.get("overall_avg_mfe_pre_stop_pct", 0.0),
            "conditioning_level": "FALLBACK_UNIVERSE_AGGREGATE",
            "calibrated": True
        }
