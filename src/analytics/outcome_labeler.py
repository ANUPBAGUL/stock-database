"""
Rich Outcome Labeler & Multibagger Ground Truth Generator.

Analyzes the full daily price path post-T0.
Calculates:
- Realized milestone prices & dates: (2x, 5x, 10x)
- Days to milestone: days_to_2x, days_to_5x, days_to_10x
- Path volatility: max_drawdown_before_2x, max_drawdown_before_5x
- Multi-horizon returns (1D to 756D)
- Daily path trajectory vector
- Automated trigger for FailureAnalyzer post-mortem diagnostics
"""

import logging
from datetime import date, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from src.db.models import DecisionSnapshot, ForwardOutcome, DailyPriceRaw, CorporateAction
from src.analytics.price_adjuster import PriceAdjuster
from src.analytics.failure_analyzer import FailureAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OutcomeLabeler:
    """
    Evaluates historical decision snapshots and persists rich path outcomes & labels.
    """

    @classmethod
    def evaluate_snapshot_outcome(
        cls,
        db: Session,
        snapshot: DecisionSnapshot,
        as_of_date: Optional[date] = None,
        market_cap_at_t0: Optional[float] = None
    ) -> Optional[ForwardOutcome]:
        """
        Calculates complete forward price trajectory and labels for a specific DecisionSnapshot.
        """
        t0_dt = snapshot.decision_timestamp.date()
        today = as_of_date or date.today()

        # Fetch split-adjusted prices from t0 onwards
        prices = PriceAdjuster.get_adjusted_prices(
            db=db,
            company_id=snapshot.company_id,
            start_date=t0_dt,
            end_date=today
        )

        if not prices:
            logger.warning(f"No prices found for company {snapshot.company_id} from {t0_dt} onwards.")
            return None

        t0_price = prices[0]["adj_close"]
        if t0_price <= 0:
            return None

        # Price horizon mappings (index positions in trading days)
        def _get_price_at_index(idx: int) -> Optional[float]:
            if idx < len(prices):
                return round(prices[idx]["adj_close"], 2)
            return None

        p_1d = _get_price_at_index(1)
        p_5d = _get_price_at_index(5)
        p_20d = _get_price_at_index(20)
        p_60d = _get_price_at_index(60)
        p_120d = _get_price_at_index(120)
        p_252d = _get_price_at_index(252)
        p_504d = _get_price_at_index(504)
        p_756d = _get_price_at_index(756)

        # Milestone and path calculations
        max_price = t0_price
        min_price = t0_price
        
        price_2x, date_2x, days_2x = None, None, None
        price_5x, date_5x, days_5x = None, None, None
        price_10x, date_10x, days_10x = None, None, None
        
        min_before_2x = t0_price
        min_before_5x = t0_price
        running_peak = t0_price
        peak_to_trough_dd = 0.0
        
        daily_path = []

        for idx, p in enumerate(prices):
            adj_p = p["adj_close"]
            dt = p.get("trading_date") or p.get("date")
            
            if adj_p > max_price:
                max_price = adj_p
            if adj_p < min_price:
                min_price = adj_p

            if adj_p > running_peak:
                running_peak = adj_p
            
            curr_dd = ((adj_p - running_peak) / running_peak) * 100.0
            if curr_dd < peak_to_trough_dd:
                peak_to_trough_dd = curr_dd

            ratio = adj_p / t0_price
            
            # 2x milestone
            if ratio >= 2.0 and days_2x is None:
                days_2x = idx
                price_2x = round(adj_p, 2)
                date_2x = dt
            elif days_2x is None:
                if adj_p < min_before_2x:
                    min_before_2x = adj_p

            # 5x milestone
            if ratio >= 5.0 and days_5x is None:
                days_5x = idx
                price_5x = round(adj_p, 2)
                date_5x = dt
            elif days_5x is None:
                if adj_p < min_before_5x:
                    min_before_5x = adj_p

            # 10x milestone
            if ratio >= 10.0 and days_10x is None:
                days_10x = idx
                price_10x = round(adj_p, 2)
                date_10x = dt

            dd_from_t0 = round(((adj_p - t0_price) / t0_price) * 100.0, 2)
            if idx <= 252: # Sample daily path for the first year
                daily_path.append({
                    "day": idx,
                    "date": dt.isoformat(),
                    "adj_close": round(adj_p, 2),
                    "return_pct": dd_from_t0
                })

        max_return_pct = round(((max_price - t0_price) / t0_price) * 100.0, 2)
        overall_drawdown_pct = round(peak_to_trough_dd, 2)
        dd_before_2x_pct = round(((min_before_2x - t0_price) / t0_price) * 100.0, 2)
        dd_before_5x_pct = round(((min_before_5x - t0_price) / t0_price) * 100.0, 2)

        is_2x = (days_2x is not None)
        is_5x = (days_5x is not None)
        is_10x = (days_10x is not None)
        is_failure = (overall_drawdown_pct <= -50.0) and not is_2x

        # Persist or update ForwardOutcome record
        outcome = db.query(ForwardOutcome).filter_by(snapshot_id=snapshot.snapshot_id).first()
        if not outcome:
            outcome = ForwardOutcome(
                snapshot_id=snapshot.snapshot_id,
                company_id=snapshot.company_id,
                t0_date=t0_dt,
                t0_price=t0_price,
                market_cap_at_t0_cr=market_cap_at_t0,
                price_at_2x=price_2x,
                date_2x=date_2x,
                days_to_2x=days_2x,
                price_at_5x=price_5x,
                date_5x=date_5x,
                days_to_5x=days_5x,
                price_at_10x=price_10x,
                date_10x=date_10x,
                days_to_10x=days_10x,
                price_t_1d=p_1d,
                price_t_5d=p_5d,
                price_t_20d=p_20d,
                price_t_60d=p_60d,
                price_t_120d=p_120d,
                price_t_252d=p_252d,
                price_t_504d=p_504d,
                price_t_756d=p_756d,
                maximum_run_pct=max_return_pct,
                max_drawdown_before_2x=dd_before_2x_pct,
                max_drawdown_before_5x=dd_before_5x_pct,
                max_forward_return_pct=max_return_pct,
                max_drawdown_pct=overall_drawdown_pct,
                daily_path_payload={"trajectory": daily_path},
                is_multibagger_2x=is_2x,
                is_multibagger_5x=is_5x,
                is_multibagger_10x=is_10x,
                is_failure=is_failure
            )
            db.add(outcome)
        else:
            outcome.price_at_2x = price_2x
            outcome.date_2x = date_2x
            outcome.days_to_2x = days_2x
            outcome.price_at_5x = price_5x
            outcome.date_5x = date_5x
            outcome.days_to_5x = days_5x
            outcome.price_at_10x = price_10x
            outcome.date_10x = date_10x
            outcome.days_to_10x = days_10x
            outcome.price_t_1d = p_1d
            outcome.price_t_5d = p_5d
            outcome.price_t_20d = p_20d
            outcome.price_t_60d = p_60d
            outcome.price_t_120d = p_120d
            outcome.price_t_252d = p_252d
            outcome.price_t_504d = p_504d
            outcome.price_t_756d = p_756d
            outcome.maximum_run_pct = max_return_pct
            outcome.max_drawdown_before_2x = dd_before_2x_pct
            outcome.max_drawdown_before_5x = dd_before_5x_pct
            outcome.max_forward_return_pct = max_return_pct
            outcome.max_drawdown_pct = overall_drawdown_pct
            outcome.daily_path_payload = {"trajectory": daily_path}
            outcome.is_multibagger_2x = is_2x
            outcome.is_multibagger_5x = is_5x
            outcome.is_multibagger_10x = is_10x
            outcome.is_failure = is_failure

        db.commit()

        # Trigger failure post-mortem diagnostics if candidate
        if is_failure or (outcome.max_drawdown_pct and outcome.max_drawdown_pct <= -40.0):
            FailureAnalyzer.diagnose_snapshot_failure(
                db=db,
                snapshot=snapshot,
                outcome=outcome,
                as_of_date=today
            )

        logger.info(f"[Outcome Labeler] Updated rich forward outcome {outcome.outcome_id} (2x={is_2x}, 5x={is_5x}, 10x={is_10x}, MaxReturn={max_return_pct}%, DD_before_2x={dd_before_2x_pct}%).")
        return outcome
