"""
Layer 5: 3-Pillar Institutional Valuation Engine.

Implements the multi-dimensional valuation framework triangulating:
1. Growth-Adjusted Valuation (Dynamic PEG Ratio)
2. Free Cash Flow Yield vs. Sovereign Risk-Free Benchmark (India 10Y G-Sec: 7.1%)
3. Reverse-DCF Expectations Solver (Mauboussin Model)
4. Historical Multiple Percentile Positioning

Assigns one of 6 institutional valuation regimes:
- UNDERVALUED_COMPOUNDER
- DEEP_VALUE
- FAIR_VALUE
- QUALITY_GROWTH_PREMIUM
- OVERVALUED_EXTREME
- VALUE_TRAP_WARNING
"""

from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

# Indian Macro Benchmark Parameters
INDIA_10Y_GSEC_YIELD_PCT = 7.10  # 10-Year Indian Sovereign Bond Baseline
EQUITY_RISK_PREMIUM_PCT = 4.90   # Standard India ERP
COST_OF_EQUITY_DEFAULT = (INDIA_10Y_GSEC_YIELD_PCT + EQUITY_RISK_PREMIUM_PCT) / 100.0  # 12.0%
TERMINAL_GROWTH_DEFAULT = 0.055  # 5.5% Long-term nominal GDP baseline


class ValuationEngine:
    """
    Quantitative valuation engine computing growth-adjusted multiples,
    cash flow yields, reverse-DCF market expectations, and composite regime states.
    """

    @classmethod
    def calculate_peg_ratio(
        cls,
        pe_ratio: Optional[float],
        eps_growth_pct: Optional[float],
        sustainable_growth_pct: Optional[float] = None
    ) -> Tuple[Optional[float], str]:
        """
        Computes dynamic Price/Earnings-to-Growth (PEG) ratio with institutional safeguards.

        Safeguards:
        - If PE <= 0 or missing, PEG is undefined.
        - If EPS growth <= 0, flagged as 'NEGATIVE_GROWTH' (cannot divide by negative).
        - If EPS growth > 60.0% (base-effect spike), normalizes using sustainable growth (e.g. revenue YoY)
          or clamps effective denominator to mitigate extreme base-effect distortions.
        - Clamps effective lower bound to 5.0% to prevent division by near-zero growth.
        """
        if pe_ratio is None or pe_ratio <= 0:
            return None, "PE_UNDEFINED"

        if eps_growth_pct is None and sustainable_growth_pct is None:
            return None, "GROWTH_UNKNOWN"

        effective_growth = eps_growth_pct if eps_growth_pct is not None else sustainable_growth_pct

        if effective_growth is None or effective_growth <= 0:
            return None, "NEGATIVE_GROWTH"

        if effective_growth > 60.0:
            # Check if sustainable revenue growth is available to normalize base-effect spike
            if sustainable_growth_pct and sustainable_growth_pct > 0:
                norm_growth = min(50.0, max(5.0, sustainable_growth_pct))
                norm_peg = round(pe_ratio / norm_growth, 2)
                return norm_peg, "NORMALIZED_SUSTAINABLE"
            # Otherwise compute genuine raw PEG on unconstrained hypergrowth with explicit base-effect flag
            raw_peg = round(pe_ratio / effective_growth, 2)
            return raw_peg, "HYPERGROWTH_BASE_EFFECT"

        # Base-effect clamping for lower bound (prevent division by near-zero growth)
        clamped_growth = max(5.0, effective_growth)
        raw_peg = round(pe_ratio / clamped_growth, 2)
        return raw_peg, "VALID"

    @staticmethod
    def calculate_fcf_yield(
        ttm_fcf_cr: Optional[float],
        market_cap_cr: Optional[float]
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Computes Free Cash Flow Yield and the spread over the 10Y Indian Sovereign Yield (7.1%).
        Returns: (fcf_yield_pct, gsec_spread_pct)
        """
        if ttm_fcf_cr is None or market_cap_cr is None or market_cap_cr <= 0:
            return None, None

        fcf_yield = round((ttm_fcf_cr / market_cap_cr) * 100.0, 2)
        gsec_spread = round(fcf_yield - INDIA_10Y_GSEC_YIELD_PCT, 2)
        return fcf_yield, gsec_spread

    @staticmethod
    def solve_reverse_dcf_implied_growth(
        market_cap_cr: Optional[float],
        ttm_fcf_cr: Optional[float],
        cost_of_equity: float = COST_OF_EQUITY_DEFAULT,
        terminal_growth: float = TERMINAL_GROWTH_DEFAULT,
        forecast_years: int = 5,
        ttm_nopat_cr: Optional[float] = None,
        net_debt_cr: Optional[float] = 0.0
    ) -> Optional[float]:
        """
        Inverts the standard 2-Stage DCF model using numerical bisection to find the exact
        5-year compound growth rate (g_implied) required to justify the current market capitalization.

        DCF Formula:
          PV = sum_{t=1}^N [ CF_0 * (1 + g)^t / (1 + r)^t ] + [ CF_N * (1 + g_T) / (r - g_T) ] / (1 + r)^N

        Returns: Implied 5-year CAGR as percentage (e.g. 14.5 for 14.5%), or None if unsolvable.
        Supports normalized Owner Earnings / NOPAT baseline when FCF is non-positive due to capacity expansion.
        """
        if market_cap_cr is None or market_cap_cr <= 0:
            return None

        # Determine normalized baseline cash flow:
        # If FCF is positive and representative, use FCF.
        # If FCF is non-positive or artificially depressed by capacity expansion capex
        # (e.g. FCF yield < 0.5% or FCF < 15% of NOPAT while NOPAT is substantial),
        # use normalized NOPAT / Owner Earnings.
        base_cf = None
        is_fcf_depressed = (
            ttm_fcf_cr is not None
            and ttm_nopat_cr is not None
            and ttm_nopat_cr > 0
            and (
                ttm_fcf_cr <= 0
                or (market_cap_cr and (ttm_fcf_cr / market_cap_cr) < 0.005)
                or ttm_fcf_cr < 0.15 * ttm_nopat_cr
            )
        )

        if not is_fcf_depressed and ttm_fcf_cr is not None and ttm_fcf_cr > 0:
            base_cf = ttm_fcf_cr
        elif ttm_nopat_cr is not None and ttm_nopat_cr > 0:
            base_cf = ttm_nopat_cr
        elif ttm_fcf_cr is not None and ttm_fcf_cr > 0:
            base_cf = ttm_fcf_cr

        if base_cf is None or base_cf <= 0:
            return None

        if cost_of_equity <= terminal_growth:
            return None

        target_val = float(market_cap_cr)
        if net_debt_cr is not None and base_cf == ttm_nopat_cr:
            # When discounting operating earnings (NOPAT/FCFF), target Enterprise Value = MCap + Net Debt.
            # Net Cash (net_debt_cr < 0) reduces required operating enterprise value.
            # Enforce 35% liquidation/operating safety floor to prevent negative EV singularities in cash shells.
            target_val = max(float(market_cap_cr) * 0.35, float(market_cap_cr) + float(net_debt_cr))

        def dcf_value(g: float) -> float:
            pv_explicit = 0.0
            cf = base_cf
            for t in range(1, forecast_years + 1):
                cf *= (1.0 + g)
                pv_explicit += cf / ((1.0 + cost_of_equity) ** t)
            
            # Terminal Value
            terminal_cf = cf * (1.0 + terminal_growth)
            tv = terminal_cf / (cost_of_equity - terminal_growth)
            pv_tv = tv / ((1.0 + cost_of_equity) ** forecast_years)
            return pv_explicit + pv_tv

        # Numerical bisection solver over [-50% growth, +200% growth]
        low = -0.50
        high = 2.00

        # Check bounds
        val_low = dcf_value(low)
        val_high = dcf_value(high)

        if target_val < val_low:
            return -50.0  # Extremely depressed valuation
        if target_val > val_high:
            return 200.0  # Extreme astronomical expectation

        for _ in range(60):
            mid = (low + high) / 2.0
            val_mid = dcf_value(mid)

            if abs(val_mid - target_val) < 0.01:
                return round(mid * 100.0, 1)

            if val_mid < target_val:
                low = mid
            else:
                high = mid

        return round(mid * 100.0, 1)

    @classmethod
    def evaluate_valuation(
        cls,
        pe_ratio: Optional[float],
        pb_ratio: Optional[float],
        eps_growth_pct: Optional[float],
        roce_pct: Optional[float],
        ttm_fcf_cr: Optional[float],
        market_cap_cr: Optional[float],
        debt_to_equity: Optional[float] = None,
        pe_percentile_3y: Optional[float] = None,
        ttm_nopat_cr: Optional[float] = None,
        sustainable_growth_pct: Optional[float] = None,
        net_debt_cr: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Full multi-factor institutional valuation synthesis.
        Triangulates PEG, FCF Yield, Implied Growth, and Capital Efficiency into a composite regime.
        """
        peg_ratio, peg_status = cls.calculate_peg_ratio(pe_ratio, eps_growth_pct, sustainable_growth_pct=sustainable_growth_pct)
        fcf_yield_pct, gsec_spread_pct = cls.calculate_fcf_yield(ttm_fcf_cr, market_cap_cr)
        implied_growth_pct = cls.solve_reverse_dcf_implied_growth(market_cap_cr, ttm_fcf_cr, ttm_nopat_cr=ttm_nopat_cr, net_debt_cr=net_debt_cr)

        is_fcf_depressed = (
            ttm_fcf_cr is not None
            and ttm_nopat_cr is not None
            and ttm_nopat_cr > 0
            and (
                ttm_fcf_cr <= 0
                or (market_cap_cr and (ttm_fcf_cr / market_cap_cr) < 0.005)
                or ttm_fcf_cr < 0.15 * ttm_nopat_cr
            )
        )
        if is_fcf_depressed:
            cf_basis = "NOPAT_NORMALIZED"
        elif ttm_fcf_cr and ttm_fcf_cr > 0:
            cf_basis = "FCF"
        elif ttm_nopat_cr and ttm_nopat_cr > 0:
            cf_basis = "NOPAT_OWNER_EARNINGS"
        else:
            cf_basis = "NONE"

        pe = pe_ratio if pe_ratio is not None else 0.0
        roce = roce_pct if roce_pct is not None else 0.0
        growth = eps_growth_pct if eps_growth_pct is not None else (sustainable_growth_pct if sustainable_growth_pct is not None else 0.0)
        fcf_y = fcf_yield_pct if fcf_yield_pct is not None else 0.0
        dte = debt_to_equity if debt_to_equity is not None else 0.0
        pe_pctile = pe_percentile_3y if pe_percentile_3y is not None else 50.0

        # ── 6-State Institutional Decision Classifier ──
        # 1. VALUE TRAP RISK (Cheap multiple masking terminal decay / negative returns)
        if pe > 0 and pe <= 18.0 and (growth < 0 or (roce < 12.0 and fcf_y < 2.0)):
            status = "VALUE_TRAP_WARNING"
            label = "Value Trap Risk"
            badge = "badge-rose"
            summary = f"Low P/E ({pe:.1f}x) is deceptive: negative growth ({growth:.1f}%) and weak ROCE ({roce:.1f}%)."

        # 2. OVERVALUED EXTREME (Excessive multiple compression risk)
        elif (pe > 65.0 and (peg_ratio is None or peg_ratio > 2.5 or growth < 15.0)) or (peg_ratio is not None and peg_ratio > 3.0) or (implied_growth_pct is not None and implied_growth_pct > 35.0 and growth < 20.0):
            status = "OVERVALUED_EXTREME"
            label = "Overvalued / Stretched"
            badge = "badge-rose"
            summary = f"High valuation friction: P/E at {pe:.1f}x (PEG {peg_ratio if peg_ratio else 'N/A'}) with market implying {implied_growth_pct or 'high'}% CAGR."

        # 3. UNDERVALUED COMPOUNDER (High ROCE + Attractive Growth Multiplier)
        # Requires reasonable valuation multiple (PE <= 38.0) and non-base-effect PEG
        elif roce >= 18.0 and peg_ratio is not None and peg_ratio <= 1.15 and pe_pctile <= 65.0 and pe <= 38.0 and peg_status != "HYPERGROWTH_BASE_EFFECT":
            status = "UNDERVALUED_COMPOUNDER"
            label = "Undervalued Compounder"
            badge = "badge-emerald"
            summary = f"Elite compounding: ROCE {roce:.1f}% trading at attractive PEG of {peg_ratio:.2f}x."

        # 4. DEEP VALUE (High cash generation & clean balance sheet)
        elif pe > 0 and pe <= 16.0 and fcf_y >= 6.5 and dte <= 0.6 and roce >= 13.0:
            status = "DEEP_VALUE"
            label = "Deep Value"
            badge = "badge-emerald"
            summary = f"High margin of safety: FCF yield {fcf_y:.1f}% exceeds G-Sec yield ({INDIA_10Y_GSEC_YIELD_PCT}%) with clean debt ({dte:.2f} D/E)."

        # 5. QUALITY GROWTH PREMIUM (Great franchise commanding market multiple premium)
        # High ROCE (> 20%) companies trading at growth multiples (PE > 35 or PEG 1.15 - 2.8)
        elif roce >= 20.0 and (pe > 35.0 or (peg_ratio is not None and 1.15 < peg_ratio <= 2.8)):
            status = "QUALITY_GROWTH_PREMIUM"
            label = "Quality Growth Premium"
            badge = "badge-amber"
            summary = f"High quality franchise (ROCE {roce:.1f}%) commanding fair growth premium (P/E {pe:.1f}x, PEG {peg_ratio if peg_ratio else 'N/A'}x)."

        # 6. FAIR VALUE (In line with fundamentals)
        else:
            status = "FAIR_VALUE"
            label = "Fairly Valued"
            badge = "badge-cyan"
            summary = f"Valuation in line with earnings compounding: P/E {pe:.1f}x with PEG {peg_ratio if peg_ratio else '1.30'}x."

        return {
            "status": status,
            "status_label": label,
            "badge_class": badge,
            "pe_ratio": round(pe, 2) if pe > 0 else None,
            "pb_ratio": round(pb_ratio, 2) if pb_ratio and pb_ratio > 0 else None,
            "peg_ratio": peg_ratio,
            "peg_status": peg_status,
            "fcf_yield_pct": fcf_yield_pct,
            "gsec_spread_pct": gsec_spread_pct,
            "india_10y_gsec_benchmark_pct": INDIA_10Y_GSEC_YIELD_PCT,
            "reverse_dcf_implied_growth_pct": implied_growth_pct,
            "cash_flow_basis": cf_basis,
            "pe_percentile_3y": pe_pctile,
            "verdict_summary": summary
        }
