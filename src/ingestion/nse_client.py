"""
NSE India Session Client — Fetches corporate filings, shareholding patterns,
and corporate actions from NSE India's internal JSON endpoints.

NSE requires session-based cookie management (visit main page first to get
session cookies, then use them for API calls). This client handles that
automatically with retries and graceful fallback.

IMPORTANT: NSE can block automated requests. This client is designed to
fail gracefully and log warnings instead of crashing.
"""

import logging
import time
from datetime import date, datetime
from typing import Dict, Any, List, Optional

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NseClient:
    """
    Fetches real data from NSE India's internal API endpoints.
    Handles session/cookie management automatically.
    """

    BASE_URL = "https://www.nseindia.com"
    MAX_RETRIES = 3
    RETRY_BACKOFF_SECONDS = 5

    def __init__(self, rate_limit_seconds: float = 3.0):
        self.rate_limit_seconds = rate_limit_seconds
        self._last_request_time: float = 0.0
        self._session: Optional[requests.Session] = None

    def _get_session(self) -> requests.Session:
        """Create or return an authenticated NSE session with cookies."""
        if self._session is not None:
            return self._session

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.nseindia.com/",
            "Connection": "keep-alive",
        })

        # Visit main page to get session cookies
        try:
            resp = session.get(self.BASE_URL, timeout=10)
            if resp.status_code == 200:
                logger.info("[NSE] Session established successfully")
                self._session = session
            else:
                logger.warning(f"[NSE] Failed to establish session: HTTP {resp.status_code}")
                self._session = session  # Try anyway
        except Exception as e:
            logger.warning(f"[NSE] Could not establish session: {e}")
            self._session = session

        return self._session

    def _throttle(self):
        """Rate limit requests to avoid being blocked."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self._last_request_time = time.time()

    def _api_get(self, endpoint: str) -> Optional[Dict]:
        """
        Make an authenticated GET request to an NSE API endpoint.
        Returns parsed JSON or None on failure.
        """
        session = self._get_session()
        url = f"{self.BASE_URL}{endpoint}"

        for attempt in range(1, self.MAX_RETRIES + 1):
            self._throttle()
            try:
                resp = session.get(url, timeout=10)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 404:
                    logger.debug(f"[NSE] Resource not found (HTTP 404): {endpoint}")
                    return None
                elif resp.status_code in (401, 403):
                    # Session expired, re-establish
                    logger.warning(f"[NSE] Session expired (HTTP {resp.status_code}), re-establishing...")
                    self._session = None
                    session = self._get_session()
                else:
                    logger.warning(f"[NSE] HTTP {resp.status_code} for {endpoint} (attempt {attempt}/{self.MAX_RETRIES})")
            except requests.exceptions.Timeout:
                logger.warning(f"[NSE] Timeout for {endpoint} (attempt {attempt}/{self.MAX_RETRIES})")
            except requests.exceptions.ConnectionError:
                logger.warning(f"[NSE] Connection error for {endpoint} (attempt {attempt}/{self.MAX_RETRIES})")
            except Exception as e:
                logger.error(f"[NSE] Unexpected error for {endpoint}: {e}")
                return None

            if attempt < self.MAX_RETRIES:
                backoff = self.RETRY_BACKOFF_SECONDS * attempt
                logger.info(f"[NSE] Retrying in {backoff}s...")
                time.sleep(backoff)

        logger.warning(f"[NSE] All {self.MAX_RETRIES} attempts failed for {endpoint}")
        return None

    # ──────────────────────────────────────────────────────────────
    # Corporate Actions (Splits, Bonuses, Dividends)
    # ──────────────────────────────────────────────────────────────

    def fetch_corporate_actions(
        self, nse_symbol: str, from_date: Optional[date] = None, to_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch corporate actions (splits, bonuses, dividends) from NSE.
        """
        endpoint = f"/api/corporateActions?index=equities&symbol={nse_symbol}"
        if from_date:
            endpoint += f"&from_date={from_date.strftime('%d-%m-%Y')}"
        if to_date:
            endpoint += f"&to_date={to_date.strftime('%d-%m-%Y')}"

        data = self._api_get(endpoint)
        if not data:
            return []

        records = []
        for item in data if isinstance(data, list) else []:
            try:
                ex_date_str = item.get("exDate", "")
                if not ex_date_str:
                    continue

                ex_dt = self._parse_nse_date(ex_date_str)
                if ex_dt is None:
                    continue

                subject = (item.get("subject", "") or "").upper()
                action_type = self._classify_action_type(subject)

                old_shares, new_shares = self._parse_split_ratio(subject)

                records.append({
                    "ex_date": ex_dt,
                    "action_type": action_type,
                    "old_shares": old_shares,
                    "new_shares": new_shares,
                    "description": item.get("subject", ""),
                    "announcement_date": self._parse_nse_date(item.get("anDate", "")),
                    "record_date": self._parse_nse_date(item.get("recDate", "")),
                })
            except Exception as e:
                logger.warning(f"[NSE] Error parsing corporate action for {nse_symbol}: {e}")
                continue

        logger.info(f"[NSE] Fetched {len(records)} corporate actions for {nse_symbol}")
        return records

    # ──────────────────────────────────────────────────────────────
    # Shareholding Pattern
    # ──────────────────────────────────────────────────────────────

    def fetch_shareholding_pattern(self, nse_symbol: str) -> List[Dict[str, Any]]:
        """
        Fetch quarterly shareholding pattern (Promoter, FII, DII, Public).
        """
        endpoint = f"/api/corporate-shareholding?symbol={nse_symbol}"
        data = self._api_get(endpoint)
        if not data:
            return []

        records = []
        try:
            # NSE returns shareholding data in a structured format
            if isinstance(data, dict):
                for period_data in data.get("data", []):
                    record = {
                        "period": period_data.get("date", ""),
                        "promoter_pct": self._safe_float(period_data.get("promotersPer")),
                        "fii_pct": self._safe_float(period_data.get("fiiPer")),
                        "dii_pct": self._safe_float(period_data.get("diiPer")),
                        "public_pct": self._safe_float(period_data.get("publicPer")),
                        "pledged_pct": self._safe_float(period_data.get("pledgedPer")),
                    }
                    records.append(record)
        except Exception as e:
            logger.warning(f"[NSE] Error parsing shareholding for {nse_symbol}: {e}")

        logger.info(f"[NSE] Fetched {len(records)} shareholding records for {nse_symbol}")
        return records

    # ──────────────────────────────────────────────────────────────
    # Corporate Announcements / Filings
    # ──────────────────────────────────────────────────────────────

    def fetch_corporate_announcements(
        self, nse_symbol: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch corporate announcements (board meetings, results, AGM, etc.) from NSE.
        """
        endpoint = f"/api/corporate-announcements?index=equities&symbol={nse_symbol}"
        data = self._api_get(endpoint)
        if not data:
            return []

        records = []
        for item in data if isinstance(data, list) else []:
            try:
                records.append({
                    "subject": item.get("desc", ""),
                    "announcement_date": self._parse_nse_date(item.get("an_dt", "")),
                    "attachment_url": item.get("attchmntFile", ""),
                    "category": item.get("smIndustry", ""),
                })
            except Exception as e:
                logger.warning(f"[NSE] Error parsing announcement for {nse_symbol}: {e}")
                continue

        logger.info(f"[NSE] Fetched {len(records)} announcements for {nse_symbol}")
        return records

    # ──────────────────────────────────────────────────────────────
    # Board Meetings / Forward Catalyst Calendar (SEBI LODR Reg 29)
    # ──────────────────────────────────────────────────────────────

    def fetch_board_meetings(
        self, nse_symbol: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch advance notices of Board Meetings from NSE (SEBI LODR Reg 29).
        """
        endpoint = f"/api/corporate-board-meetings?index=equities&symbol={nse_symbol}"
        data = self._api_get(endpoint)
        if not data:
            data = self._api_get(f"/api/corporates-board-meetings?index=equities&symbol={nse_symbol}")
        if not data:
            return []

        records = []
        for item in data if isinstance(data, list) else []:
            try:
                meeting_dt = self._parse_nse_date(item.get("bm_date") or item.get("meetingDate") or "")
                notice_dt = self._parse_nse_date(item.get("bm_anndate") or item.get("noticeDate") or "")
                purpose = item.get("bm_purpose") or item.get("purpose") or ""

                if not meeting_dt:
                    continue

                today = date.today()
                days_until = (meeting_dt - today).days

                records.append({
                    "symbol": nse_symbol.upper(),
                    "meeting_date": meeting_dt,
                    "notice_date": notice_dt or today,
                    "purpose": purpose,
                    "days_until_meeting": days_until,
                    "urgency_status": "IMMINENT" if 0 <= days_until <= 3 else ("SCHEDULED" if days_until > 3 else "COMPLETED"),
                    "source_url": item.get("attchmntFile", "")
                })
            except Exception as e:
                logger.warning(f"[NSE] Error parsing board meeting for {nse_symbol}: {e}")
                continue

        logger.info(f"[NSE] Fetched {len(records)} board meeting notices for {nse_symbol}")
        return records

    # ──────────────────────────────────────────────────────────────
    # Helper Methods
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_nse_date(date_str: str) -> Optional[date]:
        """Parse NSE date strings which come in various formats."""
        if not date_str or date_str.strip() == "-":
            return None
        for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y"):
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _classify_action_type(subject: str) -> str:
        """Classify the type of corporate action from its description."""
        subject = subject.upper()
        if "SPLIT" in subject or "SUB-DIVISION" in subject or "SUBDIVISION" in subject:
            return "SPLIT"
        elif "BONUS" in subject:
            return "BONUS"
        elif "RIGHTS" in subject:
            return "RIGHTS"
        elif "DIVIDEND" in subject:
            return "DIVIDEND"
        elif "DEMERGER" in subject or "DE-MERGER" in subject:
            return "DEMERGER"
        else:
            return "OTHER"

    @staticmethod
    def _parse_split_ratio(subject: str) -> tuple:
        """
        Parse split/bonus ratio from description.
        Returns (old_shares, new_shares).
        """
        import re
        # Try patterns like "1:5", "1:2", "FV Rs.10 to Rs.2"
        ratio_match = re.search(r"(\d+)\s*:\s*(\d+)", subject)
        if ratio_match:
            old = float(ratio_match.group(1))
            new = float(ratio_match.group(2))
            return old, new

        # Try face value patterns like "Rs.10/- to Rs.2/-"
        fv_match = re.search(r"RS\.?\s*(\d+).*?TO\s*RS\.?\s*(\d+)", subject.upper())
        if fv_match:
            old_fv = float(fv_match.group(1))
            new_fv = float(fv_match.group(2))
            if new_fv > 0:
                ratio = old_fv / new_fv
                return 1.0, ratio

        return 1.0, 1.0

    @staticmethod
    def _safe_float(value) -> Optional[float]:
        """Safely convert a value to float."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
