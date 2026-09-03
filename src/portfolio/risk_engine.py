"""
Institutional Portfolio Risk Engine.

Enforces hard institutional portfolio limits and circuit breakers:
1. Single Stock Position Cap (Max 5.0% NAV)
2. Sector Concentration Cap (Max 20.0% NAV)
3. Liquidity Participation Constraint (Max 5.0% of 20-Day ADV)
4. Portfolio Drawdown Circuit Breaker (Halts new risk if Drawdown > -10.0%)
5. Exchange Price Band / Circuit Limit Filter
"""

import logging
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InstitutionalRiskEngine:
    """
    Pre-trade risk compliance and portfolio sizing gate.
    """
    MAX_SINGLE_STOCK_PCT = 5.0    # Max 5% per stock
    MAX_SECTOR_PCT = 20.0          # Max 20% per sector
    MAX_ADV_PARTICIPATION_PCT = 5.0 # Max 5% of daily volume
    PORTFOLIO_DRAWDOWN_HALT_PCT = -10.0 # Circuit breaker at -10% portfolio drawdown

    @staticmethod
    def audit_trade_compliance(
        portfolio_nav_inr: float,
        proposed_investment_inr: float,
        symbol: str,
        sector: str,
        current_price: float,
        daily_turnover_inr: float,
        existing_stock_holding_inr: float = 0.0,
        existing_sector_exposure_inr: float = 0.0,
        current_portfolio_drawdown_pct: float = 0.0,
        is_near_circuit: bool = False
    ) -> Dict[str, Any]:
        """
        Audits a proposed trade against all institutional risk limits.
        """
        violations = []
        warnings = []
        approved_investment_inr = proposed_investment_inr

        # 1. Portfolio Drawdown Circuit Breaker
        if current_portfolio_drawdown_pct <= InstitutionalRiskEngine.PORTFOLIO_DRAWDOWN_HALT_PCT:
            violations.append(
                f"PORTFOLIO_DRAWDOWN_BREAKER_ACTIVE: Current Drawdown ({current_portfolio_drawdown_pct:.1f}%) "
                f"exceeds max limit ({InstitutionalRiskEngine.PORTFOLIO_DRAWDOWN_HALT_PCT}%). All new risk halted."
            )
            return {
                "compliance_status": "REJECTED_DRAWDOWN_BREAKER",
                "approved_investment_inr": 0.0,
                "approved_shares": 0,
                "violations": violations,
                "warnings": warnings
            }

        # 2. Exchange Circuit Band Filter
        if is_near_circuit:
            violations.append(f"CIRCUIT_BAND_RISK: {symbol} is near 5%/10%/20% exchange circuit limit. Execution blocked.")
            return {
                "compliance_status": "REJECTED_CIRCUIT_BAND",
                "approved_investment_inr": 0.0,
                "approved_shares": 0,
                "violations": violations,
                "warnings": warnings
            }

        # 3. Single Stock Position Cap Check (5% NAV)
        max_stock_capital = portfolio_nav_inr * (InstitutionalRiskEngine.MAX_SINGLE_STOCK_PCT / 100.0)
        remaining_stock_cap = max(0.0, max_stock_capital - existing_stock_holding_inr)

        if proposed_investment_inr > remaining_stock_cap:
            warnings.append(
                f"SINGLE_STOCK_CAP_EXCEEDED: Capped from Rs.{proposed_investment_inr:,.0f} to Rs.{remaining_stock_cap:,.0f} "
                f"({InstitutionalRiskEngine.MAX_SINGLE_STOCK_PCT}% NAV Limit)"
            )
            approved_investment_inr = min(approved_investment_inr, remaining_stock_cap)

        # 4. Sector Concentration Cap Check (20% NAV)
        max_sector_capital = portfolio_nav_inr * (InstitutionalRiskEngine.MAX_SECTOR_PCT / 100.0)
        remaining_sector_cap = max(0.0, max_sector_capital - existing_sector_exposure_inr)

        if approved_investment_inr > remaining_sector_cap:
            warnings.append(
                f"SECTOR_CONCENTRATION_EXCEEDED: Capped from Rs.{approved_investment_inr:,.0f} to Rs.{remaining_sector_cap:,.0f} "
                f"({InstitutionalRiskEngine.MAX_SECTOR_PCT}% Sector Limit for '{sector}')"
            )
            approved_investment_inr = min(approved_investment_inr, remaining_sector_cap)

        # 5. Liquidity / ADV Participation Limit Check (5% ADV)
        max_liquidity_capital = daily_turnover_inr * (InstitutionalRiskEngine.MAX_ADV_PARTICIPATION_PCT / 100.0)
        if approved_investment_inr > max_liquidity_capital and max_liquidity_capital > 0:
            warnings.append(
                f"LIQUIDITY_CONSTRAINT: Sized down to Rs.{max_liquidity_capital:,.0f} "
                f"(Max {InstitutionalRiskEngine.MAX_ADV_PARTICIPATION_PCT}% of 20-day ADV to prevent slippage)"
            )
            approved_investment_inr = min(approved_investment_inr, max_liquidity_capital)

        approved_shares = int(approved_investment_inr / current_price) if current_price > 0 else 0
        final_investment_inr = round(approved_shares * current_price, 2)

        if final_investment_inr <= 0:
            status = "REJECTED_CAPACITY_ZERO"
        elif warnings:
            status = "APPROVED_WITH_CAPACITY_REDUCTION"
        else:
            status = "APPROVED_FULL_SIZE"

        return {
            "symbol": symbol,
            "sector": sector,
            "compliance_status": status,
            "requested_investment_inr": proposed_investment_inr,
            "approved_investment_inr": final_investment_inr,
            "approved_shares": approved_shares,
            "risk_limits": {
                "max_single_stock_pct": InstitutionalRiskEngine.MAX_SINGLE_STOCK_PCT,
                "max_sector_pct": InstitutionalRiskEngine.MAX_SECTOR_PCT,
                "max_adv_participation_pct": InstitutionalRiskEngine.MAX_ADV_PARTICIPATION_PCT,
                "portfolio_drawdown_limit_pct": InstitutionalRiskEngine.PORTFOLIO_DRAWDOWN_HALT_PCT
            },
            "violations": violations,
            "warnings": warnings
        }
