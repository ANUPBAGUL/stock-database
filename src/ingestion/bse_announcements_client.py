"""
BSE / NSE Official Corporate Announcements Client.

Dual-Exchange Primary Authority for official SEBI Regulation 30 corporate disclosures:
1. Primary:   BSE India Disclosures API (`api.bseindia.com`) with signed PDF links.
2. Secondary: NSE India Announcements API (`/api/corporate-announcements`) with attachment URLs.

Captures:
- Exact exchange publication timestamps
- Official signed exchange filing attachments (PDFs)
- Zero third-party news blog aggregators
"""

import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple
from curl_cffi import requests as cffi_requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BSE_SCRIP_MAP = {
    "DIXON": "540699",
    "TCS": "532540",
    "RELIANCE": "500325",
    "INFY": "500209",
    "HDFCBANK": "500180",
    "ICICIBANK": "532174",
    "SBIN": "500112",
    "BHARTIARTL": "532454",
    "ITC": "500875",
    "LT": "500510",
    "HINDUNILVR": "500696",
    "BAJFINANCE": "500034",
    "TATAMOTORS": "500570",
    "MARUTI": "532500",
    "SUNPHARMA": "524715",
    "TITAN": "500114",
    "ASIANPAINT": "500820",
    "KOTAKBANK": "500247",
    "AXISBANK": "532215",
    "ADANIENT": "512599",
}


class BseAnnouncementsClient:
    """
    Ingests authentic SEBI corporate filings directly from BSE India with fallback to NSE.
    """

    BSE_API_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
    BSE_PDF_BASE = "https://www.bseindia.com/xml-data/corpfiling/AttachLive"
    NSE_ANNOUNCEMENTS_URL = "https://www.nseindia.com/api/corporate-announcements"

    def __init__(self):
        self._session = cffi_requests.Session(impersonate="chrome124")
        self._bse_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": "https://www.bseindia.com/",
            "Accept": "application/json, text/plain, */*",
        }
        self._nse_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.nseindia.com/",
            "Accept": "*/*",
        }

    def resolve_scrip_code(self, symbol: str) -> Optional[str]:
        sym_clean = symbol.upper().strip().replace(".NS", "").replace(".BO", "")
        if sym_clean in BSE_SCRIP_MAP:
            return BSE_SCRIP_MAP[sym_clean]

        try:
            r = self._session.get(
                f"https://api.bseindia.com/BseIndiaAPI/api/SuggestScrips/w?str={sym_clean}",
                headers=self._bse_headers,
                timeout=5
            )
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and len(data) > 0:
                    code = str(data[0].get("scrip_cd") or data[0].get("SecurityCode") or "")
                    if code:
                        BSE_SCRIP_MAP[sym_clean] = code
                        return code
        except Exception as e:
            logger.debug(f"[BSE] Scrip lookup error for {sym_clean}: {e}")

        return None

    def fetch_official_announcements(self, symbol: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Fetches official corporate filings for a symbol.
        Tries BSE Disclosures API first; if unavailable or slow, falls back to NSE API.
        """
        sym_clean = symbol.upper().strip().replace(".NS", "").replace(".BO", "")
        scrip_code = self.resolve_scrip_code(sym_clean)

        # ── 1. PRIMARY: BSE Disclosures API ──
        if scrip_code:
            params = {
                "pageno": 1,
                "strCat": -1,
                "strPrevDate": "",
                "strScrip": scrip_code,
                "strSearch": "P",
                "strToDate": "",
                "strType": "C"
            }
            for attempt in range(2):
                try:
                    r = self._session.get(self.BSE_API_URL, params=params, headers=self._bse_headers, timeout=15)
                    if r.status_code == 200:
                        data = r.json()
                        table = data.get("Table", [])
                        if table:
                            results = []
                            for item in table[:limit]:
                                news_id = item.get("NEWSID", "")
                                headline = item.get("NEWSSUB", "") or ""
                                more_details = item.get("MORE", "") or ""
                                dt_tm_str = item.get("DT_TM", "")
                                attachment_name = item.get("ATTACHMENTNAME", "")
                                category_name = item.get("CATEGORYNAME", "") or "REGULATORY_DISCLOSURE"

                                pub_dt = None
                                if dt_tm_str:
                                    try:
                                        pub_dt = datetime.fromisoformat(dt_tm_str.split(".")[0])
                                    except Exception:
                                        pub_dt = datetime.utcnow()

                                doc_url = None
                                if attachment_name and attachment_name.strip():
                                    doc_url = f"{self.BSE_PDF_BASE}/{attachment_name.strip()}"

                                event_type, materiality = self._classify_filing(headline, category_name)

                                results.append({
                                    "event_id": news_id or str(hash(f"{sym_clean}_{dt_tm_str}_{headline[:30]}")),
                                    "symbol": sym_clean,
                                    "exchange": "BSE",
                                    "bse_scrip_code": scrip_code,
                                    "headline": headline.strip(),
                                    "summary": (more_details or headline)[:500].strip(),
                                    "category": category_name,
                                    "event_type": event_type,
                                    "materiality": materiality,
                                    "source_published_at": pub_dt.isoformat() if pub_dt else datetime.utcnow().isoformat(),
                                    "ingested_at": datetime.utcnow().isoformat(),
                                    "event_occurred_at": None,
                                    "source_document_url": doc_url,
                                    "source_type": "OFFICIAL_EXCHANGE_FILING",
                                    "is_m6_eligible": True,
                                    "source_authority_rank": 1,
                                    "data_quality": "HIGH_CONFIDENCE",
                                })

                            logger.info(f"[BSE] Ingested {len(results)} official SEBI filings for {sym_clean}")
                            return results
                except Exception as e:
                    logger.debug(f"[BSE] Attempt {attempt+1} error for {sym_clean}: {e}")

        # ── 2. SECONDARY: NSE Corporate Announcements API ──
        try:
            self._session.get("https://www.nseindia.com", headers=self._nse_headers, timeout=5)
            r_nse = self._session.get(
                f"{self.NSE_ANNOUNCEMENTS_URL}?index=equities&symbol={sym_clean}",
                headers=self._nse_headers,
                timeout=8
            )
            if r_nse.status_code == 200:
                items = r_nse.json()
                if isinstance(items, list) and len(items) > 0:
                    results = []
                    for item in items[:limit]:
                        subject = item.get("desc") or item.get("subject") or ""
                        attch = item.get("attchmntFile") or item.get("attachment")
                        an_dt_str = item.get("an_dt") or ""
                        
                        doc_url = attch if attch and attch.startswith("http") else (f"https://nsearchives.nseindia.com/corporate/{attch}" if attch else None)
                        event_type, materiality = self._classify_filing(subject, "NSE_LODR_DISCLOSURE")

                        results.append({
                            "event_id": str(hash(f"{sym_clean}_{an_dt_str}_{subject[:30]}")),
                            "symbol": sym_clean,
                            "exchange": "NSE",
                            "bse_scrip_code": scrip_code,
                            "headline": subject.strip(),
                            "summary": subject.strip(),
                            "category": "NSE_LODR_DISCLOSURE",
                            "event_type": event_type,
                            "materiality": materiality,
                            "source_published_at": an_dt_str or datetime.utcnow().isoformat(),
                            "ingested_at": datetime.utcnow().isoformat(),
                            "event_occurred_at": None,
                            "source_document_url": doc_url,
                            "source_type": "OFFICIAL_EXCHANGE_FILING",
                            "is_m6_eligible": True,
                            "source_authority_rank": 1,
                            "data_quality": "HIGH_CONFIDENCE",
                        })

                    logger.info(f"[NSE] Ingested {len(results)} official announcements for {sym_clean}")
                    return results
        except Exception as e:
            logger.error(f"[Announcements] NSE fallback error for {sym_clean}: {e}")

        return []

    @staticmethod
    def _classify_filing(headline: str, category: str) -> Tuple[str, str]:
        hl = headline.upper()
        if any(w in hl for w in ["FINANCIAL RESULT", "UNAUDITED FINANCIAL", "AUDITED FINANCIAL", "EARNINGS", "Q1", "Q2", "Q3", "Q4"]):
            return "EARNINGS_RESULT", "HIGH"
        elif any(w in hl for w in ["CAPEX", "EXPANSION", "NEW PLANT", "COMMISSIONING", "COMMENCEMENT"]):
            return "CAPACITY_EXPANSION", "HIGH"
        elif any(w in hl for w in ["ORDER", "CONTRACT", "AGREEMENT", "AWARD OF WORK", "LOA"]):
            return "ORDER_WIN", "HIGH"
        elif any(w in hl for w in ["RESIGNATION", "APPOINTMENT", "CHIEF EXECUTIVE OFFICER", "MANAGING DIRECTOR", "CFO"]):
            return "MANAGEMENT_CHANGE", "MEDIUM"
        elif any(w in hl for w in ["DIVIDEND", "BONUS", "SPLIT", "SUB-DIVISION", "BUYBACK", "RIGHTS ISSUE"]):
            return "CORPORATE_ACTION", "MEDIUM"
        elif any(w in hl for w in ["REGULATORY", "SEBI", "FDA", "SHOW CAUSE", "PENALTY", "INVESTIGATION"]):
            return "REGULATORY_ACTION", "HIGH"
        elif any(w in hl for w in ["ESOP", "ALLOTMENT OF SHARES"]):
            return "ESOP_ALLOTMENT", "LOW"
        else:
            return "GENERAL_CORPORATE_DISCLOSURE", "LOW"
