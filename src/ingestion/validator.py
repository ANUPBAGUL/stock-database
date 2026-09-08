import logging
from typing import Dict, Any, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataValidator:
    """
    Validates financial statement data and price data before committing to Bitemporal storage.
    """

    @staticmethod
    def validate_balance_sheet(data: Dict[str, Any], tolerance: float = 0.05) -> Tuple[bool, str]:
        """
        Validates Balance Sheet double-entry equality (within tolerance percentage).
        Handles both reporting conventions:
        1. Ind AS / Indian MCA / Screener convention: 'Total Liabilities' includes Equity + Liabilities (Total Assets == Total Liabilities).
        2. External Liabilities convention: Total Assets == External Liabilities + Net Worth.
        3. Component sum: Total Assets == Net Worth + Total Debt + Other/Current Liabilities.
        """
        total_assets = data.get("total_assets")
        total_liabilities = data.get("total_liabilities")
        net_worth = data.get("net_worth")

        if total_assets is None:
            return True, "Total assets not provided; check bypassed."

        # Case 1: Ind AS Total Equities & Liabilities (total_liabilities == total_assets)
        if total_liabilities is not None:
            diff_ind_as = abs(total_assets - total_liabilities)
            rel_diff_ind_as = diff_ind_as / max(abs(total_assets), 1.0)
            if rel_diff_ind_as <= tolerance:
                return True, "Balance sheet verified: Total Assets == Total Equities & Liabilities (Ind AS)."

        # Case 2: External Liabilities + Net Worth == Total Assets
        if total_liabilities is not None and net_worth is not None:
            expected_assets = total_liabilities + net_worth
            diff_ext = abs(total_assets - expected_assets)
            rel_diff_ext = diff_ext / max(abs(total_assets), abs(expected_assets), 1.0)
            if rel_diff_ext <= tolerance:
                return True, "Balance sheet verified: Total Assets == External Liabilities + Net Worth."

        # Case 3: Component sum (Net Worth + Debt + Other Liabilities)
        debt = data.get("total_debt") or data.get("borrowings") or 0.0
        other_l = data.get("other_liabilities") or data.get("current_liabilities") or 0.0
        if net_worth is not None and (debt > 0 or other_l > 0):
            sum_parts = net_worth + debt + other_l
            diff_parts = abs(total_assets - sum_parts)
            rel_diff_parts = diff_parts / max(abs(total_assets), abs(sum_parts), 1.0)
            if rel_diff_parts <= tolerance:
                return True, "Balance sheet verified: Total Assets == Net Worth + Debt + Other Liabilities."

        if total_liabilities is None and net_worth is None:
            return True, "Liabilities and Net Worth missing; check bypassed."

        err_msg = (
            f"Balance Sheet Discrepancy: Assets ({total_assets}) does not match Liabilities "
            f"({total_liabilities}) / Net Worth ({net_worth})."
        )
        logger.warning(err_msg)
        return False, err_msg

    @staticmethod
    def validate_price_candle(open_p: float, high_p: float, low_p: float, close_p: float, volume: int) -> Tuple[bool, str]:
        """
        Validates OHLC candle logic: High >= Low, High >= Open, High >= Close, Low <= Open, Low <= Close.
        """
        if high_p < low_p:
            return False, f"Invalid Candle: High ({high_p}) < Low ({low_p})"
        if high_p < open_p or high_p < close_p:
            return False, f"Invalid Candle: High ({high_p}) is lower than Open/Close"
        if low_p > open_p or low_p > close_p:
            return False, f"Invalid Candle: Low ({low_p}) is higher than Open/Close"
        if volume < 0:
            return False, f"Invalid Volume: {volume}"

        return True, "Price candle verified."
