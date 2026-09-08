"""
Unit Tests for MissingDataGuard & SectorNormalizer.
Phase 0.5 Data Hygiene Verification.
"""

import unittest
from src.screener.missing_data_guard import MissingDataGuard, SectorCategory


class TestMissingDataGuard(unittest.TestCase):

    def test_sector_resolution(self):
        """Verify sector resolution heuristics."""
        self.assertEqual(MissingDataGuard.resolve_sector("HDFCBANK", "HDFC Bank Ltd"), SectorCategory.FINANCIALS)
        self.assertEqual(MissingDataGuard.resolve_sector("BAJFINANCE", "Bajaj Finance Ltd"), SectorCategory.FINANCIALS)
        self.assertEqual(MissingDataGuard.resolve_sector("TATASTEEL", "Tata Steel Ltd"), SectorCategory.COMMODITIES_MATERIALS)
        self.assertEqual(MissingDataGuard.resolve_sector("ADANIPOWER", "Adani Power Ltd"), SectorCategory.UTILITIES_POWER)
        self.assertEqual(MissingDataGuard.resolve_sector("LT", "Larsen & Toubro Ltd"), SectorCategory.INDUSTRIALS_CAPGOODS)
        self.assertEqual(MissingDataGuard.resolve_sector("TCS", "Tata Consultancy Services"), SectorCategory.ASSET_LIGHT_GROWTH)

    def test_banking_roce_exemption(self):
        """Ensure banks are not penalized to 0 for missing ROCE and route to ROE."""
        raw_bank = {
            "symbol": "HDFCBANK",
            "company_name": "HDFC Bank Limited",
            "roce_pct": None,  # Naturally None in TradingView
            "roe_pct": 16.5,
            "debt_to_equity": 6.8, # Normal high bank leverage
            "opm_pct": 34.5,
            "sales_growth_pct": 14.0,
            "pe_ratio": 18.2
        }
        res = MissingDataGuard.normalize_candidate_fundamentals(raw_bank, is_local_db=False)
        self.assertEqual(res["sector_category"], SectorCategory.FINANCIALS)
        # Verify ROCE is NOT cast to 0.0
        self.assertIsNone(res["roce_pct"])
        # Verify ROE is used as effective quality metric
        self.assertEqual(res["effective_quality_metric"], 16.5)
        # Verify bank leverage is not penalized
        self.assertEqual(res["effective_solvency_metric"], 1.0)
        self.assertIn("ROCE exempt", res["sector_exemption_notes"])

    def test_negative_fcf_reinvestment_classifier(self):
        """Verify high-ROIC growth reinvestment is classified correctly (not as distress)."""
        # Case 1: High growth, high ROCE, safe debt -> GROWTH_REINVESTMENT
        eval1 = MissingDataGuard.classify_negative_fcf(
            fcf_cr=-150.0,
            roce_pct=22.0,
            roe_pct=20.0,
            rev_growth_pct=35.0,
            cagr_5y_pct=28.0,
            debt_to_equity=0.4,
            opm_pct=14.0,
            cash_cr=200.0,
            total_debt_cr=100.0
        )
        self.assertEqual(eval1["fcf_status"], "GROWTH_REINVESTMENT")
        self.assertTrue(eval1["is_reinvestment_grower"])

        # Case 2: Burning cash with low ROCE and high debt -> FCF_RISK
        eval2 = MissingDataGuard.classify_negative_fcf(
            fcf_cr=-400.0,
            roce_pct=4.0,
            roe_pct=3.0,
            rev_growth_pct=5.0,
            cagr_5y_pct=2.0,
            debt_to_equity=3.5,
            opm_pct=-2.0,
            cash_cr=20.0,
            total_debt_cr=500.0
        )
        self.assertEqual(eval2["fcf_status"], "FCF_RISK")
        self.assertFalse(eval2["is_reinvestment_grower"])

        # Case 3: Positive FCF -> CASH_GENERATIVE
        eval3 = MissingDataGuard.classify_negative_fcf(
            fcf_cr=500.0,
            roce_pct=25.0,
            roe_pct=22.0,
            rev_growth_pct=15.0,
            cagr_5y_pct=15.0,
            debt_to_equity=0.1,
            opm_pct=20.0
        )
        self.assertEqual(eval3["fcf_status"], "CASH_GENERATIVE")
        self.assertFalse(eval3["is_reinvestment_grower"])

    def test_data_provenance_and_quality(self):
        """Verify metadata provenance tags and setup data quality score."""
        raw_cand = {
            "symbol": "DIXON",
            "company_name": "Dixon Technologies Ltd",
            "roce_pct": 28.5,
            "debt_to_equity": 0.25,
            "opm_pct": 4.1,
            "sales_growth_pct": 48.0,
            "pe_ratio": 65.0,
            "fcf_cr": 120.0
        }
        res = MissingDataGuard.normalize_candidate_fundamentals(raw_cand, is_local_db=True)
        prov = res["metric_provenance"]
        self.assertEqual(prov["roce_pct"]["source"], "LOCAL_DB")
        self.assertEqual(prov["roce_pct"]["quality"], "CROSS_CHECKED")
        self.assertEqual(res["setup_data_quality"], 1.00)
        self.assertEqual(res["setup_quality_rating"], "FULL_OHLCV")

        # Test Cloud Proxy
        res_cloud = MissingDataGuard.normalize_candidate_fundamentals(raw_cand, is_local_db=False)
        self.assertEqual(res_cloud["setup_data_quality"], 0.75)
        self.assertEqual(res_cloud["setup_quality_rating"], "CLOUD_PROXY")

        # Test Limited Data
        raw_sparse = {"symbol": "TEST", "company_name": "Test Ltd", "roce_pct": None, "opm_pct": None}
        res_sparse = MissingDataGuard.normalize_candidate_fundamentals(raw_sparse, is_local_db=False)
        self.assertEqual(res_sparse["setup_data_quality"], 0.50)
        self.assertEqual(res_sparse["setup_quality_rating"], "LIMITED_DATA")


if __name__ == "__main__":
    unittest.main()
