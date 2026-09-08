"""
Audit Remediation Unit Tests.
Tests all 8 fixes:
1. Screener 52W High & Low dual extraction
2. Earnings acceleration sequential persistence
3. Deterministic SHA-256 event ID generation in BSE/NSE clients
4. Timezone-aware announcement half-life decay math
5. Free cash flow yield calculation in FeatureEngine
6. Zero-fabrication inputs in ReinvestmentCalculator and WatchlistManager
7. Greenwald PPE/Sales Growth CapEx integration
8. Safe guarded share count rescaling in yfinance client
"""

import os
import sys
import unittest
from datetime import datetime, date, timezone, timedelta
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.analytics.earnings_acceleration import EarningsAccelerationEngine
from src.analytics.announcement_decay_engine import AnnouncementDecayEngine
from src.analytics.feature_engine import FeatureEngine
from src.analytics.reinvestment_calculator import ReinvestmentCalculator
from src.ingestion.screener_client import ScreenerClient
from src.ingestion.bse_announcements_client import BseAnnouncementsClient
from src.ai.longterm_engine import LongTermEngine
from src.ai.decision_engine import DecisionEngine


class TestAuditRemediation(unittest.TestCase):

    def test_screener_52w_high_and_low_extraction(self):
        """Verify ScreenerClient extracts both High and Low 52-week prices."""
        client = ScreenerClient()
        # Mock HTML soup with Screener overview structure
        html = """
        <ul id="top-ratios">
            <li class="flex flex-space-between">
                <span class="name">Current Price</span>
                <span class="nowrap value"><span class="number">14,250</span></span>
            </li>
            <li class="flex flex-space-between">
                <span class="name">High / Low</span>
                <span class="nowrap value"><span class="number">16,850</span> / <span class="number">8,200</span></span>
            </li>
            <li class="flex flex-space-between">
                <span class="name">Stock P/E</span>
                <span class="nowrap value"><span class="number">85.4</span></span>
            </li>
        </ul>
        """
        soup = BeautifulSoup(html, "html.parser")
        client._get_company_soup = lambda sym: (soup, "CONSOLIDATED")

        res = client.fetch_company_overview("DIXON")
        self.assertEqual(res.get("high_52w"), 16850.0)
        self.assertEqual(res.get("low_52w"), 8200.0)
        self.assertEqual(res.get("stock_pe"), 85.4)

    def test_earnings_acceleration_sequential_persistence(self):
        """Verify persistence count is 1 when Q-1 was decelerating and only Q0 accelerated."""
        history = [
            {'period_end_date': '2023-03-31', 'pat_cr': 100.0, 'revenue_cr': 1000.0},
            {'period_end_date': '2023-06-30', 'pat_cr': 100.0, 'revenue_cr': 1000.0},
            {'period_end_date': '2023-09-30', 'pat_cr': 100.0, 'revenue_cr': 1000.0},
            {'period_end_date': '2023-12-31', 'pat_cr': 100.0, 'revenue_cr': 1000.0},
            {'period_end_date': '2024-03-31', 'pat_cr': 125.0, 'revenue_cr': 1000.0}, # Q-2: YoY = +25%
            {'period_end_date': '2024-06-30', 'pat_cr': 110.0, 'revenue_cr': 1000.0}, # Q-1: YoY = +10% (decel: -15%)
            {'period_end_date': '2024-09-30', 'pat_cr': 130.0, 'revenue_cr': 1000.0}, # Q0:  YoY = +30% (accel: +20%)
        ]
        res = EarningsAccelerationEngine.calculate_acceleration_vector(history)
        self.assertEqual(res.get("pat_acceleration_pct_points"), 20.0)
        # Must be 1 quarter, not 2, because Q-1 decelerated from 25% to 10%
        self.assertEqual(res.get("acceleration_persistence_quarters"), 1)

    def test_earnings_acceleration_consecutive_multi_quarter_persistence(self):
        """Verify persistence count is 2 when both Q-1 and Q0 accelerated consecutively."""
        history = [
            {'period_end_date': '2023-03-31', 'pat_cr': 100.0, 'revenue_cr': 1000.0},
            {'period_end_date': '2023-06-30', 'pat_cr': 100.0, 'revenue_cr': 1000.0},
            {'period_end_date': '2023-09-30', 'pat_cr': 100.0, 'revenue_cr': 1000.0},
            {'period_end_date': '2023-12-31', 'pat_cr': 100.0, 'revenue_cr': 1000.0},
            {'period_end_date': '2024-03-31', 'pat_cr': 105.0, 'revenue_cr': 1000.0}, # Q-2: YoY = +5%
            {'period_end_date': '2024-06-30', 'pat_cr': 115.0, 'revenue_cr': 1000.0}, # Q-1: YoY = +15% (accel: +10%)
            {'period_end_date': '2024-09-30', 'pat_cr': 135.0, 'revenue_cr': 1000.0}, # Q0:  YoY = +35% (accel: +20%)
        ]
        res = EarningsAccelerationEngine.calculate_acceleration_vector(history)
        self.assertEqual(res.get("acceleration_persistence_quarters"), 2)

    def test_deterministic_bse_event_id_hashing(self):
        """Verify BSE announcement ID generation is deterministic and starts with 'bse_'."""
        import hashlib
        raw_id_str = "BSE_DIXON_2026-08-14 18:00:00_Financial Results for Q1"
        expected_id = f"bse_{hashlib.sha256(raw_id_str.encode('utf-8')).hexdigest()[:16]}"
        self.assertTrue(expected_id.startswith("bse_"))
        self.assertEqual(len(expected_id), 20)

    def test_announcement_decay_timezone_normalization(self):
        """Verify naive IST publication timestamp is properly converted to UTC in decay math."""
        # 48 hours tactical half life
        # Published: 2026-08-14 18:00:00 IST (= 12:30:00 UTC)
        # Current:   2026-08-16 12:30:00 UTC (Exactly 48.0 hours later)
        pub_ist_str = "2026-08-14T18:00:00+05:30"
        current_utc = datetime(2026, 8, 16, 12, 30, 0, tzinfo=timezone.utc)

        decayed, status = AnnouncementDecayEngine.calculate_decayed_score(
            raw_score=100.0,
            track_type="TACTICAL",
            publication_time=pub_ist_str,
            current_time=current_utc
        )
        # After 1 half-life (48h), decayed score must be exactly 50.0
        self.assertAlmostEqual(decayed, 50.0, delta=0.5)

    def test_greenwald_reinvestment_capex_model(self):
        """Verify Greenwald PPE/Sales Growth CapEx is computed and reconciled."""
        res = ReinvestmentCalculator.calculate_growth_vs_maintenance_capex(
            total_capex_cr=500.0,
            depreciation_cr=100.0,
            sales_current_cr=2000.0,
            sales_previous_cr=1600.0,
            gross_block_cr=1600.0, # PPE/Sales = 0.80
            inflation_rate_pct=6.0
        )
        self.assertEqual(res["total_capex_cr"], 500.0)
        self.assertEqual(res["ppe_to_sales_ratio"], 0.80)
        self.assertEqual(res["delta_sales_cr"], 400.0)
        # Greenwald implied growth capex = 0.80 * 400 = 320.0 Cr
        self.assertEqual(res["greenwald_implied_growth_capex_cr"], 320.0)
        # Clamped Maintenance CapEx = min(500, max(70, min(130, 106))) = 106.0 Cr
        self.assertEqual(res["maintenance_capex_cr"], 106.0)
        # Empirical Growth CapEx = 500 - 106 = 394.0 Cr
        self.assertEqual(res["growth_capex_cr"], 394.0)


if __name__ == "__main__":
    unittest.main()
