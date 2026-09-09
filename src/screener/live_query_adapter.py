"""
Live Query Adapter for External On-Demand Screening Endpoints.
Supports:
1. Screener.in cloud financial queries (with session reuse & graceful fallbacks)
2. Chartink technical moving average & VCP pattern scans
3. NSE master constituents queries
4. Built-in LRU cache & debouncing to prevent redundant network hits
"""

import time
import json
import logging
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# 60-Second In-Memory Query Cache
_QUERY_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 60.0


import re
import requests
from src.screener.missing_data_guard import MissingDataGuard

_CHARTINK_SESSION: Optional[requests.Session] = None
_CHARTINK_CSRF_TOKEN: Optional[str] = None
_CHARTINK_TOKEN_TIMESTAMP: float = 0.0
_LAST_SCAN_STATS: Dict[str, int] = {"total_count": 5000, "stage1_count": 4200}

class LiveQueryAdapter:
    """
    Connects to external screening engines (TradingView India Scanner & Chartink)
    for on-demand market-wide scanning across 5,000+ Indian equities.
    """

    @classmethod
    def get_last_scan_stats(cls) -> Dict[str, int]:
        """Returns the most recent live TradingView total match count and cohort size."""
        return dict(_LAST_SCAN_STATS)

    @classmethod
    def _get_chartink_session_and_token(cls) -> Tuple[Optional[requests.Session], Optional[str]]:
        global _CHARTINK_SESSION, _CHARTINK_CSRF_TOKEN, _CHARTINK_TOKEN_TIMESTAMP
        now = time.time()
        if _CHARTINK_SESSION is not None and _CHARTINK_CSRF_TOKEN is not None:
            if now - _CHARTINK_TOKEN_TIMESTAMP < 900.0:  # 15-minute token TTL
                return _CHARTINK_SESSION, _CHARTINK_CSRF_TOKEN

        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
            resp = session.get("https://chartink.com/screener/", timeout=4.0)
            token = None
            m = re.search(r'name=["\']csrf-token["\']\s+content=["\']([^"\']+)["\']', resp.text)
            if not m:
                m = re.search(r'content=["\']([^"\']+)["\']\s+name=["\']csrf-token["\']', resp.text)
            if m:
                token = m.group(1)

            if token:
                _CHARTINK_SESSION = session
                _CHARTINK_CSRF_TOKEN = token
                _CHARTINK_TOKEN_TIMESTAMP = now
                return session, token
        except Exception as e:
            logger.warning(f"Could not initialize Chartink CSRF session: {e}")

        return None, None

    @classmethod
    def query_chartink_technical_scan(
        cls,
        scan_clause: str
    ) -> List[Dict[str, Any]]:
        """
        Executes a technical / momentum scan via Chartink's API.
        Example scan clause:
        "( {33489} ( ( [0] 15 minute close > [0] 15 minute open and [0] 15 minute volume > [0] 15 minute sma( volume, 20 ) * 2 ) ) )"
        """
        cache_key = f"chartink_{scan_clause[:40]}"
        now = time.time()
        if cache_key in _QUERY_CACHE:
            entry = _QUERY_CACHE[cache_key]
            if now - entry["timestamp"] < CACHE_TTL_SECONDS:
                return entry["data"]

        session, csrf_token = cls._get_chartink_session_and_token()
        if not session or not csrf_token:
            return []

        post_headers = {
            "X-CSRF-TOKEN": csrf_token,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": "https://chartink.com/screener/"
        }
        url = "https://chartink.com/screener/process"

        try:
            response = session.post(
                url,
                data={"scan_clause": scan_clause},
                headers=post_headers,
                timeout=4.0
            )
            if response.status_code == 200:
                raw = response.json()
                items = raw.get("data", [])
                results = []
                for it in items:
                    results.append({
                        "symbol": it.get("nsecode", it.get("name", "")).upper(),
                        "name": it.get("name", ""),
                        "cmp": float(it.get("close", 0.0)),
                        "volume": float(it.get("volume", 0.0)),
                        "pct_change": float(it.get("per_chg", 0.0))
                    })
                _QUERY_CACHE[cache_key] = {"timestamp": now, "data": results}
                return results
        except Exception as e:
            logger.warning(f"Chartink query failed ({e}). Returning empty technical set.")

        return []

    @classmethod
    def query_tradingview_india_scanner(
        cls,
        req: Any,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Executes live real-time filtering across all 5,000+ Indian stocks via TradingView India Scanner API.
        Filters by Market Cap, ROCE, Debt/Equity, 52W High distance, Volume, and Stage 2 trend.
        """
        preset_name = getattr(req, "preset", "") or "CUSTOM"
        min_mcap = getattr(req, "min_market_cap_cr", 0.0) or 0.0
        max_mcap = getattr(req, "max_market_cap_cr", 0.0) or 0.0
        min_roce = getattr(req, "min_roce_pct", 0.0) or 0.0
        max_de = getattr(req, "max_debt_to_equity", 0.0) or 0.0
        near_52w = getattr(req, "near_52w_high_pct", 0.0) or 0.0
        min_growth = getattr(req, "min_sales_growth_3y_pct", 0.0) or 0.0
        st2 = getattr(req, "require_stage_2_uptrend", False)
        min_turnover = getattr(req, "min_daily_turnover_cr", 0.0) or 0.0

        cache_key = f"tv_{preset_name}_{min_mcap}_{max_mcap}_{min_roce}_{max_de}_{near_52w}_{min_growth}_{st2}_{limit}"
        now = time.time()

        # Evict expired entries to prevent unbounded memory growth
        expired_keys = [k for k, v in _QUERY_CACHE.items() if (now - v.get("timestamp", 0)) > CACHE_TTL_SECONDS * 2]
        for k in expired_keys:
            _QUERY_CACHE.pop(k, None)

        if cache_key in _QUERY_CACHE:
            entry = _QUERY_CACHE[cache_key]
            if now - entry["timestamp"] < CACHE_TTL_SECONDS:
                logger.debug(f"Serving TradingView scanner from cache: {cache_key}")
                return entry["data"]

        filters = [
            {"left": "exchange", "operation": "equal", "right": "NSE"},
            {"left": "type", "operation": "equal", "right": "stock"}
        ]
        
        # 1. Market Cap Filter (convert ₹ Cr to absolute INR by * 10^7)
        if min_mcap > 0:
            filters.append({"left": "market_cap_basic", "operation": "greater", "right": min_mcap * 10000000.0})
        if max_mcap > 0:
            filters.append({"left": "market_cap_basic", "operation": "less", "right": max_mcap * 10000000.0})

        # 2. Daily Turnover Liquidity Floor (if requested)
        if min_turnover > 0:
            filters.append({"left": "AvgValue.Traded_10d", "operation": "greater", "right": min_turnover * 10000000.0})

        # 3. Stage 2 Trend Template (Price > 50SMA > 200SMA)
        if st2:
            filters.append({"left": "close", "operation": "greater", "right": "SMA50"})
            filters.append({"left": "SMA50", "operation": "greater", "right": "SMA200"})

        # Two-Phase Hybrid Strategy:
        # Rather than dropping 94% of Indian companies by enforcing return_on_capital_employed_fq
        # directly in TradingView (since quarterly balance sheets are absent in semi-annual filing),
        # query TradingView with primary market filters and sort by strategy vector,
        # then apply strict deterministic Python Gating below using both FY and FQ metrics.
        sort_by = "market_cap_basic"
        sort_order = "desc"
        if "MULTIBAGGER" in preset_name:
            sort_by = "total_revenue_cagr_5y"
        elif "SWING" in preset_name:
            sort_by = "Perf.3M"
        elif "INTRADAY" in preset_name:
            sort_by = "relative_volume_10d_calc"
        elif "MICROCAP" in preset_name:
            sort_by = "total_revenue_cagr_5y"

        payload = {
            "filter": filters,
            "options": {"lang": "en"},
            "symbols": {"query": {"types": ["stock"]}},
            "columns": [
                "name",                         # 0
                "description",                  # 1
                "close",                        # 2
                "change",                       # 3
                "volume",                       # 4
                "market_cap_basic",             # 5
                "price_earnings_ttm",           # 6
                "return_on_capital_employed_fq",# 7
                "debt_to_equity_fq",            # 8
                "price_52_week_high",           # 9  (FIXED: canonical 52W high)
                "price_52_week_low",            # 10 (FIXED: canonical 52W low)
                "EMA50",                        # 11
                "EMA200",                       # 12
                "average_volume_10d_calc",      # 13
                "operating_margin_ttm",         # 14
                "net_margin_ttm",               # 15
                "total_revenue_yoy_growth_ttm", # 16
                "current_ratio_fq",             # 17
                "quick_ratio_fq",               # 18
                "ATR",                          # 19
                "relative_volume_10d_calc",     # 20
                "high",                         # 21
                "low",                          # 22
                "VWAP",                         # 23
                "High.1M",                      # 24 (2-4W swing pivot)
                "High.3M",                      # 25 (6-12W intermediate pivot)
                "SMA50",                        # 26 (Minervini Trend Template)
                "SMA150",                       # 27 (Minervini Trend Template)
                "SMA200",                       # 28 (Minervini Trend Template)
                "ATR|1W",                       # 29 (Weekly ATR for contraction)
                "RSI",                          # 30 (14-period Wilder RSI)
                "Stoch.K",                      # 31 (Stochastic momentum)
                "Perf.W",                       # 32 (1-week price performance)
                "Perf.1M",                      # 33 (1-month performance)
                "Perf.3M",                      # 34 (3-month relative performance)
                "total_revenue_cagr_5y",        # 35 (5Y revenue compounding)
                "free_cash_flow_fy",            # 36 (Annual FCF in raw INR)
                "cash_n_equivalents_fy",        # 37 (Cash in raw INR)
                "total_debt_fq",                # 38 (Total debt in raw INR)
                "AvgValue.Traded_10d",          # 39 (10-day turnover in raw INR)
                "gap",                          # 40 (Opening gap %)
                "receivables_turnover_fq",      # 41 (For authentic DSO = 365 / turnover)
                "return_on_equity_fq",          # 42 (ROE for banking/financials)
                "gross_margin_ttm",              # 43 (Gross profit margin %)
                # Canonical Fundamental Extensions (Phase 0/1 Verified)
                "total_revenue_ttm",             # 44
                "total_revenue_fy",              # 45
                "net_income_ttm",                # 46
                "net_income_fy",                 # 47
                "total_assets_fy",               # 48
                "total_liabilities_fy",          # 49
                "total_debt_fy",                 # 50
                "total_equity_fy",               # 51
                "return_on_capital_employed_fy", # 52
                "debt_to_equity_fy",             # 53
                "return_on_equity_fy"            # 54
            ],
            "sort": {"sortBy": sort_by, "sortOrder": sort_order},
            "range": [0, max(limit * 6, 200)]
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Content-Type": "application/json"
        }

        url = "https://scanner.tradingview.com/india/scan"

        try:
            post_data = json.dumps(payload).encode("utf-8")
            tv_req = urllib.request.Request(url, data=post_data, headers=headers)
            with urllib.request.urlopen(tv_req, timeout=8.0) as resp:
                if resp.status == 200:
                    raw = json.loads(resp.read().decode("utf-8"))
                    items = raw.get("data", [])
                    total_cnt = int(raw.get("totalCount") or 5000)
                    _LAST_SCAN_STATS["total_count"] = total_cnt
                    _LAST_SCAN_STATS["stage1_count"] = len(items)

                    seen_symbols = set()
                    results = []
                    
                    for it in items:
                        full_sym = it.get("s", "")  # e.g. "NSE:TCS" or "BSE:TCS"
                        ticker = full_sym.split(":")[-1].upper()

                        if ticker in seen_symbols:
                            continue
                        seen_symbols.add(ticker)

                        d = it.get("d", [])
                        if len(d) < 44:
                            continue

                        cmp = float(d[2] or 0.0)
                        if cmp <= 0:
                            continue

                        mcap_cr = round(float(d[5] or 0.0) / 10000000.0, 2)
                        pe = float(d[6]) if d[6] is not None else None
                        h52 = float(d[9]) if d[9] is not None else None
                        l52 = float(d[10]) if d[10] is not None else None
                        ema50 = float(d[11]) if d[11] is not None else None
                        ema200 = float(d[12]) if d[12] is not None else None
                        vol = float(d[4] or 0.0)
                        vol_10d = float(d[13]) if d[13] is not None else vol

                        # Robust Hierarchical Fundamentals (FQ with FY Fallback)
                        roce_fq = float(d[7]) if d[7] is not None else None
                        roce_fy = float(d[52]) if len(d) > 52 and d[52] is not None else None
                        roce = roce_fq if roce_fq is not None else roce_fy

                        roe_fq = float(d[42]) if len(d) > 42 and d[42] is not None else None
                        roe_fy = float(d[54]) if len(d) > 54 and d[54] is not None else None
                        roe = roe_fq if roe_fq is not None else roe_fy

                        de_fq = float(d[8]) if d[8] is not None else None
                        de_fy = float(d[53]) if len(d) > 53 and d[53] is not None else None
                        tot_debt_raw = float(d[50]) if len(d) > 50 and d[50] is not None else (float(d[38]) if d[38] is not None else None)
                        tot_eq_raw = float(d[51]) if len(d) > 51 and d[51] is not None else None

                        de = de_fq if de_fq is not None else (de_fy if de_fy is not None else (round(tot_debt_raw / tot_eq_raw, 2) if tot_debt_raw is not None and tot_eq_raw is not None and tot_eq_raw > 0 else None))

                        opm_ttm = float(d[14]) if len(d) > 14 and d[14] is not None else None
                        net_margin_ttm = float(d[15]) if len(d) > 15 and d[15] is not None else None
                        rev_growth_yoy = float(d[16]) if len(d) > 16 and d[16] is not None else None
                        current_ratio = float(d[17]) if len(d) > 17 and d[17] is not None else None
                        quick_ratio = float(d[18]) if len(d) > 18 and d[18] is not None else None
                        atr_live = float(d[19]) if len(d) > 19 and d[19] is not None else None
                        rvol_live = float(d[20]) if len(d) > 20 and d[20] is not None else None
                        high_day = float(d[21]) if len(d) > 21 and d[21] is not None else None
                        low_day = float(d[22]) if len(d) > 22 and d[22] is not None else None
                        vwap_live = float(d[23]) if len(d) > 23 and d[23] is not None else None

                        high_1m = float(d[24]) if len(d) > 24 and d[24] is not None else None
                        high_3m = float(d[25]) if len(d) > 25 and d[25] is not None else None
                        sma50 = float(d[26]) if len(d) > 26 and d[26] is not None else None
                        sma150 = float(d[27]) if len(d) > 27 and d[27] is not None else None
                        sma200 = float(d[28]) if len(d) > 28 and d[28] is not None else None
                        atr_weekly = float(d[29]) if len(d) > 29 and d[29] is not None else None
                        rsi_live = float(d[30]) if len(d) > 30 and d[30] is not None else None
                        stoch_k = float(d[31]) if len(d) > 31 and d[31] is not None else None
                        perf_w = float(d[32]) if len(d) > 32 and d[32] is not None else None
                        perf_1m = float(d[33]) if len(d) > 33 and d[33] is not None else None
                        perf_3m = float(d[34]) if len(d) > 34 and d[34] is not None else None
                        rev_cagr_5y = float(d[35]) if len(d) > 35 and d[35] is not None else None
                        fcf_cr = round(float(d[36]) / 10000000.0, 2) if len(d) > 36 and d[36] is not None else None
                        cash_cr = round(float(d[37]) / 10000000.0, 2) if len(d) > 37 and d[37] is not None else None
                        turnover_10d_cr = round(float(d[39]) / 10000000.0, 2) if len(d) > 39 and d[39] is not None else None
                        gap_live = float(d[40]) if len(d) > 40 and d[40] is not None else None
                        rec_turnover = float(d[41]) if len(d) > 41 and d[41] is not None else None
                        dso_days = round(365.0 / rec_turnover, 1) if (rec_turnover is not None and rec_turnover > 0) else None
                        gross_margin = float(d[43]) if len(d) > 43 and d[43] is not None else None

                        # Canonical Corporate Totals
                        revenue_raw = d[44] if (len(d) > 44 and d[44] is not None) else (d[45] if len(d) > 45 else None)
                        revenue_cr = round(float(revenue_raw) / 10000000.0, 2) if revenue_raw is not None else None

                        net_inc_raw = d[46] if (len(d) > 46 and d[46] is not None) else (d[47] if len(d) > 47 else None)
                        net_income_cr = round(float(net_inc_raw) / 10000000.0, 2) if net_inc_raw is not None else None

                        tot_assets_raw = d[48] if len(d) > 48 and d[48] is not None else None
                        total_assets_cr = round(float(tot_assets_raw) / 10000000.0, 2) if tot_assets_raw is not None else None

                        tot_liab_raw = d[49] if len(d) > 49 and d[49] is not None else None
                        total_liabilities_cr = round(float(tot_liab_raw) / 10000000.0, 2) if tot_liab_raw is not None else None

                        total_debt_cr = round(float(tot_debt_raw) / 10000000.0, 2) if tot_debt_raw is not None else None
                        net_worth_cr = round(float(tot_eq_raw) / 10000000.0, 2) if tot_eq_raw is not None else (round(total_assets_cr - total_liabilities_cr, 2) if (total_assets_cr and total_liabilities_cr) else None)

                        # Sector awareness for financial institutions
                        company_name = d[1] or d[0] or ticker
                        is_financial = (MissingDataGuard.resolve_sector(ticker, company_name) == "FINANCIALS")
                        effective_quality = roe if is_financial else (roce if roce is not None else roe)

                        # ── PHASE 2 DETERMINISTIC PYTHON GATING ──
                        # 1. Quality / Return on Capital Gate
                        if min_roce > 0 and effective_quality is not None and effective_quality < min_roce:
                            continue

                        # 2. Solvency / Debt to Equity Gate (Regulated Financials Exempt)
                        if not is_financial and max_de > 0 and de is not None and de > max_de:
                            continue

                        # 3. 52-Week High Proximity Gate
                        dist_52w = round(((h52 - cmp) / h52) * 100.0, 1) if (h52 and h52 > 0) else None
                        if near_52w > 0 and dist_52w is not None and dist_52w > near_52w:
                            continue

                        # 4. Multi-Year Sales Growth Gate
                        cand_growth = rev_cagr_5y if rev_cagr_5y is not None else rev_growth_yoy
                        if min_growth > 0 and cand_growth is not None and cand_growth < min_growth:
                            continue

                        # 5. P/E Ratio Gate
                        max_pe_user = getattr(req, "max_pe_ratio", None)
                        if max_pe_user and pe is not None and pe > max_pe_user:
                            continue

                        # Compute Genuine Continuous Inflection Rank (0-100)
                        if is_financial:
                            q_score = min(100.0, max(20.0, ((effective_quality or 15.0) / 16.0) * 80.0))
                            s_score = 80.0
                        else:
                            q_score = min(100.0, max(10.0, ((effective_quality or 15.0) / 25.0) * 80.0))
                            s_score = min(100.0, max(20.0, 100.0 - ((de or 0.5) * 35.0)))

                        growth_metric = cand_growth if cand_growth is not None else 10.0
                        g_score = min(100.0, max(25.0, (growth_metric / 20.0) * 85.0))
                        inflection_rank = round((q_score * 0.40) + (s_score * 0.35) + (g_score * 0.25), 1)

                        range_exp = (
                            round(((high_day - low_day - atr_live) / atr_live) * 100.0, 1)
                            if (high_day is not None and low_day is not None and atr_live is not None and atr_live > 0)
                            else 0.0
                        )
                        vwap_prox = (
                            round(((cmp - vwap_live) / vwap_live) * 100.0, 2)
                            if (vwap_live is not None and vwap_live > 0)
                            else 0.0
                        )

                        raw_candidate = {
                            "symbol": ticker,
                            "company_name": company_name,
                            "cmp": cmp,
                            "market_cap_cr": mcap_cr,
                            "pe_ratio": round(pe, 1) if pe is not None else None,
                            "roce_pct": round(roce, 1) if roce is not None else (round(roe, 1) if roe is not None else None),
                            "roe_pct": round(roe, 1) if roe is not None else None,
                            "debt_to_equity": round(de, 2) if de is not None else None,
                            "high_52w": h52,
                            "low_52w": l52,
                            "high_1m": high_1m,
                            "high_3m": high_3m,
                            "ema50": ema50,
                            "ema200": ema200,
                            "sma50": sma50,
                            "sma150": sma150,
                            "sma200": sma200,
                            "volume": vol,
                            "avg_volume_10d": vol_10d,
                            "turnover_10d_cr": turnover_10d_cr,
                            "opm_pct": round(opm_ttm, 2) if opm_ttm is not None else None,
                            "net_margin_pct": round(net_margin_ttm, 2) if net_margin_ttm is not None else None,
                            "gross_margin_pct": round(gross_margin, 2) if gross_margin is not None else None,
                            "sales_growth_pct": round(rev_growth_yoy, 1) if rev_growth_yoy is not None else None,
                            "revenue_cagr_5y_pct": round(rev_cagr_5y, 1) if rev_cagr_5y is not None else None,
                            "current_ratio": round(current_ratio, 3) if current_ratio is not None else None,
                            "quick_ratio": round(quick_ratio, 3) if quick_ratio is not None else None,
                            "dso_days": dso_days,
                            "fcf_cr": fcf_cr,
                            "cash_cr": cash_cr,
                            "revenue_cr": revenue_cr,
                            "net_income_cr": net_income_cr,
                            "total_assets_cr": total_assets_cr,
                            "total_liabilities_cr": total_liabilities_cr,
                            "total_debt_cr": total_debt_cr,
                            "net_worth_cr": net_worth_cr,
                            "inflection_rank": inflection_rank,
                            "atr_live": round(atr_live, 2) if atr_live is not None else None,
                            "atr_weekly": round(atr_weekly, 2) if atr_weekly is not None else None,
                            "rvol_live": round(rvol_live, 2) if rvol_live is not None else None,
                            "rsi_live": round(rsi_live, 1) if rsi_live is not None else None,
                            "stoch_k": round(stoch_k, 1) if stoch_k is not None else None,
                            "perf_w": round(perf_w, 2) if perf_w is not None else None,
                            "perf_1m": round(perf_1m, 2) if perf_1m is not None else None,
                            "perf_3m": round(perf_3m, 2) if perf_3m is not None else None,
                            "gap_pct": round(gap_live, 2) if gap_live is not None else None,
                            "range_expansion_pct": range_exp,
                            "vwap_proximity_pct": vwap_prox,
                        }

                        normalized_cand = MissingDataGuard.normalize_candidate_fundamentals(
                            raw_candidate,
                            is_local_db=False
                        )
                        results.append(normalized_cand)

                    _QUERY_CACHE[cache_key] = {"timestamp": now, "data": results}
                    logger.info(f"TradingView scanner returned {len(results)} gated live market matches.")
                    return results
        except Exception as e:
            logger.warning(f"TradingView scanner query failed or timed out ({e}). Falling back to local database.")

        return []

    @classmethod
    def get_preset_query_string(cls, preset_name: str) -> str:
        """
        Returns the optimized cloud query string for standardized institutional presets.
        """
        presets = {
            "MULTIBAGGER_INFLECTION_PRESET": (
                "Market Capitalization > 250 AND Return on capital employed > 15 "
                "AND Sales growth 3Years > 12 AND Debt to equity < 1.0 AND "
                "Price to Earning > 0"
            ),
            "SWING_VCP_BREAKOUT_PRESET": (
                "Market Capitalization > 500 AND Return on capital employed > 12 "
                "AND Current price > 0.8 * High price all time"
            ),
            "MICROCAP_COMPOUNDER_PRESET": (
                "Market Capitalization > 150 AND Market Capitalization < 3000 "
                "AND Return on capital employed > 18 AND Debt to equity < 0.5 "
                "AND Cash from operations 3Years > 0"
            ),
            "INTRADAY_MOMENTUM_SCALP_PRESET": (
                "Market Capitalization > 2000 AND Volume > 100000"
            )
        }
        return presets.get(preset_name, presets["MULTIBAGGER_INFLECTION_PRESET"])
