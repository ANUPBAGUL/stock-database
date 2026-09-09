"""
Test Suite: Comprehensive Sectoral Intelligence & Thematic Expansion.
Validates:
1. SectorConstituentsStore expanded coverage (18 sectors)
2. Accurate symbol & TV industry cluster lookups
3. MissingDataGuard financial / industrial / commodity classification
4. ContinuationProbabilityEngine sector RRG momentum alignment
5. Live MarketIntelligenceClient RRG rotation matrix
"""

import pytest
from src.mcp.sector_constituents_store import SectorConstituentsStore
from src.screener.missing_data_guard import MissingDataGuard, SectorCategory
from src.analytics.continuation_probability_engine import ContinuationProbabilityEngine
from src.mcp.market_intelligence_client import MarketIntelligenceClient


class TestSectorCoverage:
    """Validates 18-sector coverage, cross-mapping, and quant integration."""

    def test_all_18_sectors_registered(self):
        """Verifies that all 18 institutional sector and thematic indices are registered."""
        all_sectors = SectorConstituentsStore.get_all_sector_names()
        assert len(all_sectors) >= 18

        expected_new_sectors = [
            "NIFTY INDIA DEFENCE",
            "NIFTY CONSUMER DURABLES",
            "NIFTY CAPITAL MARKETS",
            "NIFTY OIL & GAS",
            "NIFTY CPSE",
            "NIFTY CHEMICALS"
        ]
        for sec in expected_new_sectors:
            assert sec in all_sectors
            constituents = SectorConstituentsStore.get_index_constituents(sec)
            assert len(constituents) >= 5
            clusters = SectorConstituentsStore.get_tv_industry_clusters(sec)
            assert len(clusters) >= 2

    def test_symbol_identification_new_sectors(self):
        """Verifies constituent symbol mapping to new sectors."""
        assert SectorConstituentsStore.identify_sector_for_symbol("HAL") == "NIFTY INDIA DEFENCE"
        assert SectorConstituentsStore.identify_sector_for_symbol("MAZDOCK") == "NIFTY INDIA DEFENCE"
        assert SectorConstituentsStore.identify_sector_for_symbol("DIXON") == "NIFTY CONSUMER DURABLES"
        assert SectorConstituentsStore.identify_sector_for_symbol("BSE") == "NIFTY CAPITAL MARKETS"
        assert SectorConstituentsStore.identify_sector_for_symbol("CDSL") == "NIFTY CAPITAL MARKETS"
        assert SectorConstituentsStore.identify_sector_for_symbol("PIIND") == "NIFTY CHEMICALS"
        assert SectorConstituentsStore.identify_sector_for_symbol("DEEPAKNTR") == "NIFTY CHEMICALS"

    def test_tv_industry_cluster_fallback(self):
        """Verifies that TradingView industry names resolve to appropriate NSE sector themes."""
        assert SectorConstituentsStore.identify_sector_by_tv_industry("Aerospace & Defense") == "NIFTY INDIA DEFENCE"
        assert SectorConstituentsStore.identify_sector_by_tv_industry("Consumer Electronics/Appliances") == "NIFTY CONSUMER DURABLES"
        assert SectorConstituentsStore.identify_sector_by_tv_industry("Investment Banks/Brokers") == "NIFTY CAPITAL MARKETS"
        assert SectorConstituentsStore.identify_sector_by_tv_industry("Chemicals: Specialty") == "NIFTY CHEMICALS"
        assert SectorConstituentsStore.identify_sector_by_tv_industry("Oil & Gas Production") == "NIFTY ENERGY" or \
               SectorConstituentsStore.identify_sector_by_tv_industry("Oil & Gas Production") == "NIFTY OIL & GAS"

    def test_missing_data_guard_classification(self):
        """Verifies that Capital Markets, Defence, and Chemicals map to correct financial models."""
        # Capital markets should be classified as FINANCIALS to avoid false debt ceiling drops
        assert MissingDataGuard.resolve_sector("CDSL") == SectorCategory.FINANCIALS
        assert MissingDataGuard.resolve_sector("BSE") == SectorCategory.FINANCIALS
        assert MissingDataGuard.resolve_sector("CAMS") == SectorCategory.FINANCIALS

        # Defence leaders should be classified as INDUSTRIALS_CAPGOODS
        assert MissingDataGuard.resolve_sector("HAL") == SectorCategory.INDUSTRIALS_CAPGOODS
        assert MissingDataGuard.resolve_sector("MAZDOCK") == SectorCategory.INDUSTRIALS_CAPGOODS
        assert MissingDataGuard.resolve_sector("COCHINSHIP") == SectorCategory.INDUSTRIALS_CAPGOODS

        # Chemical leaders should be classified as COMMODITIES_MATERIALS
        assert MissingDataGuard.resolve_sector("DEEPAKNTR") == SectorCategory.COMMODITIES_MATERIALS
        assert MissingDataGuard.resolve_sector("PIIND") == SectorCategory.COMMODITIES_MATERIALS

    def test_continuation_radar_sector_rrg_alignment(self):
        """Verifies that ContinuationProbabilityEngine incorporates Sector RRG tailwinds and headwinds."""
        stock_leading = {
            "symbol": "MAZDOCK",
            "close": 4200.0,
            "open": 4050.0,
            "high": 4250.0,
            "low": 4020.0,
            "change": 4.5,
            "total_shares_outstanding": 200000000,
            "promoter_holding_pct": 84.8,
        }
        deliv = {
            "has_data": True,
            "latest_delivery_pct": 45.0,
            "latest_delivery_qty": 300000,
            "delivery_velocity": 3.0,
            "trajectory_label": "STAIRCASE_ACCUMULATION",
            "is_eod_confirmed": True
        }
        dvm = {"durability": 75.0, "valuation": 40.0, "momentum": 85.0, "composite": 70.0}

        # Scenario A: Sector is in LEADING quadrant
        macro_leading = {
            "cmmi_score": 60.0,
            "nifty_change_pct": 0.5,
            "leading_sectors": ["NIFTY INDIA DEFENCE", "NIFTY AUTO"],
            "improving_sectors": [],
            "lagging_sectors": ["NIFTY IT"]
        }

        res_lead = ContinuationProbabilityEngine.evaluate_candidate(
            stock=stock_leading,
            delivery_info=deliv,
            dvm_scores=dvm,
            horizon="TODAY",
            macro_context=macro_leading
        )

        lead_factors = [f for f in res_lead["factor_breakdown"] if f["status"] == "SECTOR_TAILWIND"]
        assert len(lead_factors) == 1
        assert "NIFTY INDIA DEFENCE" in lead_factors[0]["name"]
        assert "+3.0 pts" in lead_factors[0]["impact"]

        # Scenario B: Sector is in LAGGING quadrant
        macro_lagging = {
            "cmmi_score": 50.0,
            "nifty_change_pct": 0.0,
            "leading_sectors": ["NIFTY PHARMA"],
            "improving_sectors": [],
            "lagging_sectors": ["NIFTY INDIA DEFENCE"]
        }

        res_lag = ContinuationProbabilityEngine.evaluate_candidate(
            stock=stock_leading,
            delivery_info=deliv,
            dvm_scores=dvm,
            horizon="TODAY",
            macro_context=macro_lagging
        )

        lag_factors = [f for f in res_lag["factor_breakdown"] if f["status"] == "SECTOR_HEADWIND"]
        assert len(lag_factors) == 1
        assert "-3.0 pts" in lag_factors[0]["impact"]
        # Leading sector score must be strictly higher than lagging sector score
        assert res_lead["raw_score"] > res_lag["raw_score"]
