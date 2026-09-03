"""
Economic ROIC & Incremental ROIIC Engine (Mauboussin / Counterpoint Global Framework).
Distinguishes Accounting ROCE from True Economic ROIC and computes multi-year
Return on Incremental Invested Capital (ROIIC) with denominator threshold safeguards.
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class EconomicROICEngine:
    """
    Computes Economic Return on Invested Capital (ROIC), Invested Capital,
    and 3-Year Rolling Incremental ROIIC (ΔNOPAT / ΔInvested Capital).
    """

    @staticmethod
    def calculate_economic_roic(
        ebit_cr: float,
        tax_rate_pct: float,
        net_worth_cr: float,
        borrowings_cr: float,
        cash_and_equivalents_cr: float = 0.0,
        fixed_assets_cr: Optional[float] = None,
        working_capital_cr: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Computes Economic ROIC and Invested Capital for a single period.
        
        Invested Capital (Operating Approach) = Net Fixed Assets + Net Working Capital
        Invested Capital (Financing Approach) = Net Worth + Total Debt - Excess Cash
        """
        tax_rate = max(0.0, min(0.40, tax_rate_pct / 100.0 if tax_rate_pct > 1.0 else tax_rate_pct))
        nopat = round(ebit_cr * (1.0 - tax_rate), 2)

        # Invested Capital derivation
        if fixed_assets_cr is not None and working_capital_cr is not None:
            invested_capital = max(1.0, fixed_assets_cr + working_capital_cr)
            ic_methodology = "OPERATING_ASSETS"
        else:
            invested_capital = max(1.0, (net_worth_cr + borrowings_cr) - cash_and_equivalents_cr)
            ic_methodology = "FINANCING_CAPITAL_NET_OF_CASH"

        economic_roic_pct = round((nopat / invested_capital) * 100.0, 2)

        return {
            "nopat_cr": nopat,
            "invested_capital_cr": round(invested_capital, 2),
            "economic_roic_pct": economic_roic_pct,
            "ic_methodology": ic_methodology,
            "tax_rate_used_pct": round(tax_rate * 100.0, 1),
        }

    @staticmethod
    def calculate_rolling_incremental_roiic(
        history_periods: List[Dict[str, Any]],
        lookback_quarters: int = 12,  # 3-Year Rolling Window
        min_ic_delta_pct: float = 0.05, # Minimum 5% change in IC to avoid small denominator explosion
    ) -> Dict[str, Any]:
        """
        Computes 3-Year Rolling Incremental Return on Invested Capital (ROIIC):
        ROIIC = (NOPAT_t - NOPAT_t-n) / (Invested_Capital_t - Invested_Capital_t-n)
        
        Includes denominator safeguards to prevent infinity/division-by-zero on asset-light quarters.
        """
        if not history_periods or len(history_periods) < 2:
            return {
                "rolling_roiic_pct": None,
                "roiic_status": "INSUFFICIENT_HISTORY",
                "delta_nopat_cr": 0.0,
                "delta_ic_cr": 0.0,
                "lookback_quarters_used": 0,
            }

        # Sort history ascending by period/date
        periods = sorted(history_periods, key=lambda x: x.get("period_end_date", ""))
        current = periods[-1]

        # Select lookback target (3 years / 12 quarters or maximum available)
        idx_lookback = max(0, len(periods) - 1 - lookback_quarters)
        baseline = periods[idx_lookback]

        curr_nopat = current.get("nopat_cr", 0.0)
        base_nopat = baseline.get("nopat_cr", 0.0)
        curr_ic = current.get("invested_capital_cr", 1.0)
        base_ic = baseline.get("invested_capital_cr", 1.0)

        delta_nopat = curr_nopat - base_nopat
        delta_ic = curr_ic - base_ic

        # Denominator threshold safeguard
        min_ic_threshold = max(5.0, base_ic * min_ic_delta_pct)
        if abs(delta_ic) < min_ic_threshold:
            # Asset-light expansion or capital unchanged: ROIIC not meaningful via formula
            return {
                "rolling_roiic_pct": None,
                "roiic_status": "CAPITAL_UNCHANGED_ASSET_LIGHT",
                "delta_nopat_cr": round(delta_nopat, 2),
                "delta_ic_cr": round(delta_ic, 2),
                "lookback_quarters_used": len(periods) - 1 - idx_lookback,
            }

        rolling_roiic = round((delta_nopat / delta_ic) * 100.0, 2)

        # Classify economic quality of incremental deployment
        curr_roic = current.get("economic_roic_pct", 0.0)
        if rolling_roiic > curr_roic and rolling_roiic > 20.0:
            quality = "ACCELERATING_CAPITAL_EFFICIENCY"
        elif rolling_roiic >= 15.0:
            quality = "HEALTHY_COMPOUNDER"
        elif rolling_roiic > 0.0:
            quality = "DILUTIVE_GROWTH"
        else:
            quality = "VALUE_DESTRUCTION"

        return {
            "rolling_roiic_pct": rolling_roiic,
            "roiic_status": quality,
            "delta_nopat_cr": round(delta_nopat, 2),
            "delta_ic_cr": round(delta_ic, 2),
            "lookback_quarters_used": len(periods) - 1 - idx_lookback,
        }

    @staticmethod
    def calculate_roic_trajectory_momentum(
        history_periods: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluates the first derivative of Economic ROIC across 1-year and 2-year windows.
        Example: 18% -> 24% -> 31% is an early multibagger rerating signature.
        """
        if not history_periods or len(history_periods) < 2:
            return {
                "roic_1y_delta_pct": 0.0,
                "roic_2y_delta_pct": 0.0,
                "trajectory_profile": "FLAT_OR_INSUFFICIENT_DATA"
            }

        periods = sorted(history_periods, key=lambda x: x.get("period_end_date", ""))
        curr_roic = periods[-1].get("economic_roic_pct", 0.0)

        # 1-Year (4 quarters ago)
        idx_1y = max(0, len(periods) - 1 - 4)
        roic_1y_ago = periods[idx_1y].get("economic_roic_pct", curr_roic)
        delta_1y = round(curr_roic - roic_1y_ago, 2)

        # 2-Year (8 quarters ago)
        idx_2y = max(0, len(periods) - 1 - 8)
        roic_2y_ago = periods[idx_2y].get("economic_roic_pct", curr_roic)
        delta_2y = round(curr_roic - roic_2y_ago, 2)

        if delta_1y >= 5.0 and delta_2y >= 8.0:
            profile = "POWERFUL_ROIC_EXPANSION"
        elif delta_1y > 1.5:
            profile = "STEADY_ROIC_IMPROVEMENT"
        elif delta_1y < -3.0:
            profile = "DETERIORATING_CAPITAL_EFFICIENCY"
        else:
            profile = "STABLE_PLATEAU"

        return {
            "current_roic_pct": curr_roic,
            "roic_1y_delta_pct": delta_1y,
            "roic_2y_delta_pct": delta_2y,
            "trajectory_profile": profile
        }
