"""
Unit Tests for NSE Security-Wise Delivery Client.
Tests official NSE archive bhavcopy downloading, CSV sanitization,
caching, date rollback, and 3-day delivery trajectory velocity.
"""

import os
import pytest
from datetime import date, timedelta
from src.ingestion.nse_delivery_client import NseDeliveryClient


class TestNseDeliveryClient:
    """Test suite for NseDeliveryClient."""

    def test_client_initialization_and_cache(self, tmp_path):
        """Tests that cache directory is created properly."""
        cache_dir = str(tmp_path / "nse_cache")
        client = NseDeliveryClient(cache_dir=cache_dir)
        assert os.path.exists(cache_dir)
        assert client._memory_cache == {}

    def test_csv_parsing_logic(self, tmp_path):
        """Tests parsing of official NSE bhavcopy format with leading spaces."""
        sample_csv = """SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER
RELIANCE, EQ, 08-Sep-2026, 1309.50, 1312.00, 1315.00, 1290.00, 1294.90, 1294.90, 1301.20, 10000000, 130120.00, 150000, 5800000, 58.00
MIDHANI, EQ, 08-Sep-2026, 420.00, 422.50, 482.40, 421.00, 477.00, 477.00, 465.00, 36000000, 167400.00, 200000, 3600000, 10.00
JUNK_BOND, GS, 08-Sep-2026, 100.00, 100.00, 100.00, 100.00, 100.00, 100.00, 100.00, 500, 5.00, 2, 500, 100.00
"""
        client = NseDeliveryClient(cache_dir=str(tmp_path))
        test_date = date(2026, 9, 8)
        records = client._parse_csv(sample_csv, test_date)

        # Verify equity stocks are captured and debt/bonds ignored
        assert "RELIANCE" in records
        assert "MIDHANI" in records
        assert "JUNK_BOND" not in records

        # Verify numerical fields
        rel = records["RELIANCE"]
        assert rel["symbol"] == "RELIANCE"
        assert rel["series"] == "EQ"
        assert rel["close_price"] == 1294.90
        assert rel["prev_close"] == 1309.50
        assert rel["traded_qty"] == 10000000
        assert rel["delivery_qty"] == 5800000
        assert rel["delivery_pct"] == 58.0
        assert rel["turnover_cr"] == 1301.20
        assert rel["delivery_turnover_cr"] == round(1301.20 * 0.58, 2)

        mid = records["MIDHANI"]
        assert mid["delivery_pct"] == 10.0
        assert mid["delivery_qty"] == 3600000

    def test_multi_day_trajectory_classification(self, tmp_path):
        """Tests classification of staircase accumulation vs distribution churn."""
        client = NseDeliveryClient(cache_dir=str(tmp_path))

        # Setup mock multi-day history in memory cache
        # Day 1: 25% delivery
        client._memory_cache["04092026"] = {
            "LEADER": {"symbol": "LEADER", "delivery_pct": 25.0, "delivery_qty": 250000, "turnover_cr": 50.0, "date": "2026-09-04"},
            "FADER": {"symbol": "FADER", "delivery_pct": 45.0, "delivery_qty": 450000, "turnover_cr": 80.0, "date": "2026-09-04"}
        }
        # Day 2: 38% delivery
        client._memory_cache["07092026"] = {
            "LEADER": {"symbol": "LEADER", "delivery_pct": 38.0, "delivery_qty": 420000, "turnover_cr": 70.0, "date": "2026-09-07"},
            "FADER": {"symbol": "FADER", "delivery_pct": 22.0, "delivery_qty": 200000, "turnover_cr": 60.0, "date": "2026-09-07"}
        }
        # Day 3: 55% delivery (Staircase!) vs 8% delivery (Distribution!)
        client._memory_cache["08092026"] = {
            "LEADER": {"symbol": "LEADER", "delivery_pct": 55.0, "delivery_qty": 650000, "turnover_cr": 95.0, "date": "2026-09-08"},
            "FADER": {"symbol": "FADER", "delivery_pct": 8.0, "delivery_qty": 80000, "turnover_cr": 120.0, "date": "2026-09-08"}
        }

        mock_dates = [date(2026, 9, 8), date(2026, 9, 7), date(2026, 9, 4)]

        # Evaluate LEADER
        leader_traj = client.get_multi_day_delivery("LEADER", num_days=3, available_dates=mock_dates)
        assert leader_traj["has_data"] is True
        assert leader_traj["latest_delivery_pct"] == 55.0
        assert leader_traj["trajectory_label"] == "STAIRCASE_ACCUMULATION"
        assert leader_traj["delivery_velocity"] > 0

        # Evaluate FADER
        fader_traj = client.get_multi_day_delivery("FADER", num_days=3, available_dates=mock_dates)
        assert fader_traj["has_data"] is True
        assert fader_traj["latest_delivery_pct"] == 8.0
        assert fader_traj["trajectory_label"] == "DISTRIBUTION_CHURN"
        assert fader_traj["delivery_velocity"] < 0
