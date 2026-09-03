import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TransactionCostCalculator:
    """
    Calculates realistic trade execution costs for Indian equities.
    Accounts for STT (round-trip), Brokerage, Stamp Duty, GST, Exchange charges,
    SEBI Turnover charges, DP charges, and Slippage.
    """

    DP_CHARGE_INR = 15.93 # CDSL/NSDL flat DP charge (~13.50 + 18% GST) per sell leg

    @classmethod
    def calculate_trade_costs(
        cls,
        invested_capital_inr: float,
        gross_return_pct: float,
        is_delivery: bool = True,
        slippage_pct: float = 0.15 # 0.15% per side default slippage
    ) -> Dict[str, Any]:
        """
        Calculates exact round-trip trade execution costs for a position in Indian equities.
        """
        buy_value = max(100.0, invested_capital_inr)
        sell_value = max(0.0, buy_value * (1.0 + gross_return_pct / 100.0))
        turnover_inr = buy_value + sell_value

        # 1. Statutory Taxes & Exchange Fees
        if is_delivery:
            # Delivery: STT 0.1% on Buy AND 0.1% on Sell (Total 0.20%)
            stt = 0.0010 * buy_value + 0.0010 * sell_value
            stamp_duty = 0.00015 * buy_value # Stamp duty on buy side only
            dp_charge = cls.DP_CHARGE_INR if sell_value > 0 else 0.0
        else:
            # Intraday: STT 0.025% on Sell side only
            stt = 0.00025 * sell_value
            stamp_duty = 0.00003 * buy_value
            dp_charge = 0.0

        exchange_fee = 0.0000345 * turnover_inr
        sebi_charges = 0.0000010 * turnover_inr # Rs 10 per crore

        # Brokerage (Buy + Sell leg)
        brokerage_buy = min(20.0, 0.0005 * buy_value)
        brokerage_sell = min(20.0, 0.0005 * sell_value)
        total_brokerage = brokerage_buy + brokerage_sell

        # GST 18% on services (Brokerage + Exchange fees + SEBI charges)
        gst = 0.18 * (total_brokerage + exchange_fee + sebi_charges)

        statutory_costs_inr = stt + stamp_duty + exchange_fee + sebi_charges + total_brokerage + gst + dp_charge

        # 2. Slippage & Impact Cost
        slippage_cost_inr = (buy_value * (slippage_pct / 100.0)) + (sell_value * (slippage_pct / 100.0))
        total_costs_inr = statutory_costs_inr + slippage_cost_inr

        # Net Return relative to initial invested capital
        gross_profit_inr = sell_value - buy_value
        net_profit_inr = gross_profit_inr - total_costs_inr
        net_return_pct = (net_profit_inr / buy_value) * 100.0
        total_cost_pct = (total_costs_inr / buy_value) * 100.0

        return {
            "invested_capital_inr": round(buy_value, 2),
            "sell_value_inr": round(sell_value, 2),
            "turnover_inr": round(turnover_inr, 2),
            "gross_return_pct": round(gross_return_pct, 2),
            "net_return_pct": round(net_return_pct, 2),
            "statutory_cost_inr": round(statutory_costs_inr, 2),
            "slippage_cost_inr": round(slippage_cost_inr, 2),
            "total_costs_inr": round(total_costs_inr, 2),
            "total_cost_pct": round(total_cost_pct, 4),
            "stt_inr": round(stt, 2),
            "brokerage_inr": round(total_brokerage, 2),
            "dp_charge_inr": round(dp_charge, 2)
        }

    @classmethod
    def calculate_net_return(
        cls,
        gross_return_pct: float,
        turnover_inr: float = 100000.0,
        is_delivery: bool = True,
        slippage_pct: float = 0.15
    ) -> Dict[str, Any]:
        """Convenience wrapper for portfolio return calculation."""
        invested = turnover_inr / (2.0 + gross_return_pct / 100.0) if turnover_inr > 0 else 100000.0
        res = cls.calculate_trade_costs(invested, gross_return_pct, is_delivery, slippage_pct)
        return {
            "gross_return_pct": res["gross_return_pct"],
            "net_return_pct": res["net_return_pct"],
            "statutory_cost_inr": res["statutory_cost_inr"],
            "statutory_cost_pct": round((res["statutory_cost_inr"] / res["invested_capital_inr"]) * 100, 4),
            "slippage_pct": round(slippage_pct * 2, 4),
            "total_cost_pct": res["total_cost_pct"]
        }
