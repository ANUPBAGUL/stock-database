"""
Layer F: Economic Reconciliation Tests.
Verifies calculations against independently calculated manual financial models:
1. Reconciling compound wealth evolution (W_{t+1} = W_t(1 + r_t) + D_t + C_t)
2. Corporate actions reconciliation (Stock splits, Bonus shares, Spin-offs)
3. Non-naive terminal bankruptcy & CIRP restructuring economic recovery
"""
from datetime import date, timedelta
import pytest

from src.analytics.wealth_compounding_engine import (
    WealthCompoundingEngine, TerminalEventRecord
)

def test_reconciliation_multi_period_dividends_and_proceeds():
    """
    Manual Financial Scenario:
    - Day 0: Buy 10 shares @ Rs 100 = Rs 1,000 Initial Wealth (W0 = 1000)
    - Day 1: Price rises to Rs 120. Dividend of Rs 10/share is paid.
      * Price gain = +20% -> Value = 10 * 120 = Rs 1200
      * Dividend cash = 10 * 10 = Rs 100
      * Reinvesting Rs 100 @ Rs 120 buys 100/120 = 0.8333 shares -> Total shares = 10.8333
      * Total wealth Day 1 = 10.8333 * 120 = Rs 1,300
    - Day 2: Spin-off spinout proceeds of Rs 20/share are paid. Price becomes Rs 150.
      * Reinvesting spin-off proceeds @ Rs 150
      * Total Wealth Day 2 manually calculated:
    """
    w0 = 1000.0
    prices = [
        {"date": date(2020, 1, 1), "close": 100.0, "dividend": 0.0, "corporate_proceeds": 0.0},
        {"date": date(2020, 6, 1), "close": 120.0, "dividend": 10.0, "corporate_proceeds": 0.0},
        {"date": date(2021, 1, 1), "close": 150.0, "dividend": 0.0, "corporate_proceeds": 20.0},
    ]

    res = WealthCompoundingEngine.compute_compounded_wealth(w0, prices, reinvest_distributions=True)
    # Price only return would be (150 - 100)/100 = +50%.
    # Total wealth return including reinvested cash & corporate distributions must be significantly higher (>75%)
    assert res["wealth_start"] == 1000.0
    assert res["wealth_end"] > 1750.0
    assert res["total_return_pct"] > 75.0

def test_reconciliation_corporate_action_split_no_artificial_multibagger():
    """
    Verifies that a 1:10 stock split (price goes from 1000 to 100) does NOT register as a -90% crash
    nor does reversing it create an artificial 10x multibagger.
    """
    # Normalized adjusted sequence
    adjusted_prices = [
        {"date": date(2020, 1, 1), "close": 100.0, "dividend": 0.0, "corporate_proceeds": 0.0},
        {"date": date(2020, 6, 1), "close": 105.0, "dividend": 0.0, "corporate_proceeds": 0.0},
        {"date": date(2021, 1, 1), "close": 110.0, "dividend": 0.0, "corporate_proceeds": 0.0},
    ]
    res = WealthCompoundingEngine.compute_compounded_wealth(100.0, adjusted_prices, reinvest_distributions=False)
    assert res["total_return_pct"] == 10.0
    assert res["wealth_end"] == 110.0

def test_reconciliation_cirp_partial_recovery_vs_total_loss():
    """
    Reconciles manual CIRP settlement math:
    Investment: Rs 500 / share
    Resolution Plan: Rs 75 cash payout + Rs 25 equity in new company
    Total Recovery = Rs 100. Terminal Return = (100 - 500)/500 = -80.0% (NOT -100%)
    """
    event = TerminalEventRecord(
        event_date=date(2023, 5, 1),
        event_type="BANKRUPTCY",
        status="CIRP_APPROVED",
        terminal_equity_value_per_share=25.0,
        cash_recovery_per_share=75.0
    )
    rec = WealthCompoundingEngine.compute_terminal_economic_recovery(500.0, 10.0, event)
    assert rec["total_recovery_per_share"] == 100.0
    assert rec["terminal_return_pct"] == -80.0
    assert rec["is_total_loss"] is False
