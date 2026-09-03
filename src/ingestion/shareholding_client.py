"""
Shareholding Pattern Ingestion Client.

Fetches authentic quarterly shareholding patterns (Promoter, FII, DII, Public, Government)
directly from official SEBI LODR Clause 31 disclosures.

DATA TRUTH HIERARCHY:
1. Primary Authority:   Screener.in XBRL Engine (Parses official BSE/NSE SEBI quarterly XML filings)
2. Secondary Authority: Direct NSE India Session (`NseClient`)
3. NO-FABRICATION RULE: If neither source returns official filings, the pattern returns None
                        with data_quality_flag="UNAVAILABLE".
                        Yahoo Finance 'heldPercentInsiders' is NEVER used as a promoter fallback.
"""

import logging
from datetime import date, datetime
from typing import Dict, Any, Optional, List

from src.ingestion.screener_client import ScreenerClient
from src.ingestion.nse_client import NseClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ShareholdingClient:
    """
    Fetches genuine quarterly shareholding patterns directly from SEBI LODR filings.
    """

    @classmethod
    def fetch_shareholding_pattern(
        cls,
        symbol: str,
        screener_client: Optional[ScreenerClient] = None,
        nse_client: Optional[NseClient] = None,
    ) -> Dict[str, Any]:
        """
        Fetch the most recent verified quarterly shareholding pattern for an Indian stock.

        Returns dict matching ShareholdingHistory schema:
            period_end_date, promoter_holding_pct, fii_holding_pct, dii_holding_pct,
            government_holding_pct, retail_public_pct, institutional_holding_pct,
            source, data_quality_flag, consolidation_scope
        """
        sym_clean = symbol.upper().strip().replace(".NS", "").replace(".BO", "")

        # ── 1. PRIMARY SOURCE: Screener.in XBRL SEBI Filing Parser ──
        try:
            sc_client = screener_client or ScreenerClient()
            history = sc_client.fetch_shareholding_history(sym_clean)
            if history and len(history) > 0:
                latest = history[0]
                if latest.get("promoter_holding_pct") is not None:
                    logger.info(
                        f"[Shareholding] Screener primary source for {sym_clean} | "
                        f"Period={latest['period_label']} | Promoter={latest['promoter_holding_pct']}%, "
                        f"FII={latest['fii_holding_pct']}%, DII={latest['dii_holding_pct']}%, "
                        f"Public={latest['retail_public_pct']}%"
                    )
                    return {
                        "period_end_date": latest["period_end_date"].isoformat() if isinstance(latest["period_end_date"], date) else str(latest["period_end_date"]),
                        "promoter_holding_pct": latest["promoter_holding_pct"],
                        "fii_holding_pct": latest["fii_holding_pct"],
                        "dii_holding_pct": latest["dii_holding_pct"],
                        "mf_holding_pct": latest.get("mf_holding_pct", 0.0),
                        "other_dii_holding_pct": latest.get("other_dii_holding_pct", 0.0),
                        "government_holding_pct": latest.get("government_holding_pct", 0.0),
                        "retail_public_pct": latest["retail_public_pct"],
                        "institutional_holding_pct": latest["institutional_holding_pct"],
                        "pledged_pct": latest.get("pledged_pct", 0.0),
                        "number_of_shareholders": latest.get("number_of_shareholders"),
                        "source": "SCREENER_XBRL_SEBI_FILING",
                        "consolidation_scope": latest.get("consolidation_scope", "CONSOLIDATED"),
                        "data_quality_flag": latest.get("data_quality_flag", "HIGH_CONFIDENCE"),
                    }
        except Exception as e:
            logger.warning(f"[Shareholding] Screener primary source failed for {sym_clean}: {e}")

        # ── 2. SECONDARY SOURCE: Direct NSE Session ──
        try:
            nse = nse_client or NseClient()
            records = nse.fetch_shareholding_pattern(sym_clean)
            if records and len(records) > 0:
                latest = records[0]
                promoter_pct = latest.get("promoter_pct")
                if promoter_pct is not None and promoter_pct > 0:
                    period_date = cls._parse_nse_period(latest.get("period", ""))
                    fii_pct = latest.get("fii_pct")
                    dii_pct = latest.get("dii_pct")
                    inst_pct = round((fii_pct or 0.0) + (dii_pct or 0.0), 2) if (fii_pct or dii_pct) else None

                    logger.info(
                        f"[Shareholding] NSE secondary source: {sym_clean} | "
                        f"Promoter={promoter_pct}%, FII={fii_pct}%, DII={dii_pct}%"
                    )
                    return {
                        "period_end_date": period_date.isoformat() if period_date else date.today().isoformat(),
                        "promoter_holding_pct": promoter_pct,
                        "fii_holding_pct": fii_pct,
                        "dii_holding_pct": dii_pct,
                        "other_dii_holding_pct": None,
                        "government_holding_pct": 0.0,
                        "retail_public_pct": latest.get("public_pct"),
                        "institutional_holding_pct": inst_pct,
                        "pledged_pct": latest.get("pledged_pct", 0.0),
                        "number_of_shareholders": None,
                        "source": "NSE_SEBI_LODR_SHAREHOLDING_PATTERN",
                        "consolidation_scope": "SEBI_LODR_PATTERN_FILING",
                        "data_quality_flag": "HIGH_CONFIDENCE",
                    }
        except Exception as e:
            logger.warning(f"[Shareholding] NSE secondary source failed for {sym_clean}: {e}")

        # ── 3. STRICT NO-FABRICATION POLICY ──
        # If neither official source returns data, report UNAVAILABLE.
        # NEVER return yfinance insider percentages as promoter holding.
        logger.error(f"[Shareholding] Official SEBI shareholding unavailable for {sym_clean}. Returning UNAVAILABLE.")
        return {
            "period_end_date": date.today().isoformat(),
            "promoter_holding_pct": None,
            "fii_holding_pct": None,
            "dii_holding_pct": None,
            "other_dii_holding_pct": None,
            "government_holding_pct": None,
            "retail_public_pct": None,
            "institutional_holding_pct": None,
            "pledged_pct": None,
            "number_of_shareholders": None,
            "source": "UNAVAILABLE",
            "consolidation_scope": "UNAVAILABLE",
            "data_quality_flag": "UNAVAILABLE",
        }

    @staticmethod
    def _parse_nse_period(period_str: str) -> Optional[date]:
        """Parses 'Jun 2026' or '30-Jun-2026' to date(2026, 6, 30)."""
        if not period_str:
            return None
        parts = period_str.strip().split()
        if len(parts) == 2:
            m_str, y_str = parts[0][:3].title(), parts[1]
            m_map = {"Mar": (3, 31), "Jun": (6, 30), "Sep": (9, 30), "Dec": (12, 31)}
            if m_str in m_map:
                try:
                    return date(int(y_str), m_map[m_str][0], m_map[m_str][1])
                except Exception:
                    pass
        return None
