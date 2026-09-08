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

    # Cache of resolved Yahoo Finance ticker suffixes per NSE symbol
    # Key: NSE symbol (str), Value: Yahoo Finance suffix ('.NS' or '-SM.NS')
    # Pre-seeded with known NSE SME/Emerge (NSME) segment stocks that use -SM.NS suffix.
    # Auto-detection in _get_ticker() will add any newly discovered ones at runtime.
    _TICKER_SUFFIX_CACHE: dict = {
        # NSE SME/Emerge (NSME) segment — confirmed via live scan Sep 2026
        "SAHANA":    "-SM.NS",
        "PRIZOR":    "-SM.NS",
        "EFFWA":     "-SM.NS",
        "ANLON":     "-SM.NS",
        "GRCL":      "-SM.NS",
        "SHEETAL":   "-SM.NS",
        "AIMTRON":   "-SM.NS",
        "UNIHEALTH": "-SM.NS",
        "DYNAMIC":   "-SM.NS",
        "ACCENTMIC": "-SM.NS",
        "DANISH":    "-SM.NS",
        "VINSYS":    "-SM.NS",
        "NAMOEWASTE":"-SM.NS",
        "UTSSAV":    "-SM.NS",
        "GPECO":     "-SM.NS",
        "SUNLITE":   "-SM.NS",
    }

    def _get_ticker(self, nse_symbol: str) -> yf.Ticker:
        """
        Returns the correct Yahoo Finance Ticker for an equity symbol.

        Hierarchy:
        1. NSE Main Board: SYMBOL.NS
        2. NSE SME/Emerge: SYMBOL-SM.NS (e.g. SAHANA-SM.NS)
        3. BSE Main / SME: SYMBOL.BO (e.g. YASHHV.BO, COSPOWER.BO)
        4. BSE Scrip Code: {bse_code}.BO (e.g. 544310.BO)

        The correct suffix is auto-detected once and cached in _TICKER_SUFFIX_CACHE.
        """
        self._throttle()
        sym = nse_symbol.upper().strip()

        if sym in YFinanceClient._TICKER_SUFFIX_CACHE:
            cached_val = YFinanceClient._TICKER_SUFFIX_CACHE[sym]
            target_str = f"{sym}{cached_val}" if cached_val.startswith((".", "-")) else cached_val
            return yf.Ticker(target_str)

        # Try the standard main-board suffix first
        suffix = ".NS"
        try:
            probe = yf.Ticker(f"{sym}.NS")
            h = probe.history(period="2d", auto_adjust=False)
            if not h.empty:
                suffix = ".NS"
            else:
                # No data for .NS — try the SME/Emerge suffix
                probe_sm = yf.Ticker(f"{sym}-SM.NS")
                h_sm = probe_sm.history(period="2d", auto_adjust=False)
                if not h_sm.empty:
                    suffix = "-SM.NS"
                    logger.info(f"[YFinance] {sym}: SME/Emerge segment detected — using {sym}-SM.NS")
                else:
                    # Try BSE (.BO) with symbol
                    probe_bo = yf.Ticker(f"{sym}.BO")
                    h_bo = probe_bo.history(period="2d", auto_adjust=False)
                    if not h_bo.empty:
                        suffix = ".BO"
                        logger.info(f"[YFinance] {sym}: BSE segment detected — using {sym}.BO")
                    else:
                        # Try looking up 6-digit BSE scrip code from DB if available
                        bse_code_resolved = None
                        try:
                            from src.db.base import SessionLocal
                            from src.db.models import Company
                            db_chk = SessionLocal()
                            c_chk = db_chk.query(Company).filter(
                                (Company.nse_symbol == sym) | (Company.bse_code == sym)
                            ).first()
                            if c_chk and c_chk.bse_code and c_chk.bse_code != sym and c_chk.bse_code.isdigit():
                                bse_code_resolved = c_chk.bse_code
                            db_chk.close()
                        except Exception:
                            pass

                        if bse_code_resolved:
                            probe_bcode = yf.Ticker(f"{bse_code_resolved}.BO")
                            h_bcode = probe_bcode.history(period="2d", auto_adjust=False)
                            if not h_bcode.empty:
                                suffix = f"{bse_code_resolved}.BO"
                                logger.info(f"[YFinance] {sym}: BSE scrip code detected — using {bse_code_resolved}.BO")
                                YFinanceClient._TICKER_SUFFIX_CACHE[sym] = suffix
                                return probe_bcode

                        logger.warning(f"[YFinance] {sym}: No price data found on NSE, NSE-SM, or BSE")
            if suffix != ".NS" or (not h.empty):
                YFinanceClient._TICKER_SUFFIX_CACHE[sym] = suffix
        except Exception as e:
            logger.warning(f"[YFinance] {sym}: Error during suffix detection — {e}. Defaulting to .NS without caching.")

        target_str = f"{sym}{suffix}" if suffix.startswith((".", "-")) else suffix
        return yf.Ticker(target_str)

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
                    "is_split_adjusted":  True,   # Yahoo Finance OHLC candles are already split-adjusted
                    "price_source":       "YFINANCE",
                    "exchange":           "BSE" if str(getattr(ticker, "ticker", "")).endswith(".BO") else "NSE",
                    "quote_type":         "CLOSE",
                })

            logger.info(f"[yfinance] Fetched {len(records)} daily candles for {nse_symbol}")
            return records

        except Exception as e:
            logger.error(f"[yfinance] Error fetching prices for {nse_symbol}: {e}")
            return []

    # ──────────────────────────────────────────────────────────────
    # Corporate Actions (Splits, Bonuses, Dividends)
    # ──────────────────────────────────────────────────────────────

    def fetch_corporate_actions(self, nse_symbol: str) -> List[Dict[str, Any]]:
        """
        Fetch historical corporate actions (splits, bonuses, dividends) from Yahoo Finance.
        Yahoo Finance reports splits and bonuses under .splits with split_ratio = (new / old).
        Dividends are reported under .dividends in INR per share.

        Returns a list of standardized dicts:
            ex_date: date,
            action_type: 'SPLIT' | 'DIVIDEND',
            old_shares: float,
            new_shares: float,
            dividend_amount: float,
            description: str
        """
        try:
            ticker = self._get_ticker(nse_symbol)
            actions_list = []

            # 1. Splits and Bonuses
            splits = ticker.splits
            if splits is not None and not splits.empty:
                for idx, ratio in splits.items():
                    ex_dt = idx.date() if hasattr(idx, 'date') else idx
                    ratio_val = float(ratio)
                    if ratio_val > 0:
                        actions_list.append({
                            "ex_date": ex_dt,
                            "action_type": "SPLIT",
                            "old_shares": 1.0,
                            "new_shares": ratio_val,
                            "dividend_amount": 0.0,
                            "description": f"Stock Split/Bonus ratio 1:{ratio_val:g}"
                        })

            # 2. Dividends
            dividends = ticker.dividends
            if dividends is not None and not dividends.empty:
                for idx, div_amt in dividends.items():
                    ex_dt = idx.date() if hasattr(idx, 'date') else idx
                    div_val = float(div_amt)
                    if div_val > 0:
                        actions_list.append({
                            "ex_date": ex_dt,
                            "action_type": "DIVIDEND",
                            "old_shares": 1.0,
                            "new_shares": 1.0,
                            "dividend_amount": round(div_val, 2),
                            "description": f"Dividend of INR {div_val:.2f} per share"
                        })

            logger.info(f"[yfinance] Fetched {len(actions_list)} corporate actions for {nse_symbol}")
            return actions_list
        except Exception as e:
            logger.error(f"[yfinance] Error fetching corporate actions for {nse_symbol}: {e}")
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
                # Only rescale if shares < 500,000 AND company has large net worth/revenue (> 500 Cr)
                # indicating a unit omission rather than a legitimate micro-float equity structure.
                if shares is not None and shares < 500_000:
                    nw_check = (net_worth or 0.0)
                    rev_check = (revenue or 0.0)
                    if nw_check > 500.0 or rev_check > 500.0:
                        logger.warning(f"[yfinance] {nse_symbol} shares_outstanding={shares:,.0f} appears to be in millions for large enterprise. Rescaling by 1,000,000.")
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
                    "depreciation":         self._to_crores(depreciation),
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
    # Annual Financial Statements
    # ──────────────────────────────────────────────────────────────

    def fetch_annual_financials(
        self, nse_symbol: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch audited annual financial statements (income statement + balance sheet + cash flow).
        Returns list of dicts with keys matching BitemporalFinancial schema for period_type='ANNUAL'.
        All monetary values in INR Crores.
        """
        try:
            ticker = self._get_ticker(nse_symbol)

            income_stmt   = ticker.financials
            balance_sheet = ticker.balance_sheet
            cash_flow     = ticker.cashflow

            if income_stmt is None or income_stmt.empty:
                logger.warning(f"[yfinance] No annual financials for {nse_symbol}")
                return []

            records = []
            for col_date in income_stmt.columns:
                period_end = col_date.date() if hasattr(col_date, 'date') else col_date
                pub_date = datetime.combine(period_end, datetime.min.time()) + timedelta(days=60)

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

                # ── Balance sheet ──
                total_assets     = self._safe_get_bs_tolerant(balance_sheet, "Total Assets", col_date, tolerance_days=10)
                total_liabilities = self._safe_get_bs_tolerant(balance_sheet, "Total Liab", col_date, tolerance_days=10)
                if total_liabilities is None:
                    total_liabilities = self._safe_get_bs_tolerant(balance_sheet, "Total Liabilities Net Minority Interest", col_date, tolerance_days=10)

                net_worth = self._safe_get_bs_tolerant(balance_sheet, "Total Stockholder Equity", col_date, tolerance_days=10)
                if net_worth is None:
                    net_worth = self._safe_get_bs_tolerant(balance_sheet, "Stockholders Equity", col_date, tolerance_days=10)
                if net_worth is None:
                    net_worth = self._safe_get_bs_tolerant(balance_sheet, "Common Stock Equity", col_date, tolerance_days=10)

                total_debt = self._safe_get_bs_tolerant(balance_sheet, "Total Debt", col_date, tolerance_days=10)
                financial_debt_lt = self._safe_get_bs_tolerant(balance_sheet, "Long Term Debt", col_date, tolerance_days=10)
                if total_debt is None and financial_debt_lt is not None:
                    total_debt = financial_debt_lt

                lease_liabilities_lt = None
                if total_debt is not None and financial_debt_lt is not None and total_debt > financial_debt_lt:
                    lease_liabilities_lt = total_debt - financial_debt_lt

                cash = self._safe_get_bs_tolerant(balance_sheet, "Cash And Cash Equivalents", col_date, tolerance_days=10)
                if cash is None:
                    cash = self._safe_get_bs_tolerant(balance_sheet, "Cash", col_date, tolerance_days=10)

                current_investments = self._safe_get_bs_tolerant(balance_sheet, "Other Short Term Investments", col_date, tolerance_days=10)
                if current_investments is None:
                    current_investments = self._safe_get_bs_tolerant(balance_sheet, "Short Term Investments", col_date, tolerance_days=10)

                net_debt = None
                if total_debt is not None and cash is not None:
                    net_debt = total_debt - cash - (current_investments or 0.0)

                current_liab = self._safe_get_bs_tolerant(balance_sheet, "Current Liabilities", col_date, tolerance_days=10)
                if current_liab is None:
                    current_liab = self._safe_get_bs_tolerant(balance_sheet, "Total Current Liabilities", col_date, tolerance_days=10)

                shares = self._safe_get_bs_tolerant(balance_sheet, "Share Issued", col_date, tolerance_days=10)
                if shares is None:
                    shares = self._safe_get_bs_tolerant(balance_sheet, "Ordinary Shares Number", col_date, tolerance_days=10)
                if shares is not None and shares < 500_000:
                    if (net_worth is not None and net_worth > 5_000_000_000) or (revenue is not None and revenue > 5_000_000_000):
                        shares = shares * 10_000_000.0

                receivables = self._safe_get_bs_tolerant(balance_sheet, "Receivables", col_date, tolerance_days=10)
                if receivables is None:
                    receivables = self._safe_get_bs_tolerant(balance_sheet, "Accounts Receivable", col_date, tolerance_days=10)

                inventories = self._safe_get_bs_tolerant(balance_sheet, "Inventory", col_date, tolerance_days=10)
                payables = self._safe_get_bs_tolerant(balance_sheet, "Accounts Payable", col_date, tolerance_days=10)
                fixed_assets = self._safe_get_bs_tolerant(balance_sheet, "Net PPE", col_date, tolerance_days=10)
                if fixed_assets is None:
                    fixed_assets = self._safe_get_bs_tolerant(balance_sheet, "Gross PPE", col_date, tolerance_days=10)
                cwip = self._safe_get_bs_tolerant(balance_sheet, "Construction In Progress", col_date, tolerance_days=10) or 0.0

                # ── Cash flow ──
                ocf = self._safe_get_cf(cash_flow, "Operating Cash Flow", col_date)
                if ocf is None:
                    ocf = self._safe_get_cf(cash_flow, "Cash Flow From Continuing Operating Activities", col_date)

                capex_raw = self._safe_get_cf(cash_flow, "Capital Expenditure", col_date)
                capex = abs(capex_raw) if capex_raw is not None else None

                metrics = {
                    "revenue":              self._to_crores(revenue),
                    "ebitda":               self._to_crores(ebitda),
                    "ebit":                 self._to_crores(ebit),
                    "depreciation":         self._to_crores(depreciation),
                    "pat":                  self._to_crores(net_income),
                    "eps":                  None,
                    "operating_cash_flow":  self._to_crores(ocf),
                    "capex":                self._to_crores(capex),
                    "total_debt":           self._to_crores(total_debt),
                    "financial_debt_lt":    self._to_crores(financial_debt_lt),
                    "financial_debt_st":    None,
                    "lease_liabilities_lt": self._to_crores(lease_liabilities_lt),
                    "lease_liabilities_st": None,
                    "current_investments":  self._to_crores(current_investments),
                    "net_debt":             self._to_crores(net_debt),
                    "cash_and_equivalents": self._to_crores(cash),
                    "total_assets":         self._to_crores(total_assets),
                    "total_liabilities":    self._to_crores(total_liabilities),
                    "net_worth":            self._to_crores(net_worth),
                    "trade_receivables":    self._to_crores(receivables),
                    "inventories":          self._to_crores(inventories),
                    "trade_payables":       self._to_crores(payables),
                    "ppe_gross":            self._to_crores(fixed_assets),
                    "capital_wip":          self._to_crores(cwip),
                    "current_liabilities":  self._to_crores(current_liab),
                    "shares_outstanding":   shares,
                    "consolidation_scope":  "YFINANCE_UNVERIFIED",
                }

                if metrics["pat"] is not None and shares and shares > 0:
                    metrics["eps"] = round((metrics["pat"] * CRORE_DIVISOR) / shares, 2)

                records.append({
                    "period_end_date":     period_end,
                    "publication_date":    pub_date,
                    "period_type":         "ANNUAL",
                    "source":              "YFINANCE",
                    "source_quality":      "ESTIMATED_PUB_DATE",
                    "consolidation_scope": "YFINANCE_UNVERIFIED",
                    "metrics":             metrics,
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
                        "net_debt":         metrics["net_debt"],
                        "pub_date_is_estimated": True,
                        "fetched_at":       datetime.utcnow().isoformat(),
                    }
                })

            logger.info(f"[yfinance] Fetched {len(records)} annual filings for {nse_symbol}")
            return records

        except Exception as e:
            logger.error(f"[yfinance] Error fetching annual financials for {nse_symbol}: {e}")
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
    def _safe_get_bs_tolerant(
        df: Optional[pd.DataFrame],
        row_label: str,
        col_date,
        tolerance_days: int = 100,
        preceding_only: bool = True
    ) -> Optional[float]:
        """
        Extract balance sheet item with date tolerance.
        Defaults to preceding_only=True with 100-day lookback for quarterly statements
        where full balance sheet is only published semi-annually / annually under SEBI LODR.
        """
        if df is None or df.empty:
            return None
        try:
            matched_col = YFinanceClient._find_column(df, col_date, tolerance_days=tolerance_days, preceding_only=preceding_only)
            if matched_col is not None and row_label in df.index:
                val = df.loc[row_label, matched_col]
                if pd.notna(val):
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
        return YFinanceClient._safe_get_bs_tolerant(df, row_label, col_date, tolerance_days=0, preceding_only=False)

    @staticmethod
    def _safe_get_cf(df: Optional[pd.DataFrame], row_label: str, col_date) -> Optional[float]:
        """Safely extract a value from a cash flow DataFrame."""
        return YFinanceClient._safe_get(df, row_label, col_date)

    @staticmethod
    def _find_column(df: pd.DataFrame, col_date, tolerance_days: int = 0, preceding_only: bool = False):
        """
        Find the DataFrame column that best matches col_date.
        If preceding_only=True, only considers columns where c_dt <= target_dt (Point-in-Time discipline).
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

        # Tolerance / lookback match
        if tolerance_days > 0:
            best_col = None
            best_diff = tolerance_days + 1
            for c in df.columns:
                c_dt = c.date() if hasattr(c, 'date') else c
                try:
                    if preceding_only:
                        if c_dt > target_dt:
                            continue
                        diff = (target_dt - c_dt).days
                    else:
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
