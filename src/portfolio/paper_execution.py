"""
Paper Execution & Implementation Shortfall Simulator.

Tracks realistic paper order routing, arrival price vs execution price slippage,
market impact modeling, statutory friction, and implementation shortfall auditing.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from src.portfolio.transaction_costs import TransactionCostCalculator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PaperExecutionEngine:
    """
    Simulates institutional trade execution and calculates implementation shortfall.
    """

    @staticmethod
    def simulate_order_execution(
        symbol: str,
        side: str,  # "BUY" or "SELL"
        shares: int,
        arrival_price: float,
        daily_turnover_inr: float,
        is_delivery: bool = True,
        base_slippage_pct: float = 0.15
    ) -> Dict[str, Any]:
        """
        Executes a paper order and accounts for market impact, slippage, and statutory taxes.
        """
        order_id = str(uuid.uuid4())[:8]
        order_value_arrival = shares * arrival_price

        # Model market impact: quadratic expansion based on trade size vs daily turnover
        if daily_turnover_inr > 0:
            participation_rate = order_value_arrival / daily_turnover_inr
            market_impact_pct = round(min(1.5, participation_rate * 2.0), 3)
        else:
            market_impact_pct = 0.05

        total_friction_pct = base_slippage_pct + market_impact_pct

        if side.upper() == "BUY":
            executed_price = round(arrival_price * (1.0 + total_friction_pct / 100.0), 2)
            slippage_inr = round((executed_price - arrival_price) * shares, 2)
        else:
            executed_price = round(arrival_price * (1.0 - total_friction_pct / 100.0), 2)
            slippage_inr = round((arrival_price - executed_price) * shares, 2)

        actual_turnover = round(shares * executed_price, 2)

        # Calculate Indian statutory taxes (STT, GST, Exchange fee, Stamp duty)
        cost_report = TransactionCostCalculator.calculate_trade_costs(
            invested_capital_inr=actual_turnover,
            gross_return_pct=0.0,
            is_delivery=is_delivery,
            slippage_pct=0.0
        )
        total_taxes_inr = cost_report["statutory_cost_inr"]

        return {
            "order_id": order_id,
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": symbol,
            "side": side.upper(),
            "shares": shares,
            "arrival_price": arrival_price,
            "executed_price": executed_price,
            "turnover_inr": actual_turnover,
            "market_impact_pct": market_impact_pct,
            "base_slippage_pct": base_slippage_pct,
            "slippage_cost_inr": slippage_inr,
            "statutory_taxes_inr": total_taxes_inr,
            "total_execution_friction_inr": round(slippage_inr + total_taxes_inr, 2),
            "execution_status": "FILLED_PAPER_SIMULATION"
        }

    @staticmethod
    def calculate_implementation_shortfall(
        entry_arrival_price: float,
        exit_arrival_price: float,
        entry_executed_price: float,
        exit_executed_price: float,
        shares: int,
        is_delivery: bool = True
    ) -> Dict[str, Any]:
        """
        Audits theoretical paper return vs actual net realized return after all friction.
        """
        # 1. Theoretical Return (Zero slippage at exact arrival prices)
        theoretical_gross_inr = (exit_arrival_price - entry_arrival_price) * shares
        theoretical_invested = entry_arrival_price * shares
        theoretical_return_pct = round((theoretical_gross_inr / theoretical_invested) * 100.0, 2) if theoretical_invested > 0 else 0.0

        # 2. Actual Realized Return
        actual_invested = entry_executed_price * shares
        actual_gross_inr = (exit_executed_price - entry_executed_price) * shares
        actual_gross_pct = ((exit_executed_price - entry_executed_price) / entry_executed_price) * 100.0 if entry_executed_price > 0 else 0.0

        cost_res = TransactionCostCalculator.calculate_trade_costs(
            invested_capital_inr=actual_invested,
            gross_return_pct=actual_gross_pct,
            is_delivery=is_delivery
        )
        actual_net_return_pct = cost_res["net_return_pct"]
        actual_net_pnl_inr = round(actual_invested * (actual_net_return_pct / 100.0), 2)

        # Implementation Shortfall = Theoretical P&L - Actual Net P&L
        shortfall_inr = round(theoretical_gross_inr - actual_net_pnl_inr, 2)
        shortfall_pct = round(theoretical_return_pct - actual_net_return_pct, 2)

        return {
            "theoretical_gross_pnl_inr": round(theoretical_gross_inr, 2),
            "theoretical_return_pct": theoretical_return_pct,
            "actual_net_pnl_inr": actual_net_pnl_inr,
            "actual_net_return_pct": actual_net_return_pct,
            "implementation_shortfall_inr": shortfall_inr,
            "implementation_shortfall_pct": shortfall_pct,
            "friction_drag_summary": f"Total friction drag: {shortfall_pct:.2f}% (Taxes + Slippage + Market Impact)"
        }
