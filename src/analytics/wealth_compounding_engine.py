"""
Total Shareholder Wealth Compounding & Terminal Economic Realization Engine.
Replaces naive additive returns with institutional wealth path compounding:
W_{t+1} = W_t * (1 + r_t^price) + D_t^cash + C_t^corporate
or for total-return reinvested series:
W_{t+1} = W_t * (1 + r_t^total) where r_t^total = r_t^price + r_t^distribution + r_t^corporate
R_T = (W_T / W_0) - 1.

Crucially: Bankruptcy/Delisting is an event state, not automatically hardcoded to -100%.
The engine models actual terminal shareholder recovery.
"""
from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Dict, Any

@dataclass
class CorporateCashDistribution:
    distribution_date: date
    dividend_per_share: float = 0.0
    special_cash_dividend: float = 0.0
    liquidation_cash_recovery: float = 0.0
    corporate_action_proceeds: float = 0.0 # From spin-offs, tender offers, restructuring

@dataclass
class TerminalEventRecord:
    event_date: date
    event_type: str # '10X', 'BANKRUPTCY', 'DELISTING', 'ACQUISITION', 'LIQUIDATION', 'MERGED'
    status: str # 'ACTIVE', 'SUSPENDED', 'DELISTED', 'BANKRUPTCY', 'LIQUIDATION', 'MERGED', 'ACQUIRED'
    terminal_equity_value_per_share: float = 0.0 # Residual equity value after restructuring
    cash_recovery_per_share: float = 0.0 # Insolvency resolution / liquidation recovery
    corporate_consideration_per_share: float = 0.0 # Consideration in new shares/merger
    notes: Optional[str] = None


class WealthCompoundingEngine:
    """
    Computes true total shareholder return path and terminal economic recovery.
    """

    @staticmethod
    def compute_compounded_wealth(
        initial_wealth: float,
        price_series: List[Dict[str, Any]], # [{'date': d, 'close': p, 'dividend': d, 'corporate_proceeds': c}]
        reinvest_distributions: bool = True
    ) -> Dict[str, Any]:
        """
        Compounds shareholder wealth over a historical price and corporate distribution trajectory.
        """
        if not price_series:
            return {
                "wealth_start": initial_wealth,
                "wealth_end": initial_wealth,
                "total_return_pct": 0.0,
                "total_dividends": 0.0,
                "total_proceeds": 0.0,
                "trajectory": []
            }

        w_current = float(initial_wealth)
        initial_price = float(price_series[0]["close"])
        if initial_price <= 0:
            initial_price = 1.0

        shares_held = initial_wealth / initial_price
        cash_accumulated = 0.0
        total_dividends = 0.0
        total_proceeds = 0.0
        trajectory = []

        for i in range(len(price_series)):
            pt = price_series[i]
            p_close = float(pt["close"])
            div_ps = float(pt.get("dividend", 0.0))
            corp_ps = float(pt.get("corporate_proceeds", 0.0))

            div_total = div_ps * shares_held
            corp_total = corp_ps * shares_held
            total_dividends += div_total
            total_proceeds += corp_total

            if reinvest_distributions and p_close > 0:
                # Buy additional fractional shares at close
                additional_shares = (div_total + corp_total) / p_close
                shares_held += additional_shares
                equity_val = shares_held * p_close
                w_current = equity_val
            else:
                cash_accumulated += (div_total + corp_total)
                w_current = (shares_held * p_close) + cash_accumulated

            trajectory.append({
                "date": pt["date"],
                "shares_held": round(shares_held, 6),
                "wealth": round(w_current, 4),
                "cash_accumulated": round(cash_accumulated, 4)
            })

        total_return_pct = ((w_current - initial_wealth) / initial_wealth) * 100.0

        return {
            "wealth_start": initial_wealth,
            "wealth_end": round(w_current, 4),
            "total_return_pct": round(total_return_pct, 4),
            "total_dividends": round(total_dividends, 4),
            "total_proceeds": round(total_proceeds, 4),
            "trajectory": trajectory
        }

    @staticmethod
    def compute_terminal_economic_recovery(
        initial_price_at_t0: float,
        last_traded_price: float,
        terminal_event: TerminalEventRecord
    ) -> Dict[str, Any]:
        """
        Reconstructs the actual economic recovery of a shareholder upon terminal corporate events
        (e.g. Insolvency, CIRP resolution, delisting, merger).

        Avoids the dangerous naive assumption of 'bankruptcy = -100% loss'.
        """
        if initial_price_at_t0 <= 0:
            initial_price_at_t0 = 1.0

        total_recovery_per_share = (
            terminal_event.terminal_equity_value_per_share +
            terminal_event.cash_recovery_per_share +
            terminal_event.corporate_consideration_per_share
        )

        # If zero recovery confirmed, terminal return is indeed -100%
        # If partial recovery exists (e.g. Rs 2 per share recovered), return is (2 - P0)/P0
        terminal_return_pct = ((total_recovery_per_share - initial_price_at_t0) / initial_price_at_t0) * 100.0

        return {
            "initial_price_t0": initial_price_at_t0,
            "last_traded_price": last_traded_price,
            "event_date": terminal_event.event_date,
            "event_type": terminal_event.event_type,
            "status": terminal_event.status,
            "terminal_equity_value": terminal_event.terminal_equity_value_per_share,
            "cash_recovery": terminal_event.cash_recovery_per_share,
            "corporate_consideration": terminal_event.corporate_consideration_per_share,
            "total_recovery_per_share": round(total_recovery_per_share, 4),
            "terminal_return_pct": round(terminal_return_pct, 4),
            "is_total_loss": total_recovery_per_share == 0.0
        }
