"""
Pillar 3: Working Capital & Forensic Anti-Trap Sentinel.

Detects aggressive revenue recognition, debtor days drift (second derivative acceleration),
cash conversion cycle (CCC) bloat, and CFO/EBITDA divergence in Indian equities.

Key Forensic Metrics:
1. Days Sales Outstanding (DSO) 1st & 2nd Derivative Drift (ΔDSO, Δ²DSO)
2. Receivables Growth YoY vs. Revenue Growth YoY Divergence
3. CFO to EBITDA Conversion Ratio (CFO / EBITDA < 70% warning, < 50% critical trap)
4. Cash Conversion Cycle (CCC = DSO + DIO - DPO) Trend
5. Composite Working Capital Forensic Risk Classification
"""

from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


class WorkingCapitalSentinel:
    """
    Forensic accounting sentinel analyzing working capital health and earnings quality.
    """

    @staticmethod
    def calculate_dso(
        trade_receivables_cr: Optional[float],
        revenue_cr: Optional[float],
        days_in_period: int = 365
    ) -> Optional[float]:
        """
        Computes Days Sales Outstanding (DSO).
        DSO = (Trade Receivables / Revenue) * days_in_period
        """
        if (
            trade_receivables_cr is None
            or revenue_cr is None
            or revenue_cr <= 0
            or trade_receivables_cr < 0
        ):
            return None
        return round((trade_receivables_cr / revenue_cr) * days_in_period, 2)

    @staticmethod
    def calculate_dio(
        inventories_cr: Optional[float],
        cogs_or_revenue_cr: Optional[float],
        days_in_period: int = 365
    ) -> Optional[float]:
        """
        Computes Days Inventory Outstanding (DIO).
        DIO = (Inventories / Cost of Goods or Revenue) * days_in_period
        """
        if (
            inventories_cr is None
            or cogs_or_revenue_cr is None
            or cogs_or_revenue_cr <= 0
            or inventories_cr < 0
        ):
            return None
        return round((inventories_cr / cogs_or_revenue_cr) * days_in_period, 2)

    @staticmethod
    def calculate_dpo(
        trade_payables_cr: Optional[float],
        cogs_or_revenue_cr: Optional[float],
        days_in_period: int = 365
    ) -> Optional[float]:
        """
        Computes Days Payable Outstanding (DPO).
        DPO = (Trade Payables / Cost of Goods or Revenue) * days_in_period
        """
        if (
            trade_payables_cr is None
            or cogs_or_revenue_cr is None
            or cogs_or_revenue_cr <= 0
            or trade_payables_cr < 0
        ):
            return None
        return round((trade_payables_cr / cogs_or_revenue_cr) * days_in_period, 2)

    @staticmethod
    def calculate_cash_conversion_cycle(
        dso: Optional[float],
        dio: Optional[float],
        dpo: Optional[float]
    ) -> Optional[float]:
        """
        Computes Cash Conversion Cycle (CCC).
        CCC = DSO + DIO - DPO
        """
        if dso is None:
            return None
        # If DIO or DPO is missing, treat as 0 for conservative fallback or return None
        effective_dio = dio if dio is not None else 0.0
        effective_dpo = dpo if dpo is not None else 0.0
        return round(dso + effective_dio - effective_dpo, 2)

    @staticmethod
    def calculate_dso_derivatives(
        dso_history: List[float]
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Computes the first derivative (ΔDSO) and second derivative (Δ²DSO) of DSO history.
        dso_history should be ordered chronologically [T-2, T-1, T_current].
        """
        if not dso_history or len(dso_history) < 2:
            return None, None

        # 1st derivative (latest change)
        delta_1 = dso_history[-1] - dso_history[-2]

        if len(dso_history) < 3:
            return round(delta_1, 2), None

        # 2nd derivative: (DSO_t - DSO_{t-1}) - (DSO_{t-1} - DSO_{t-2})
        prev_delta = dso_history[-2] - dso_history[-3]
        delta_2 = delta_1 - prev_delta

        return round(delta_1, 2), round(delta_2, 2)

    @staticmethod
    def calculate_receivables_divergence(
        revenue_growth_yoy_pct: Optional[float],
        receivables_growth_yoy_pct: Optional[float]
    ) -> Tuple[Optional[float], bool]:
        """
        Flags whether Trade Receivables are growing significantly faster than Revenue.
        Divergence = Receivables Growth YoY - Revenue Growth YoY.
        Threshold: Divergence > 15.0 percentage points is a severe red flag.
        """
        if revenue_growth_yoy_pct is None or receivables_growth_yoy_pct is None:
            return None, False

        divergence = round(receivables_growth_yoy_pct - revenue_growth_yoy_pct, 2)
        is_divergent = bool(divergence > 15.0 and receivables_growth_yoy_pct > 20.0)
        return divergence, is_divergent

    @staticmethod
    def calculate_cfo_ebitda_conversion(
        cfo_cr: Optional[float],
        ebitda_cr: Optional[float]
    ) -> Tuple[Optional[float], str]:
        """
        Computes Cash Flow from Operations (CFO) to EBITDA conversion ratio.
        - Ratio >= 80%: EXCELLENT_CASH_CONVERSION
        - 70% <= Ratio < 80%: ACCEPTABLE_CONVERSION
        - 50% <= Ratio < 70%: LOW_CONVERSION_WARNING (Working capital drag)
        - Ratio < 50% or CFO < 0 while EBITDA > 0: SEVERE_EARNINGS_QUALITY_TRAP
        """
        if ebitda_cr is None or ebitda_cr <= 0:
            if cfo_cr is not None and cfo_cr < 0:
                return None, "NEGATIVE_CFO_AND_EBITDA"
            return None, "EBITDA_NON_POSITIVE"

        if cfo_cr is None:
            return None, "CFO_DATA_MISSING"

        conversion_ratio = round(cfo_cr / ebitda_cr, 3)
        conversion_pct = round(conversion_ratio * 100.0, 1)

        if conversion_pct >= 80.0:
            status = "EXCELLENT_CASH_CONVERSION"
        elif conversion_pct >= 70.0:
            status = "ACCEPTABLE_CONVERSION"
        elif conversion_pct >= 50.0:
            status = "LOW_CONVERSION_WARNING"
        else:
            status = "SEVERE_EARNINGS_QUALITY_TRAP"

        return conversion_pct, status

    @classmethod
    def audit_forensic_risk(
        cls,
        current_receivables_cr: Optional[float],
        current_revenue_cr: Optional[float],
        current_inventories_cr: Optional[float],
        current_payables_cr: Optional[float],
        current_cfo_cr: Optional[float],
        current_ebitda_cr: Optional[float],
        revenue_growth_yoy_pct: Optional[float] = None,
        receivables_growth_yoy_pct: Optional[float] = None,
        dso_history: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        Executes complete forensic working capital audit and generates risk score and verdict.
        """
        dso = cls.calculate_dso(current_receivables_cr, current_revenue_cr)
        dio = cls.calculate_dio(current_inventories_cr, current_revenue_cr)
        dpo = cls.calculate_dpo(current_payables_cr, current_revenue_cr)
        ccc = cls.calculate_cash_conversion_cycle(dso, dio, dpo)

        delta_dso, delta2_dso = None, None
        if dso_history and len(dso_history) >= 2:
            delta_dso, delta2_dso = cls.calculate_dso_derivatives(dso_history)
        elif dso is not None:
            delta_dso = 0.0

        rec_div, is_rec_divergent = cls.calculate_receivables_divergence(
            revenue_growth_yoy_pct, receivables_growth_yoy_pct
        )

        cfo_conv_pct, cfo_status = cls.calculate_cfo_ebitda_conversion(
            current_cfo_cr, current_ebitda_cr
        )

        # Risk Penalties and Flags
        flags: List[str] = []
        risk_score = 0  # 0 = pristine, 100 = critical trap

        # 1. DSO Acceleration Check
        if delta2_dso is not None and delta2_dso > 10.0:
            flags.append(f"DSO accelerating upward (+{delta2_dso:.1f} days 2nd derivative)")
            risk_score += 25
        elif delta_dso is not None and delta_dso > 20.0:
            flags.append(f"DSO expansion (+{delta_dso:.1f} days YoY)")
            risk_score += 15

        # 2. Receivables Divergence Check
        if is_rec_divergent and rec_div is not None:
            flags.append(f"Receivables growth (+{receivables_growth_yoy_pct:.1f}%) outpacing revenue growth (+{revenue_growth_yoy_pct:.1f}%) by {rec_div:.1f}%")
            risk_score += 35

        # 3. CFO / EBITDA Quality Check
        if cfo_status == "SEVERE_EARNINGS_QUALITY_TRAP":
            pct_text = f"{cfo_conv_pct:.1f}%" if cfo_conv_pct is not None else "Negative"
            flags.append(f"Critical CFO/EBITDA conversion shortfall ({pct_text} vs 70% threshold)")
            risk_score += 40
        elif cfo_status == "LOW_CONVERSION_WARNING":
            pct_text = f"{cfo_conv_pct:.1f}%" if cfo_conv_pct is not None else "<70%"
            flags.append(f"Sub-par CFO/EBITDA conversion ({pct_text}) indicates working capital bloat")
            risk_score += 15

        # 4. Absolute DSO Threshold
        if dso is not None and dso > 180:
            flags.append(f"Elevated absolute DSO ({dso:.1f} days > 180 days)")
            risk_score += 15

        risk_score = min(100, risk_score)

        # Classification
        if risk_score >= 50 or cfo_status == "SEVERE_EARNINGS_QUALITY_TRAP":
            regime = "WORKING_CAPITAL_TRAP"
            badge_class = "badge-rose"
            is_circuit_breaker_triggered = True
            summary = "High forensic risk: Uncollected receivables and cash flow conversion failure."
        elif risk_score >= 30 or is_rec_divergent:
            regime = "AGGRESSIVE_RECOGNITION_RISK"
            badge_class = "badge-amber"
            is_circuit_breaker_triggered = False
            summary = "Elevated working capital drift: Receivables growing faster than reported sales."
        elif risk_score >= 15:
            regime = "MODERATE_DRIFT"
            badge_class = "badge-yellow"
            is_circuit_breaker_triggered = False
            summary = "Moderate working capital expansion; monitor future quarterly cash collection."
        else:
            regime = "HEALTHY"
            badge_class = "badge-emerald"
            is_circuit_breaker_triggered = False
            summary = "Pristine working capital: Strong CFO conversion and stable debtor days."

        return {
            "status": regime,
            "badge_class": badge_class,
            "risk_score": risk_score,
            "is_circuit_breaker_triggered": is_circuit_breaker_triggered,
            "dso": dso,
            "dio": dio,
            "dpo": dpo,
            "cash_conversion_cycle": ccc,
            "delta_dso": delta_dso,
            "delta2_dso": delta2_dso,
            "receivables_growth_divergence_pct": rec_div,
            "cfo_to_ebitda_pct": cfo_conv_pct,
            "cfo_conversion_status": cfo_status,
            "red_flags": flags,
            "summary": summary
        }
