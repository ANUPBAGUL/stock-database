"""
Feature Engine — Computes Point-In-Time technical and fundamental features as of date T.

All features are computed strictly using data that was published and available at date T,
guaranteeing zero look-ahead bias.

ROCE METHODOLOGY (IND-AS / Institutional Standard):
  - Numerator:   TTM EBIT (sum of 4 most recent quarterly EBIT values)
  - Denominator: Period-Average Capital Employed = (CE_Q0 + CE_Q-4) / 2
                 where CE = Total Assets - Current Liabilities
  - If Q-4 CE unavailable: single-period CE used with roce_methodology='SINGLE_PERIOD_CE' flag.
  - If balance sheet entirely missing: roce_pct = None (NOT fabricated from revenue proxy).

DEBT RATIOS:
  - gross_de_ratio  = total_debt / net_worth
  - net_de_ratio    = (total_debt - cash) / net_worth
  - financial_de_ratio = (financial_debt_lt + financial_debt_st) / net_worth  [excludes lease liabilities]
  - debt_to_ebitda  = total_debt / ttm_ebitda
"""

import logging
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from src.analytics.bitemporal_query import BitemporalQueryEngine
from src.analytics.price_adjuster import PriceAdjuster
from src.db.models import DailyPriceRaw

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252
TRADING_DAYS_50 = 50
TRADING_DAYS_200 = 200


class FeatureEngine:
    """
    Computes Point-In-Time technical and fundamental features as of date T.
    Uses institutional quantitative finance standards:
    - Annualized TTM (Trailing Twelve Months) EBIT & Revenue for ROCE and Margins
    - Wilder's 14-period exponential smoothed RSI
    - 14-day Average True Range (ATR)
    - Intraday High/Low 52-week distance metrics
    """

    @staticmethod
    def extract_features_as_of(
        db: Session, company_id: str, as_of_date: date
    ) -> Dict[str, Any]:
        as_of_datetime = datetime.combine(as_of_date, datetime.max.time())
        features = {
            "company_id": company_id,
            "as_of_date": as_of_date.isoformat(),
        }

        # ──────────────────────────────────────────────────────────────
        # 1. Fundamental Features (using Bitemporal PIT Query Engine)
        # ──────────────────────────────────────────────────────────────
        financials = BitemporalQueryEngine.get_financials_as_of(
            db, company_id, as_of_datetime, period_type="QUARTERLY", limit=8
        )

        if len(financials) >= 1:
            q0 = financials[0] # Most recent filing available at date T

            # Extract TTM (Trailing 4 Quarters) aggregates for annualized metrics
            recent_4_q = financials[:4]
            
            # Consolidation scope consistency check — flag if TTM quarters are mixed
            consolidation_scopes = [
                getattr(q, 'consolidation_scope', 'UNKNOWN') 
                for q in recent_4_q
            ]
            unique_scopes = set(consolidation_scopes)
            
            if len(unique_scopes) > 1:
                logger.warning(
                    f"[FeatureEngine] {company_id} TTM quarters have mixed consolidation_scope: "
                    f"{consolidation_scopes}. This may cause apples-to-oranges TTM aggregation. "
                    f"Consider filtering to single scope in bitemporal query."
                )
                features["ttm_consolidation_scope_flag"] = "MIXED"
            else:
                features["ttm_consolidation_scope_flag"] = "CONSISTENT"
            
            ttm_rev = sum(q.revenue for q in recent_4_q if q.revenue is not None)
            ttm_ebit = sum(q.ebit for q in recent_4_q if q.ebit is not None)
            ttm_ebitda = sum(q.ebitda for q in recent_4_q if q.ebitda is not None)
            ttm_pat = sum(q.pat for q in recent_4_q if q.pat is not None)
            ttm_ocf = sum(q.operating_cash_flow for q in recent_4_q if q.operating_cash_flow is not None)
            ttm_capex = sum(q.capex for q in recent_4_q if q.capex is not None)

            # Annualize if fewer than 4 quarters are available
            q_factor = 4.0 / len(recent_4_q) if len(recent_4_q) > 0 else 1.0
            if len(recent_4_q) < 4:
                ttm_rev *= q_factor
                ttm_ebit *= q_factor
                ttm_ebitda *= q_factor
                ttm_pat *= q_factor

            features["latest_revenue"] = q0.revenue
            features["latest_pat"] = q0.pat
            features["ttm_revenue"] = round(ttm_rev, 2) if ttm_rev > 0 else None
            features["ttm_pat"] = round(ttm_pat, 2)
            features["ttm_ebit"] = round(ttm_ebit, 2)

            features["ebitda_margin"] = round((ttm_ebitda / ttm_rev * 100), 2) if (ttm_ebitda and ttm_rev > 0) else None
            features["pat_margin"] = round((ttm_pat / ttm_rev * 100), 2) if (ttm_pat and ttm_rev > 0) else None

            # YoY Growth: match quarters 4 quarters apart
            q4 = FeatureEngine._find_yoy_quarter(financials, q0.period_end_date)
            if q4 and q4.revenue and q4.revenue > 0 and q0.revenue:
                features["revenue_yoy_growth_pct"] = round(((q0.revenue - q4.revenue) / abs(q4.revenue)) * 100, 2)
            else:
                features["revenue_yoy_growth_pct"] = None

            if q4 and q4.pat and q4.pat != 0 and q0.pat:
                features["pat_yoy_growth_pct"] = round(((q0.pat - q4.pat) / abs(q4.pat)) * 100, 2)
            else:
                features["pat_yoy_growth_pct"] = None

            # ── ROCE: Period-Average Capital Employed (IND-AS Institutional Standard) ──
            # Numerator:   TTM EBIT (4-quarter sum)
            # Denominator: Average CE = (CE_Q0 + CE_Q-4) / 2
            # If Q0 is an interim quarter (Q1/Q3 limited review without BS), look back to the latest
            # available audited balance sheet (e.g. Annual March / Semi-Annual Sept) in financials.
            total_assets = q0.total_assets or 0.0
            current_liab = getattr(q0, 'current_liabilities', None) or 0.0
            net_worth = q0.net_worth or 0.0
            total_debt = q0.total_debt or 0.0
            cash = q0.cash_and_equivalents or 0.0

            ce_q0 = None
            if total_assets > 0 and total_assets > current_liab:
                ce_q0 = total_assets - current_liab
            elif (net_worth + total_debt) > 0:
                ce_q0 = net_worth + total_debt

            # If Q0 has no balance sheet (intermediate quarter), find the most recent audited BS filing
            roce_methodology = "PERIOD_AVERAGE_CE"
            if ce_q0 is None:
                for f in financials[1:]:
                    ta = f.total_assets or 0.0
                    cl = getattr(f, 'current_liabilities', None) or 0.0
                    nw = f.net_worth or 0.0
                    td = f.total_debt or 0.0
                    if ta > 0 and ta > cl:
                        ce_q0 = ta - cl
                        total_assets = ta
                        current_liab = cl
                        net_worth = nw
                        total_debt = td
                        cash = f.cash_and_equivalents or 0.0
                        roce_methodology = "LAST_AUDITED_BS"
                        break
                    elif (nw + td) > 0:
                        ce_q0 = nw + td
                        net_worth = nw
                        total_debt = td
                        cash = f.cash_and_equivalents or 0.0
                        roce_methodology = "LAST_AUDITED_BS"
                        break

            # Fetch Q-4 (1-year ago) balance sheet for period-average CE
            ce_q4 = None
            if len(financials) >= 5:
                q4_filing = financials[4]
                ta4 = q4_filing.total_assets or 0.0
                cl4 = getattr(q4_filing, 'current_liabilities', None) or 0.0
                nw4 = q4_filing.net_worth or 0.0
                td4 = q4_filing.total_debt or 0.0
                if ta4 > 0 and ta4 > cl4:
                    ce_q4 = ta4 - cl4
                elif (nw4 + td4) > 0:
                    ce_q4 = nw4 + td4

            if ce_q0 is not None and ce_q4 is not None:
                cap_employed = (ce_q0 + ce_q4) / 2.0
            elif ce_q0 is not None:
                cap_employed = ce_q0
                if roce_methodology != "LAST_AUDITED_BS":
                    roce_methodology = "SINGLE_PERIOD_CE"  # flag: Q-4 CE unavailable
            else:
                cap_employed = None  # Balance sheet genuinely missing — do NOT fabricate

            roce_quarantine_flag = False
            if ttm_ebit is not None and cap_employed is not None and cap_employed > 0:
                calc_roce = (ttm_ebit / cap_employed) * 100
                features["roce_pct"] = round(min(120.0, max(-50.0, calc_roce)), 2)
                features["roce_methodology"] = roce_methodology
            else:
                features["roce_pct"] = None  # Missing balance sheet — never fabricate
                features["roce_methodology"] = "UNAVAILABLE"
                roce_quarantine_flag = True

            features["roce_quarantine_flag"] = roce_quarantine_flag
            features["roce_raw_inputs"] = {
                "ttm_ebit": ttm_ebit,
                "ce_q0": ce_q0,
                "ce_q4": ce_q4,
                "cap_employed_avg": cap_employed,
                "methodology": roce_methodology,
            }

            # ── Disaggregated Debt Ratios ──
            # gross_de_ratio: total debt (including leases) / equity
            # net_de_ratio:   (total debt - cash) / equity
            # financial_de_ratio: financial debt only (ex-lease liabilities) / equity
            # debt_to_ebitda: total debt / TTM EBITDA
            financial_debt = (
                (getattr(q0, 'financial_debt_lt', None) or 0.0)
                + (getattr(q0, 'financial_debt_st', None) or 0.0)
            )
            net_debt = total_debt - cash

            if net_worth > 0:
                features["gross_de_ratio"] = round(total_debt / net_worth, 2)
                features["net_de_ratio"] = round(net_debt / net_worth, 2)
                features["financial_de_ratio"] = round(financial_debt / net_worth, 2) if financial_debt >= 0 else None
                features["debt_to_equity"] = features["gross_de_ratio"]  # backward compat alias
            else:
                features["gross_de_ratio"] = None
                features["net_de_ratio"] = None
                features["financial_de_ratio"] = None
                features["debt_to_equity"] = None

            features["debt_to_ebitda"] = round(total_debt / ttm_ebitda, 2) if (ttm_ebitda and ttm_ebitda > 0) else None
            features["net_cash_position"] = round(-net_debt, 2)  # positive = net cash, negative = net debt

            # ── Free Cash Flow TTM (OCF - CapEx) ──
            if ttm_ocf is not None:
                features["ttm_fcf"] = round(ttm_ocf - (ttm_capex or 0.0), 2)
                features["ocf_to_pat"] = round(ttm_ocf / ttm_pat, 2) if ttm_pat > 0 else None
            else:
                features["ttm_fcf"] = None
                features["ocf_to_pat"] = None

            features["shares_outstanding"] = q0.shares_outstanding
            features["consolidation_scope"] = getattr(q0, 'consolidation_scope', 'CONSOLIDATED')

        else:
            features.update({
                "latest_revenue": None, "latest_pat": None, "ttm_revenue": None,
                "ttm_pat": None, "ttm_ebit": None, "ebitda_margin": None,
                "pat_margin": None, "revenue_yoy_growth_pct": None, "pat_yoy_growth_pct": None,
                "gross_de_ratio": None, "net_de_ratio": None, "financial_de_ratio": None,
                "debt_to_equity": None, "debt_to_ebitda": None, "net_cash_position": None,
                "roce_pct": None, "roce_methodology": "UNAVAILABLE", "roce_quarantine_flag": True,
                "roce_raw_inputs": None, "ttm_fcf": None, "ocf_to_pat": None,
                "shares_outstanding": None, "consolidation_scope": None,
                "ttm_consolidation_scope_flag": None
            })

        # ──────────────────────────────────────────────────────────────
        # 2. Technical Features (Split-adjusted prices strictly <= as_of_date)
        # ──────────────────────────────────────────────────────────────
        start_price_date = as_of_date - timedelta(days=400)
        adj_prices = PriceAdjuster.get_adjusted_prices(
            db, company_id, start_price_date, as_of_date, as_of_date=as_of_date
        )

        if len(adj_prices) >= 20:
            closes = [p["adj_close"] for p in adj_prices]
            highs = [p["adj_high"] for p in adj_prices]
            lows = [p["adj_low"] for p in adj_prices]
            volumes = [p["volume"] for p in adj_prices]

            current_close = closes[-1]
            features["close_price"] = current_close

            # Valuation metrics using real price and shares
            shares = features.get("shares_outstanding")
            if shares and shares > 0 and current_close:
                # Market Cap in Crores = (Close * Shares) / 10,000,000
                mcap_cr = (current_close * shares) / 10_000_000.0
                
                # Sanity guard: mcap should be reasonable relative to revenue
                # If mcap < 0.1x TTM revenue, likely data quality issue (wrong shares unit, stale price, etc.)
                ttm_revenue = features.get("ttm_revenue")
                if ttm_revenue and ttm_revenue > 0 and mcap_cr < (ttm_revenue * 0.1):
                    logger.warning(
                        f"[FeatureEngine] {company_id} mcap_cr={mcap_cr:.2f} Cr implausibly small "
                        f"(< 0.1x TTM revenue {ttm_revenue:.2f} Cr). Nullifying mcap/PE/PB."
                    )
                    features["market_cap_crores"] = None
                    features["pe_ratio"] = None
                    features["pb_ratio"] = None
                else:
                    features["market_cap_crores"] = round(mcap_cr, 2)

                    ttm_pat = features.get("ttm_pat")
                    if ttm_pat and ttm_pat > 0:
                        features["pe_ratio"] = round(mcap_cr / ttm_pat, 2)
                    else:
                        features["pe_ratio"] = None

                    net_worth = financials[0].net_worth if financials and financials[0].net_worth else None
                    if net_worth and net_worth > 0:
                        features["pb_ratio"] = round(mcap_cr / net_worth, 2)
                    else:
                        features["pb_ratio"] = None
            else:
                features["market_cap_crores"] = None
                features["pe_ratio"] = None
                features["pb_ratio"] = None

            # Moving Averages
            sma_20 = sum(closes[-20:]) / 20.0
            sma_50 = sum(closes[-TRADING_DAYS_50:]) / min(len(closes), TRADING_DAYS_50) if len(closes) >= TRADING_DAYS_50 else None
            sma_200 = sum(closes[-TRADING_DAYS_200:]) / min(len(closes), TRADING_DAYS_200) if len(closes) >= TRADING_DAYS_200 else None

            features["sma_20"] = round(sma_20, 2)
            features["sma_50"] = round(sma_50, 2) if sma_50 else None
            features["sma_200"] = round(sma_200, 2) if sma_200 else None
            features["dist_from_sma20_pct"] = round(((current_close - sma_20) / sma_20) * 100, 2) if sma_20 else None
            features["dist_from_sma50_pct"] = round(((current_close - sma_50) / sma_50) * 100, 2) if sma_50 else None
            features["dist_from_sma200_pct"] = round(((current_close - sma_200) / sma_200) * 100, 2) if sma_200 else None

            # Wilder's 14-period Exponential Smoothed RSI
            features["rsi_14"] = FeatureEngine._calculate_wilder_rsi(closes, period=14)

            # 14-day Average True Range (ATR)
            atr, atr_pct = FeatureEngine._calculate_atr(highs, lows, closes, period=14)
            features["atr_14"] = round(atr, 2)
            features["atr_pct"] = round(atr_pct, 2)

            # 52-week High & Low from actual intraday adjusted Highs/Lows
            lookback_len = min(len(adj_prices), TRADING_DAYS_PER_YEAR)
            high_52w = max(highs[-lookback_len:])
            low_52w = min(lows[-lookback_len:])

            features["high_52w"] = round(high_52w, 2)
            features["low_52w"] = round(low_52w, 2)
            features["dist_from_52w_high_pct"] = round(((current_close - high_52w) / high_52w) * 100, 2)
            features["dist_from_52w_low_pct"] = round(((current_close - low_52w) / low_52w) * 100, 2) if low_52w > 0 else 0.0

            # Volume Acceleration (20-day avg vol vs 50-day avg vol)
            avg_vol_20 = sum(volumes[-20:]) / 20.0
            avg_vol_50 = sum(volumes[-TRADING_DAYS_50:]) / min(len(volumes), TRADING_DAYS_50) if len(volumes) >= TRADING_DAYS_50 else avg_vol_20
            features["volume_acceleration_ratio"] = round(avg_vol_20 / avg_vol_50, 2) if avg_vol_50 > 0 else 1.0

        else:
            features.update({
                "close_price": None, "market_cap_crores": None, "pe_ratio": None, "pb_ratio": None,
                "sma_20": None, "sma_50": None, "sma_200": None,
                "dist_from_sma20_pct": None, "dist_from_sma50_pct": None,
                "dist_from_sma200_pct": None, "rsi_14": None, "atr_14": None, "atr_pct": None,
                "high_52w": None, "low_52w": None, "dist_from_52w_high_pct": None,
                "dist_from_52w_low_pct": None, "volume_acceleration_ratio": None
            })

        return features

    @staticmethod
    def _calculate_wilder_rsi(closes: List[float], period: int = 14) -> float:
        """
        Calculates classic 14-period Wilder Smoothed Relative Strength Index.
        """
        if len(closes) < period + 1:
            return 50.0

        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [max(0.0, d) for d in deltas]
        losses = [max(0.0, -d) for d in deltas]

        # First average
        avg_gain = sum(gains[:period]) / float(period)
        avg_loss = sum(losses[:period]) / float(period)

        # Smoothed Wilder EMA for subsequent values
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / float(period)
            avg_loss = (avg_loss * (period - 1) + losses[i]) / float(period)

        if avg_loss == 0.0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return round(max(0.0, min(100.0, rsi)), 2)

    @staticmethod
    def _calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Tuple[float, float]:
        """
        Calculates 14-day Average True Range (ATR) and ATR percentage of current close.
        """
        if len(closes) < 2:
            return 0.0, 0.0

        true_ranges = []
        for i in range(1, len(closes)):
            h = highs[i]
            l = lows[i]
            prev_c = closes[i - 1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            true_ranges.append(tr)

        if not true_ranges:
            return 0.0, 0.0

        lookback = min(len(true_ranges), period)
        atr = sum(true_ranges[-lookback:]) / float(lookback)
        current_close = closes[-1] if closes[-1] > 0 else 1.0
        atr_pct = (atr / current_close) * 100.0

        return atr, atr_pct

    @staticmethod
    def _find_yoy_quarter(financials: List[Any], current_period_end: date) -> Optional[Any]:
        """
        Find the same quarter from the prior year by strictly matching month AND year.

        Strategy (in order of preference):
        1. Exact month match in prior year (e.g., Jun-2025 → Jun-2024).
        2. Same quarter boundary: accept if the candidate's month is within the same
           calendar quarter (±0 quarters, prior year).

        The old index-based fallback (financials[4]) is removed — it silently returned
        the wrong quarter whenever the filing list had gaps or irregular dates, producing
        incorrect YoY growth figures without any warning.
        """
        target_month = current_period_end.month
        target_year = current_period_end.year - 1

        # Pass 1: exact month + exact prior year
        for f in financials[1:]:
            if f.period_end_date.year == target_year and f.period_end_date.month == target_month:
                return f

        # Pass 2: same calendar quarter in prior year (months within the same Q boundary)
        # Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec
        def _quarter(m: int) -> int:
            return (m - 1) // 3

        target_q = _quarter(target_month)
        for f in financials[1:]:
            if f.period_end_date.year == target_year and _quarter(f.period_end_date.month) == target_q:
                return f

        # No valid YoY match found — return None rather than silently using wrong data
        return None
