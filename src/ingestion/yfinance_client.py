"""
YFinance Data Client — Secondary data source for OHLCV + Financials + Corporate Actions.

Uses the yfinance library to fetch market data from Yahoo Finance.
Indian NSE stocks use the '.NS' suffix (e.g., 'RELIANCE.NS').

IMPORTANT DATA QUALITY NOTES:
1. Publication dates for financial filings are ESTIMATED as period_end + 35-60 days.
   They are NOT the actual NSE XBRL filing dates. Every record is tagged
   source_quality="ESTIMATED_PUB_DATE". NSE corporate announcements API should be
   used to cross-reference and replace these with actual publication dates.

2. consolidation_scope is UNVERIFIED. yfinance returns consolidated results for
   most large-cap Indian stocks, but may return standalone for others without
   explicit indication. Tag: "YFINANCE_UNVERIFIED".

3. total_debt from yfinance "Total Debt" row includes IND-AS 116 lease liabilities
   for Indian companies. financial_debt_lt/st are extracted separately where possible.

4. All prices returned are raw/unadjusted (auto_adjust=False).
   Every price record is tagged is_split_adjusted=False.
   Callers MUST use PriceAdjuster before using prices in any ratio or chart.

Financial values are converted to INR Crores (÷ 10,000,000).
"""

import logging
import time
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

import yfinance as yf
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CRORE_DIVISOR = 10_000_000.0


class YFinanceClient:
    """
    Fetches market data from Yahoo Finance for Indian NSE equities.
    All financial values returned in INR Crores (except EPS which is INR per share).
    All prices are RAW/UNADJUSTED — callers must apply PriceAdjuster.
    """

    def __init__(self, rate_limit_seconds: float = 1.0):
        self.rate_limit_seconds = rate_limit_seconds
        self._last_request_time: float = 0.0

    def _throttle(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self._last_request_time = time.time()

    def _get_ticker(self, nse_symbol: str) -> yf.Ticker:
        self._throttle()
        yahoo_symbol = f"{nse_symbol}.NS"
        return yf.Ticker(yahoo_symbol)

    # ──────────────────────────────────────────────────────────────
    # OHLCV Price Data
    # ──────────────────────────────────────────────────────────────

    def fetch_daily_prices(
        self, nse_symbol: str, start_date: date, end_date: date
    ) -> List[Dict[str, Any]]:
        """
        Fetch daily OHLCV price data for an NSE stock.

        IMPORTANT: Returns RAW unadjusted prices (is_split_adjusted=False).
        Callers MUST use PriceAdjuster before using these prices for any
        analysis, ratio, or chart. Never use raw close prices directly.

        Returns list of dicts with keys:
            trading_date, open_price, high_price, low_price, close_price,
            volume, turnover, deliverable_volume, delivery_pct,
            is_split_adjusted, price_source
        """
        try:
            ticker = self._get_ticker(nse_symbol)
            hist = ticker.history(
                start=start_date.isoformat(),
                end=(end_date + timedelta(days=1)).isoformat(),
                auto_adjust=False  # Raw unadjusted prices — PriceAdjuster handles splits
            )

            if hist.empty:
                logger.warning(f"[yfinance] No price data returned for {nse_symbol}")
                return []

            records = []
            for idx, row in hist.iterrows():
                trading_dt = idx.date() if hasattr(idx, 'date') else idx
                open_p  = round(float(row["Open"]),   2)
                high_p  = round(float(row["High"]),   2)
                low_p   = round(float(row["Low"]),    2)
                close_p = round(float(row["Close"]),  2)
                vol     = int(row["Volume"])
                turnover = round(close_p * vol, 2) if vol > 0 else 0.0

                records.append({
                    "trading_date":       trading_dt,
                    "open_price":         open_p,
                    "high_price":         high_p,
                    "low_price":          low_p,
                    "close_price":        close_p,
                    "volume":             vol,
                    "turnover":           turnover,
                    # Deliverable volume is NOT available from yfinance.
                    # Set None — never fabricate as a fixed % of volume.
                    "deliverable_volume": None,
                    "delivery_pct":       None,
                    # Provenance fields
                    "is_split_adjusted":  False,   # Raw price — must apply PriceAdjuster
                    "price_source":       "YFINANCE",
                    "exchange":           "NSE",
                    "quote_type":         "CLOSE",
                })

            logger.info(f"[yfinance] Fetched {len(records)} daily candles for {nse_symbol}")
            return records

        except Exception as e:
            logger.error(f"[yfinance] Error fetching prices for {nse_symbol}: {e}")
            return []

    # ──────────────────────────────────────────────────────────────
    # Quarterly Financial Statements
    # ──────────────────────────────────────────────────────────────

    def fetch_quarterly_financials(
        self, nse_symbol: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch quarterly financial statements (income statement + balance sheet + cash flow).

        DATA QUALITY NOTES:
        - publication_date is ESTIMATED as period_end + 35 days for Q1/Q2/Q3
          and period_end + 60 days for Q4 (annual results). Tag: ESTIMATED_PUB_DATE.
          This is NOT the actual NSE XBRL filing date.
        - consolidation_scope is YFINANCE_UNVERIFIED. The actual scope (consolidated
          vs standalone) cannot be reliably determined from yfinance for all stocks.
        - total_debt from yfinance includes IND-AS 116 lease liabilities.
          financial_debt_lt is extracted separately from "Long Term Debt" if available.

        Returns list of dicts with keys matching BitemporalFinancial schema.
        All monetary values in INR Crores.
        """
        try:
            ticker = self._get_ticker(nse_symbol)

            income_stmt  = ticker.quarterly_financials
            balance_sheet = ticker.quarterly_balance_sheet
            cash_flow    = ticker.quarterly_cashflow

            if income_stmt is None or income_stmt.empty:
                logger.warning(f"[yfinance] No quarterly financials for {nse_symbol}")
                return []

            records = []
            for col_date in income_stmt.columns:
                period_end = col_date.date() if hasattr(col_date, 'date') else col_date

                # ── Income statement ──
                revenue = self._safe_get(income_stmt, "Total Revenue", col_date)
                if revenue is None:
                    revenue = self._safe_get(income_stmt, "Operating Revenue", col_date)

                ebitda = self._safe_get(income_stmt, "EBITDA", col_date)
                if ebitda is None:
                    ebitda = self._safe_get(income_stmt, "Normalized EBITDA", col_date)

                ebit = self._safe_get(income_stmt, "EBIT", col_date)
                if ebit is None:
                    ebit = self._safe_get(income_stmt, "Operating Income", col_date)

                net_income = self._safe_get(income_stmt, "Net Income", col_date)
                if net_income is None:
                    net_income = self._safe_get(income_stmt, "Net Income From Continuing Ops", col_date)
                if net_income is None:
                    net_income = self._safe_get(income_stmt, "Net Income Common Stockholders", col_date)

                depreciation = self._safe_get(income_stmt, "Reconciled Depreciation", col_date) or 0.0
                if ebitda is None and ebit is not None:
                    ebitda = ebit + depreciation

                # ── Balance sheet — with ±1 day tolerance for date matching ──
                total_assets     = self._safe_get_bs_tolerant(balance_sheet, "Total Assets", col_date)
                total_liabilities = self._safe_get_bs_tolerant(balance_sheet, "Total Liab", col_date)
                if total_liabilities is None:
                    total_liabilities = self._safe_get_bs_tolerant(balance_sheet, "Total Liabilities Net Minority Interest", col_date)

                net_worth = self._safe_get_bs_tolerant(balance_sheet, "Total Stockholder Equity", col_date)
                if net_worth is None:
                    net_worth = self._safe_get_bs_tolerant(balance_sheet, "Stockholders Equity", col_date)
                if net_worth is None:
                    net_worth = self._safe_get_bs_tolerant(balance_sheet, "Common Stock Equity", col_date)

                # total_debt: includes lease liabilities under IND-AS 116
                total_debt = self._safe_get_bs_tolerant(balance_sheet, "Total Debt", col_date)

                # financial_debt_lt: explicit long-term FINANCIAL debt only (ex lease liabilities)
                # "Long Term Debt" in yfinance = bank loans, NCDs, bonds (excludes IND-AS 116 leases)
                financial_debt_lt = self._safe_get_bs_tolerant(balance_sheet, "Long Term Debt", col_date)
                if total_debt is None and financial_debt_lt is not None:
                    total_debt = financial_debt_lt  # Use LT debt as proxy if Total Debt missing

                # Lease liabilities: difference between total_debt and financial_debt_lt (approximate)
                lease_liabilities_lt = None
                if total_debt is not None and financial_debt_lt is not None and total_debt > financial_debt_lt:
                    lease_liabilities_lt = total_debt - financial_debt_lt

                cash = self._safe_get_bs_tolerant(balance_sheet, "Cash And Cash Equivalents", col_date)
                if cash is None:
                    cash = self._safe_get_bs_tolerant(balance_sheet, "Cash", col_date)

                current_investments = self._safe_get_bs_tolerant(balance_sheet, "Other Short Term Investments", col_date)
                if current_investments is None:
                    current_investments = self._safe_get_bs_tolerant(balance_sheet, "Short Term Investments", col_date)

                # net_debt = total_debt - cash - current_investments
                net_debt = None
                if total_debt is not None and cash is not None:
                    net_debt = total_debt - cash - (current_investments or 0.0)

                current_liab = self._safe_get_bs_tolerant(balance_sheet, "Current Liabilities", col_date)
                if current_liab is None:
                    current_liab = self._safe_get_bs_tolerant(balance_sheet, "Total Current Liabilities", col_date)

                shares = self._safe_get_bs_tolerant(balance_sheet, "Share Issued", col_date)
                if shares is None:
                    shares = self._safe_get_bs_tolerant(balance_sheet, "Ordinary Shares Number", col_date)
                
                # Unit sanity check: yfinance sometimes returns shares in millions instead of absolute count
                # For Indian companies, shares < 500,000 is implausible (would imply tiny float)
                if shares is not None and shares < 500_000:
                    logger.warning(f"[yfinance] {nse_symbol} shares_outstanding={shares:,.0f} appears to be in millions. Rescaling by 1,000,000.")
                    shares = shares * 1_000_000

                receivables = self._safe_get_bs_tolerant(balance_sheet, "Receivables", col_date)
                if receivables is None:
                    receivables = self._safe_get_bs_tolerant(balance_sheet, "Accounts Receivable", col_date)
                if receivables is None:
                    receivables = self._safe_get_bs_tolerant(balance_sheet, "Net Receivables", col_date)

                # ── Cash flow ──
                ocf = self._safe_get_cf(cash_flow, "Operating Cash Flow", col_date)
                if ocf is None:
                    ocf = self._safe_get_cf(cash_flow, "Cash Flow From Continuing Operating Activities", col_date)

                capex = self._safe_get_cf(cash_flow, "Capital Expenditure", col_date)
                if capex is None:
                    capex = self._safe_get_cf(cash_flow, "Net PPE Purchase And Sale", col_date)
                if capex is not None:
                    capex = abs(capex)  # CapEx reported as negative in cash flow statement

                # ── Publication date estimation ──
                # Q4 (Mar 31 year-end) results typically take 45-60 days.
                # Q1/Q2/Q3 results typically take 30-45 days.
                # This is an ESTIMATE — tag as ESTIMATED_PUB_DATE.
                is_q4 = period_end.month == 3
                est_days = 55 if is_q4 else 42
                pub_date = datetime.combine(
                    period_end + timedelta(days=est_days),
                    datetime.min.time().replace(hour=18)
                )

                metrics = {
                    "revenue":              self._to_crores(revenue),
                    "ebitda":               self._to_crores(ebitda),
                    "ebit":                 self._to_crores(ebit),
                    "pat":                  self._to_crores(net_income),
                    "eps":                  None,
                    "operating_cash_flow":  self._to_crores(ocf),
                    "capex":                self._to_crores(capex),
                    "total_debt":           self._to_crores(total_debt),
                    "financial_debt_lt":    self._to_crores(financial_debt_lt),   # Financial debt only (ex leases)
                    "financial_debt_st":    None,                                  # Not available from yfinance
                    "lease_liabilities_lt": self._to_crores(lease_liabilities_lt), # Approximate: total_debt - LT debt
                    "lease_liabilities_st": None,                                  # Not available from yfinance
                    "current_investments":  self._to_crores(current_investments),
                    "net_debt":             self._to_crores(net_debt),
                    "cash_and_equivalents": self._to_crores(cash),
                    "total_assets":         self._to_crores(total_assets),
                    "total_liabilities":    self._to_crores(total_liabilities),
                    "net_worth":            self._to_crores(net_worth),
                    "trade_receivables":     self._to_crores(receivables),
                    "current_liabilities":  self._to_crores(current_liab),
                    "shares_outstanding":   shares,
                    # Consolidation scope: cannot verify from yfinance — tag as unverified
                    "consolidation_scope":  "YFINANCE_UNVERIFIED",
                }

                if metrics["pat"] is not None and shares and shares > 0:
                    metrics["eps"] = round((metrics["pat"] * CRORE_DIVISOR) / shares, 2)

                records.append({
                    "period_end_date":    period_end,
                    "publication_date":   pub_date,
                    "period_type":        "QUARTERLY",
                    "source":             "YFINANCE",
                    # Data quality metadata
                    "source_quality":     "ESTIMATED_PUB_DATE",  # publication_date is estimated, NOT actual NSE filing date
                    "consolidation_scope": "YFINANCE_UNVERIFIED",
                    "metrics":            metrics,
                    "raw_payload": {
                        "source":           "yfinance",
                        "symbol":           nse_symbol,
                        "revenue":          metrics["revenue"],
                        "pat":              metrics["pat"],
                        "ebit":             metrics["ebit"],
                        "ebitda":           metrics["ebitda"],
                        "ocf":              metrics["operating_cash_flow"],
                        "capex":            metrics["capex"],
                        "total_debt":       metrics["total_debt"],
                        "financial_debt_lt": metrics["financial_debt_lt"],
                        "lease_liabilities_lt": metrics["lease_liabilities_lt"],
                        "net_debt":         metrics["net_debt"],
                        "pub_date_is_estimated": True,
                        "fetched_at":       datetime.utcnow().isoformat(),
                    }
                })

            logger.info(f"[yfinance] Fetched {len(records)} quarterly filings for {nse_symbol}")
            return records

        except Exception as e:
            logger.error(f"[yfinance] Error fetching financials for {nse_symbol}: {e}")
            return []

    # ──────────────────────────────────────────────────────────────
    # Corporate Actions (Splits & Dividends)
    # ──────────────────────────────────────────────────────────────

    def fetch_corporate_actions(
        self, nse_symbol: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch stock splits and dividends from yfinance.
        Note: NSE client should be preferred for corporate actions as it provides
        official ex-date and record date from exchange records.
        """
        try:
            ticker = self._get_ticker(nse_symbol)
            actions = ticker.actions

            if actions is None or actions.empty:
                logger.info(f"[yfinance] No corporate actions for {nse_symbol}")
                return []

            records = []
            for idx, row in actions.iterrows():
                action_date = idx.date() if hasattr(idx, 'date') else idx

                if "Stock Splits" in row and row["Stock Splits"] != 0:
                    split_ratio = float(row["Stock Splits"])
                    if split_ratio > 0 and split_ratio != 1.0:
                        records.append({
                            "ex_date":        action_date,
                            "action_type":    "SPLIT",
                            "old_shares":     1.0,
                            "new_shares":     split_ratio,
                            "dividend_amount": 0.0,
                            "description":    f"Stock Split 1:{int(split_ratio)}" if split_ratio == int(split_ratio) else f"Stock Split 1:{split_ratio:.2f}",
                            "source":         "YFINANCE",
                        })

                if "Dividends" in row and row["Dividends"] > 0:
                    records.append({
                        "ex_date":        action_date,
                        "action_type":    "DIVIDEND",
                        "old_shares":     1.0,
                        "new_shares":     1.0,
                        "dividend_amount": float(row["Dividends"]),
                        "description":    f"Dividend ₹{float(row['Dividends']):.2f} per share",
                        "source":         "YFINANCE",
                    })

            logger.info(f"[yfinance] Fetched {len(records)} corporate actions for {nse_symbol}")
            return records

        except Exception as e:
            logger.error(f"[yfinance] Error fetching corporate actions for {nse_symbol}: {e}")
            return []

    # ──────────────────────────────────────────────────────────────
    # Company Metadata & Ratios
    # ──────────────────────────────────────────────────────────────

    def fetch_company_info(self, nse_symbol: str) -> Dict[str, Any]:
        """Fetch company metadata, real valuation ratios, and shares outstanding."""
        try:
            ticker = self._get_ticker(nse_symbol)
            info = ticker.info or {}

            mcap = info.get("marketCap")
            mcap_cr = self._to_crores(mcap) if mcap else None
            
            shares = info.get("sharesOutstanding")
            # Unit sanity check: yfinance sometimes returns shares in millions instead of absolute count
            if shares is not None and shares < 500_000:
                logger.warning(f"[yfinance] {nse_symbol} sharesOutstanding={shares:,.0f} appears to be in millions. Rescaling by 1,000,000.")
                shares = shares * 1_000_000

            return {
                "sector":               info.get("sector"),
                "industry":             info.get("industry"),
                "market_cap_crores":    mcap_cr,
                "shares_outstanding":   shares,
                "trailing_pe":          round(info.get("trailingPE"), 2) if info.get("trailingPE") else None,
                "forward_pe":           round(info.get("forwardPE"), 2) if info.get("forwardPE") else None,
                "price_to_book":        round(info.get("priceToBook"), 2) if info.get("priceToBook") else None,
                "enterprise_to_ebitda": round(info.get("enterpriseToEbitda"), 2) if info.get("enterpriseToEbitda") else None,
                "dividend_yield":       round(info.get("dividendYield", 0.0) * 100, 2) if info.get("dividendYield") else 0.0,
                "beta":                 round(info.get("beta"), 2) if info.get("beta") else None,
                "website":              info.get("website"),
                "description":          info.get("longBusinessSummary", "")[:500],
            }

        except Exception as e:
            logger.error(f"[yfinance] Error fetching info for {nse_symbol}: {e}")
            return {}

    # ──────────────────────────────────────────────────────────────
    # Helper Methods
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _safe_get(df: Optional[pd.DataFrame], row_label: str, col_date) -> Optional[float]:
        """Safely extract a value from an income statement or cash flow DataFrame."""
        if df is None or df.empty:
            return None
        try:
            matched_col = YFinanceClient._find_column(df, col_date, tolerance_days=0)
            if matched_col is not None and row_label in df.index:
                val = df.loc[row_label, matched_col]
                if pd.notna(val):
                    return float(val)
        except Exception:
            pass
        return None

    @staticmethod
    def _safe_get_bs_tolerant(df: Optional[pd.DataFrame], row_label: str, col_date, tolerance_days: int = 1) -> Optional[float]:
        """
        Safely extract a value from a balance sheet DataFrame with ±N day date tolerance.

        Balance sheet column dates sometimes differ from income statement dates by up to 1 day
        due to timezone handling in yfinance (e.g., 2026-03-31 vs 2026-04-01 UTC offset).
        The tolerance prevents silent None returns when the data is present but off by a day.
        """
        if df is None or df.empty:
            return None
        try:
            matched_col = YFinanceClient._find_column(df, col_date, tolerance_days=tolerance_days)
            if matched_col is not None and row_label in df.index:
                val = df.loc[row_label, matched_col]
                if pd.notna(val):
                    # Log if we had to use tolerance to find the match
                    matched_dt = matched_col.date() if hasattr(matched_col, 'date') else matched_col
                    target_dt  = col_date.date() if hasattr(col_date, 'date') else col_date
                    if matched_dt != target_dt:
                        logger.debug(
                            f"[yfinance] Balance sheet date tolerance used: "
                            f"requested {target_dt}, matched {matched_dt} for '{row_label}'"
                        )
                    return float(val)
        except Exception:
            pass
        return None

    @staticmethod
    def _safe_get_bs(df: Optional[pd.DataFrame], row_label: str, col_date) -> Optional[float]:
        """Exact-match balance sheet lookup (no tolerance). Use _safe_get_bs_tolerant for production."""
        return YFinanceClient._safe_get_bs_tolerant(df, row_label, col_date, tolerance_days=0)

    @staticmethod
    def _safe_get_cf(df: Optional[pd.DataFrame], row_label: str, col_date) -> Optional[float]:
        """Safely extract a value from a cash flow DataFrame."""
        return YFinanceClient._safe_get(df, row_label, col_date)

    @staticmethod
    def _find_column(df: pd.DataFrame, col_date, tolerance_days: int = 0):
        """
        Find the DataFrame column that best matches col_date, within ±tolerance_days.
        Returns the column key or None if not found.
        """
        target_dt = col_date.date() if hasattr(col_date, 'date') else col_date

        # Exact match first
        if col_date in df.columns:
            return col_date

        # Date-level exact match (ignoring time component)
        for c in df.columns:
            c_dt = c.date() if hasattr(c, 'date') else c
            if c_dt == target_dt:
                return c

        # Tolerance-based match
        if tolerance_days > 0:
            best_col = None
            best_diff = tolerance_days + 1
            for c in df.columns:
                c_dt = c.date() if hasattr(c, 'date') else c
                try:
                    diff = abs((c_dt - target_dt).days)
                    if diff <= tolerance_days and diff < best_diff:
                        best_diff = diff
                        best_col = c
                except Exception:
                    continue
            return best_col

        return None

    @staticmethod
    def _to_crores(value: Optional[float]) -> Optional[float]:
        """Convert absolute INR value to Crores."""
        if value is None:
            return None
        return round(value / CRORE_DIVISOR, 2)
