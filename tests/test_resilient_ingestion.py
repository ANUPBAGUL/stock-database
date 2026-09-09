"""
Tests for Resilient Exchange Ingestion, Anti-Hallucination Governance,
and Fail-Closed Architecture across Market Intelligence & Continuation Radar.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date

from src.ingestion.nse_delivery_client import NseDeliveryClient
from src.mcp.market_intelligence_client import MarketIntelligenceClient
import src.mcp.market_intelligence_client as mic_module
from src.analytics.continuation_probability_engine import ContinuationProbabilityEngine


class TestResilientIngestion:
    """Validates curl_cffi ingestion, TradingView failover, and fail-closed safety."""

    def test_nse_delivery_client_uses_curl_cffi_with_mirrors(self):
        """Ensures NseDeliveryClient initializes curl_cffi session with Chrome impersonation."""
        client = NseDeliveryClient()
        session = client._get_session()
        assert session is not None
        # Verify mirror URLs are configured
        assert len(client.ARCHIVE_URL_TEMPLATES) >= 2
        assert "archives.nseindia.com" in client.ARCHIVE_URL_TEMPLATES[0]
        assert "nsearchives.nseindia.com" in client.ARCHIVE_URL_TEMPLATES[1]

    @patch("curl_cffi.requests.Session.get")
    def test_nse_delivery_client_mirror_fallback_on_403(self, mock_get, tmp_path):
        """Verifies that 403 on primary mirror falls back to secondary mirror."""
        client = NseDeliveryClient(cache_dir=str(tmp_path))

        # First call fails with 403, second call succeeds with CSV content
        mock_resp_fail = MagicMock()
        mock_resp_fail.status_code = 403

        mock_resp_success = MagicMock()
        mock_resp_success.status_code = 200
        mock_resp_success.text = (
            "SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER\n"
            "RELIANCE, EQ, 02-Mar-2026, 1200.0, 1205.0, 1220.0, 1200.0, 1215.0, 1215.0, 1210.0, 100000, 1210.0, 5000, 50000, 50.00\n"
        )

        mock_get.side_effect = [mock_resp_fail, mock_resp_success]

        records = client.fetch_bhavcopy_for_date(date(2026, 3, 2))
        assert records is not None
        assert "RELIANCE" in records
        assert records["RELIANCE"]["delivery_pct"] == 50.00
        assert mock_get.call_count == 2

    @patch.object(MarketIntelligenceClient, "_fetch_indices_from_tradingview")
    def test_market_intel_tradingview_failover_when_nse_blocked(self, mock_tv):
        """Verifies automatic seamless failover to TradingView Scanner when NSE returns None/403."""
        client = MarketIntelligenceClient()

        # Mock NSE client returning None (Akamai WAF blocked)
        client.nse_client._api_get = MagicMock(return_value=None)

        # TradingView returns live macro telemetry
        mock_tv.return_value = {
            "indices": {
                "NSE:NIFTY": {"name": "NIFTY", "close": 24500.0, "day_change": 0.65, "perf_1m": 2.1},
                "NSE:CNX500": {"name": "NIFTY 500", "close": 22000.0, "day_change": 0.70, "perf_1m": 2.5},
                "NSE:CNXMIDCAP": {"name": "NIFTY MIDCAP", "close": 55000.0, "day_change": 0.85, "perf_1m": 3.0},
                "NSE:INDIAVIX": {"name": "INDIA VIX", "close": 12.8, "day_change": -0.4, "perf_1m": -5.0},
            },
            "advances": 3200,
            "declines": 1800,
            "source": "TRADINGVIEW_CLOUD"
        }

        intel = client.fetch_live_market_intelligence()

        assert intel["provenance_mode"] == "TRADINGVIEW_CLOUD_VERIFIED"
        assert intel["benchmark_nifty50"]["close"] == 24500.0
        assert intel["volatility_regime"]["india_vix"] == 12.8
        assert intel["cmmi_score"] is not None
        assert intel["cmmi_score"] > 0
        assert intel["overall_regime"] != "DATA_FEED_OFFLINE"

    @patch.object(MarketIntelligenceClient, "_fetch_indices_from_tradingview")
    def test_fail_closed_zero_hallucination_when_all_feeds_down(self, mock_tv):
        """
        CRITICAL INSTITUTIONAL FIREWALL:
        When both NSE and TradingView fail and no cache exists, the system MUST FAIL-CLOSED.
        It must NEVER invent fake VIX=13.0 or Breadth=50%.
        """
        client = MarketIntelligenceClient()
        client.nse_client._api_get = MagicMock(return_value=None)
        mock_tv.return_value = None

        # Reset in-memory cache to simulate fresh startup during full outage
        mic_module._LAST_KNOWN_GOOD_INTEL = None
        mic_module._LAST_GOOD_TIMESTAMP = 0.0

        intel = client.fetch_live_market_intelligence()

        assert intel["provenance_mode"] == "DATA_FEED_OFFLINE"
        assert intel["overall_regime"] == "DATA_FEED_OFFLINE"
        assert intel["risk_budget_pct"] == 25.0  # Safe defensive stance
        assert intel["cmmi_score"] is None
        assert intel["volatility_regime"]["india_vix"] is None
        assert "Exchange and cloud market data feeds unreachable" in intel["warning"]

    def test_continuation_radar_offline_macro_handling(self):
        """Verifies ContinuationProbabilityEngine gracefully handles cmmi_score=None without crashing or inventing 50.0."""
        stock = {
            "symbol": "TRENT",
            "close": 5000.0,
            "open": 4850.0,
            "high": 5020.0,
            "low": 4840.0,
            "change": 3.5,
            "total_shares_outstanding": 355000000,
            "promoter_holding_pct": 37.0,
        }
        deliv = {
            "has_data": True,
            "latest_delivery_pct": 48.0,
            "latest_delivery_qty": 500000,
            "delivery_velocity": 2.5,
            "trajectory_label": "STAIRCASE_ACCUMULATION",
            "is_eod_confirmed": True,
        }
        dvm = {"durability": 75.0, "valuation": 40.0, "momentum": 80.0, "composite": 68.0}

        # Pass macro context where telemetry is completely offline
        offline_macro = {
            "cmmi_score": None,
            "nifty_change_pct": 0.0,
            "regime": "DATA_FEED_OFFLINE"
        }

        eval_res = ContinuationProbabilityEngine.evaluate_candidate(
            stock=stock,
            delivery_info=deliv,
            dvm_scores=dvm,
            horizon="TODAY",
            macro_context=offline_macro
        )

        assert eval_res["macro_multiplier"] == 1.0
        # Factor breakdown must explicitly show OFFLINE status, not hallucinated values
        offline_factors = [f for f in eval_res["factor_breakdown"] if f["status"] == "OFFLINE"]
        assert len(offline_factors) == 1
        assert "Macro Telemetry Offline" in offline_factors[0]["name"]
        # Free-float FSAR should be calculated from total_shares and promoter_holding_pct
        assert eval_res["fsar_pct"] is not None
        assert eval_res["fsar_pct"] > 0

    def test_derived_free_float_fsar(self):
        """Verifies FSAR derives free-float from total_shares and promoter_holding_pct."""
        # Total shares: 100,000,000, Promoter: 60% -> Free float = 40,000,000
        # Delivered: 800,000 -> FSAR = (800,000 / 40,000,000) * 100 = 2.0%
        fsar = ContinuationProbabilityEngine.calculate_fsar(
            delivery_qty=800000,
            float_shares=None,
            total_shares=100000000,
            promoter_holding_pct=60.0
        )
        assert fsar == 2.0
