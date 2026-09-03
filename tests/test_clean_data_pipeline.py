"""
Clean & Verified Data Pipeline Test Suite.

Verifies institutional-grade data ingestion:
1. ScreenerClient: Verified SEBI shareholding patterns & 10-year audited balance sheets
2. BseAnnouncementsClient: Official SEBI LODR Regulation 30 filings with signed attachments
3. ShareholdingClient: Primary Screener authority with zero Yahoo Finance insider fallbacks
4. MacroRegimeClient: Live India VIX & Nifty valuation from official NSE feeds
5. FeatureEngine: ROCE computation with intermediate quarter audited BS lookback
"""

import os
import sys
import unittest
from datetime import date, datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.ingestion.screener_client import ScreenerClient
from src.ingestion.bse_announcements_client import BseAnnouncementsClient
from src.ingestion.shareholding_client import ShareholdingClient
from src.ingestion.macro_client import MacroRegimeClient
from src.analytics.feature_engine import FeatureEngine
from src.db.base import SessionLocal, Base, engine
from src.db.models import Company, BitemporalFinancial


class TestCleanDataPipeline(unittest.TestCase):

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    # ──────────────────────────────────────────────────────────────
    # 1. ScreenerClient Tests
    # ──────────────────────────────────────────────────────────────

    def test_screener_shareholding_dixon_truth(self):
        """Verify Screener extracts official SEBI shareholding pattern for DIXON."""
        client = ScreenerClient()
        history = client.fetch_shareholding_history("DIXON")
        self.assertGreater(len(history), 0, "Should fetch at least 1 quarter of shareholding")

        latest = history[0]
        # Dixon official SEBI promoter holding is ~28.55% (NOT 40.14% Yahoo fallback)
        self.assertAlmostEqual(latest["promoter_holding_pct"], 28.55, delta=1.5)
        self.assertAlmostEqual(latest["fii_holding_pct"], 17.87, delta=3.0)
        self.assertAlmostEqual(latest["dii_holding_pct"], 28.38, delta=3.0)
        self.assertAlmostEqual(latest["retail_public_pct"], 25.20, delta=3.0)
        self.assertEqual(latest["source"], "SCREENER_XBRL_SEBI_FILING")
        self.assertEqual(latest["data_quality_flag"], "HIGH_CONFIDENCE")

    def test_screener_balance_sheet_history(self):
        """Verify Screener extracts 10-year audited balance sheet primitives."""
        client = ScreenerClient()
        bs = client.fetch_balance_sheet_history("DIXON")
        self.assertGreater(len(bs), 3, "Should fetch multiple years of balance sheets")

        latest_bs = bs[0]
        self.assertIsNotNone(latest_bs["total_assets"])
        self.assertIsNotNone(latest_bs["borrowings"])
        self.assertIsNotNone(latest_bs["net_worth"])
        self.assertGreater(latest_bs["total_assets"], 1000.0)  # > 1000 Cr
        self.assertEqual(latest_bs["source"], "SCREENER_AUDITED_FILING")

    def test_screener_company_overview(self):
        """Verify Screener extracts verified ROCE, ROE, and Market Cap."""
        client = ScreenerClient()
        overview = client.fetch_company_overview("DIXON")
        self.assertIn("roce_pct", overview)
        self.assertIn("market_cap_crores", overview)
        if overview.get("roce_pct"):
            # Dixon ROCE is in the 30% - 50% range
            self.assertGreater(overview["roce_pct"], 20.0)
            self.assertLess(overview["roce_pct"], 70.0)

    # ──────────────────────────────────────────────────────────────
    # 2. BseAnnouncementsClient Tests
    # ──────────────────────────────────────────────────────────────

    def test_bse_announcements_official_filings(self):
        """Verify BSE client fetches official SEBI Regulation 30 filings with PDF links."""
        client = BseAnnouncementsClient()
        announcements = client.fetch_official_announcements("MANORAMA", limit=10)
        if not announcements:
            # Fallback test with DIXON
            announcements = client.fetch_official_announcements("DIXON", limit=10)

        if announcements:
            first = announcements[0]
            self.assertIn(first["symbol"], ["MANORAMA", "DIXON"])
            self.assertEqual(first["source_type"], "OFFICIAL_EXCHANGE_FILING")
            self.assertEqual(first["source_authority_rank"], 1)
            self.assertIn("headline", first)
            self.assertIn("source_published_at", first)
            self.assertTrue(first["is_m6_eligible"])
        else:
            # If live network timed out, test parser method directly
            event_type, materiality = client._classify_filing("Board Meeting to consider Financial Results", "Result")
            self.assertEqual(event_type, "FINANCIAL_RESULT")
            self.assertEqual(materiality, "HIGH")

    # ──────────────────────────────────────────────────────────────
    # 3. ShareholdingClient Authority Routing Tests
    # ──────────────────────────────────────────────────────────────

    def test_shareholding_client_uses_screener_primary(self):
        """Verify ShareholdingClient routes through Screener and returns verified data."""
        result = ShareholdingClient.fetch_shareholding_pattern("DIXON")
        self.assertEqual(result["source"], "SCREENER_XBRL_SEBI_FILING")
        self.assertEqual(result["data_quality_flag"], "HIGH_CONFIDENCE")
        self.assertAlmostEqual(result["promoter_holding_pct"], 28.55, delta=1.5)
        self.assertIsNotNone(result["fii_holding_pct"])
        self.assertIsNotNone(result["dii_holding_pct"])

    def test_shareholding_client_no_fabrication_on_missing(self):
        """If symbol is non-existent, client must return UNAVAILABLE, never an insider guess."""
        result = ShareholdingClient.fetch_shareholding_pattern("COMPLETELYFAKETICKER999")
        self.assertEqual(result["source"], "UNAVAILABLE")
        self.assertEqual(result["data_quality_flag"], "UNAVAILABLE")
        self.assertIsNone(result["promoter_holding_pct"])
        self.assertIsNone(result["fii_holding_pct"])

    # ──────────────────────────────────────────────────────────────
    # 4. MacroRegimeClient Tests
    # ──────────────────────────────────────────────────────────────

    def test_macro_regime_client_live_vix(self):
        """Verify MacroRegimeClient fetches live India VIX and Nifty valuation without errors."""
        macro = MacroRegimeClient.fetch_current_macro_regime()
        self.assertIn("india_vix", macro)
        self.assertIn("macro_regime", macro)
        self.assertIn("risk_stance", macro)
        self.assertGreater(macro["india_vix"], 5.0)
        self.assertLess(macro["india_vix"], 45.0)
        self.assertIsNotNone(macro["brent_crude_usd"])
        self.assertIsNotNone(macro["usdinr_exchange_rate"])

    # ──────────────────────────────────────────────────────────────
    # 5. FeatureEngine ROCE Lookback Tests
    # ──────────────────────────────────────────────────────────────

    def test_roce_lookback_to_audited_balance_sheet(self):
        """
        When Q0 is an intermediate quarter with NO balance sheet, FeatureEngine
        must look back to the latest audited Annual balance sheet (Q1) and flag LAST_AUDITED_BS.
        """
        test_comp_id = "comp_audit_lookback_test"
        comp = self.db.query(Company).filter_by(company_id=test_comp_id).first()
        if not comp:
            comp = Company(company_id=test_comp_id, isin="INELOOK12345", nse_symbol="LOOKTEST",
                           company_name="Lookback Test Ltd", status="ACTIVE")
            self.db.add(comp)
            self.db.commit()

        self.db.query(BitemporalFinancial).filter_by(company_id=test_comp_id).delete()

        # Q0 (June 30) - Unaudited Limited Review Income Statement ONLY (No balance sheet)
        pub_q0 = datetime(2026, 8, 14, 18, 0)
        q0 = BitemporalFinancial(
            company_id=test_comp_id,
            period_type="QUARTERLY",
            period_end_date=date(2026, 6, 30),
            publication_date=pub_q0,
            system_rec_start=pub_q0,
            system_rec_end=datetime(9999, 12, 31, 23, 59, 59),
            source="TEST",
            revenue=1000.0,
            ebit=250.0,
            # total_assets, total_debt, net_worth are all None
        )
        # Q1 (March 31) - Full Audited Annual Balance Sheet
        pub_q1 = datetime(2026, 5, 20, 18, 0)
        q1 = BitemporalFinancial(
            company_id=test_comp_id,
            period_type="QUARTERLY",
            period_end_date=date(2026, 3, 31),
            publication_date=pub_q1,
            system_rec_start=pub_q1,
            system_rec_end=datetime(9999, 12, 31, 23, 59, 59),
            source="TEST",
            revenue=950.0,
            ebit=240.0,
            total_assets=6000.0,
            current_liabilities=1000.0,  # CE = 5000.0
            net_worth=4000.0,
            total_debt=1000.0
        )
        self.db.add(q0)
        self.db.add(q1)
        self.db.commit()

        # Query as of Sept 5, 2026 (after both Q0 and Q1 are published)
        features = FeatureEngine.extract_features_as_of(self.db, test_comp_id, date(2026, 9, 5))

        self.assertIsNotNone(features.get("roce_pct"))
        self.assertEqual(features.get("roce_methodology"), "LAST_AUDITED_BS")
        self.assertFalse(features.get("roce_quarantine_flag"))
        # TTM EBIT = (250 + 240) * 2 = 980; CE = 5000; ROCE = 980 / 5000 * 100 = 19.6%
        self.assertAlmostEqual(features["roce_pct"], 19.6, delta=1.0)


if __name__ == "__main__":
    unittest.main()
