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
        Validates Assets = Liabilities + Net Worth (within tolerance percentage).
        """
        total_assets = data.get("total_assets")
        total_liabilities = data.get("total_liabilities")
        net_worth = data.get("net_worth")

        if total_assets is None or total_liabilities is None or net_worth is None:
            return True, "Balance sheet items partially missing; check bypassed."

        expected_assets = total_liabilities + net_worth
        diff = abs(total_assets - expected_assets)
        max_val = max(abs(total_assets), abs(expected_assets), 1.0)
        relative_diff = diff / max_val

        if relative_diff > tolerance:
            err_msg = (
                f"Balance Sheet Discrepancy: Assets ({total_assets}) != "
                f"Liabilities ({total_liabilities}) + Net Worth ({net_worth}). "
                f"Diff: {diff} ({relative_diff:.2%})"
            )
            logger.warning(err_msg)
            return False, err_msg

        return True, "Balance sheet double-entry verified successfully."

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
