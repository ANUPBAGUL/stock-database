"""
Integration Tests for Continuation Radar REST API Endpoint.
Tests GET /api/screener/continuation-radar across TODAY, WEEKLY, and YEARLY horizons.
"""

import json
import socket
import urllib.request
import pytest


def is_server_listening(host="127.0.0.1", port=8060, timeout=0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not is_server_listening(), reason="Integration test requires running hub server on port 8060")
class TestContinuationRadarApi:
    """Integration test suite for the Continuation Radar API."""

    BASE_URL = "http://127.0.0.1:8060/api/screener/continuation-radar"

    def test_today_horizon_endpoint(self):
        """Tests TODAY horizon returns valid candidates with full microstructure."""
        url = f"{self.BASE_URL}?horizon=TODAY&limit=5"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))

        assert data["success"] is True
        assert data["horizon"] == "TODAY"
        assert "summary" in data
        assert data["summary"]["total_analyzed"] > 0
        assert "tradingview_watchlist_string" in data
        assert "NSE:" in data["tradingview_watchlist_string"]

        candidates = data["candidates"]
        assert len(candidates) > 0
        cand = candidates[0]

        # Verify microstructure & delivery fields
        assert "symbol" in cand
        assert "cmp" in cand
        assert "continuation_probability_pct" in cand
        assert 10.0 <= cand["continuation_probability_pct"] <= 95.0
        assert "delivery_pct" in cand
        assert "clv_pct" in cand
        assert "verdict" in cand
        assert cand["verdict"] in [
            "GAP_AND_GO_CANDIDATE", "PULLBACK_ACCUMULATION",
            "RANGE_BOUND_DIGESTION", "RETAIL_TRAP_FADE_RISK",
            "CIRCUIT_LOCKED_ILLIQUID"
        ]
        assert "provenance_mode" in cand
        assert "is_circuit_locked" in cand
        assert "macro_multiplier" in cand

        # Verify execution rules & devil's advocate
        assert "orb15_playbook" in cand
        assert "gap_up_rule" in cand["orb15_playbook"]
        assert "trade_brackets" in cand
        assert "recommended_entry" in cand["trade_brackets"]
        assert "stop_loss" in cand["trade_brackets"]
        assert "target_1_2r" in cand["trade_brackets"]
        assert "devils_advocate_invalidation" in cand
        assert len(cand["devils_advocate_invalidation"]) > 20

    def test_weekly_horizon_endpoint(self):
        """Tests WEEKLY horizon returns 5-day momentum leaders."""
        url = f"{self.BASE_URL}?horizon=WEEKLY&limit=5"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))

        assert data["success"] is True
        assert data["horizon"] == "WEEKLY"
        assert len(data["candidates"]) > 0

    def test_yearly_horizon_endpoint(self):
        """Tests YEARLY horizon returns multi-bagger compounders."""
        url = f"{self.BASE_URL}?horizon=YEARLY&limit=5"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))

        assert data["success"] is True
        assert data["horizon"] == "YEARLY"
        assert len(data["candidates"]) > 0

    def test_sort_by_delivery(self):
        """Tests sorting candidates by delivery percentage."""
        url = f"{self.BASE_URL}?horizon=TODAY&sort_by=delivery_pct&limit=5"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))

        candidates = data["candidates"]
        assert len(candidates) >= 2
        # Verify non-ascending order of delivery_pct
        for i in range(len(candidates) - 1):
            assert candidates[i]["delivery_pct"] >= candidates[i + 1]["delivery_pct"]
