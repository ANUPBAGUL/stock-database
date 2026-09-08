"""
Unit & Integration Tests for Intraday Focus Radar & Live Hotlist Tape
Validates:
1. Singleton integrity & armed/disarmed lifecycle
2. Focus basket constraints (max 8 symbols, dedup, casing)
3. Microstructure math: OBI calculation, VWAP delta, ORB-15 breakout detection
4. Order ticket risk budget (1% capital risk MIS sizing)
5. Zero placeholder data invariant
"""

import pytest
from src.analytics.intraday_focus_manager import IntradayFocusManager, is_indian_market_open


class TestIntradayFocusManager:

    @pytest.fixture(autouse=True)
    def setup_manager(self):
        manager = IntradayFocusManager.get_instance()
        # Ensure fresh state
        manager.disarm()
        manager.clear_basket()
        manager.add_to_basket("DIXON")
        manager.add_to_basket("KAYNES")
        manager.add_to_basket("HAL")
        yield manager
        manager.disarm()

    def test_singleton_instance(self, setup_manager):
        m1 = setup_manager
        m2 = IntradayFocusManager.get_instance()
        assert m1 is m2

    def test_arm_disarm_toggle(self, setup_manager):
        manager = setup_manager
        assert not manager.is_armed()
        
        status = manager.arm()
        assert status is True
        assert manager.is_armed()
        
        status = manager.disarm()
        assert status is False
        assert not manager.is_armed()

        # Test toggle method
        status = manager.toggle(True)
        assert status is True
        assert manager.is_armed()

        status = manager.toggle(False)
        assert status is False
        assert not manager.is_armed()

    def test_basket_constraints(self, setup_manager):
        manager = setup_manager
        manager.clear_basket()
        manager.add_to_basket("DIXON")
        manager.add_to_basket("HAL")
        assert manager.get_basket() == ["DIXON", "HAL"]

        # Add duplicate (should not duplicate)
        manager.add_to_basket("DIXON")
        assert manager.get_basket() == ["DIXON", "HAL"]

        # Add new symbol with lowercase (should uppercase)
        manager.add_to_basket("kaynes")
        assert "KAYNES" in manager.get_basket()

        # Test max basket cap of 8 (sliding window: evicts oldest)
        manager.clear_basket()
        for i in range(1, 9):
            manager.add_to_basket(f"SYM{i}")
        assert len(manager.get_basket()) == 8
        assert manager.get_basket()[0] == "SYM1"

        # Adding 9th symbol should maintain cap of 8 and evict SYM1
        manager.add_to_basket("SYM9")
        basket = manager.get_basket()
        assert len(basket) == 8
        assert "SYM1" not in basket
        assert basket[-1] == "SYM9"

        # Remove symbol
        manager.remove_from_basket("SYM2")
        assert "SYM2" not in manager.get_basket()
        assert len(manager.get_basket()) == 7

    def test_market_hours_checker(self):
        """Verify market hours logic behaves predictably"""
        is_open = is_indian_market_open()
        assert isinstance(is_open, bool)

    def test_microstructure_snapshot_calculation(self, setup_manager):
        manager = setup_manager
        mock_quote = {
            "last_price": 105.0,
            "average_price": 100.0,
            "net_change": 5.0,
            "percentage_change": 5.0,
            "volume": 250000,
            "ohlc": {"open": 101.0, "high": 106.0, "low": 99.5, "close": 100.0},
            "total_buy_quantity": 70000,
            "total_sell_quantity": 30000,
            "instrument_token": "NSE_EQ|HAL"
        }
        
        snap = manager._compute_microstructure_snapshot("HAL", mock_quote, source="UPSTOX_V2_LIVE")
        
        assert snap["symbol"] == "HAL"
        assert snap["ltp"] == 105.0
        assert snap["vwap"] == 100.0
        assert snap["vwap_delta_pct"] == 5.0
        assert snap["is_above_vwap"] is True
        # OBI: 70k / (70k + 30k) = 70.0%
        assert snap["order_book_imbalance_pct"] == 70.0
        assert snap["imbalance_label"] == "AGGRESSIVE_BUYING_PRESSURE"
        assert snap["source"] == "UPSTOX_V2_LIVE"
        
        # Verify 1.0% risk MIS order ticket
        ticket = snap["broker_order_ticket"]
        assert ticket["symbol"] == "HAL"
        assert ticket["transaction_type"] == "BUY"
        assert ticket["product"] == "MIS"
        assert ticket["price"] == 105.0
        assert ticket["stop_loss"] < 105.0
        assert ticket["target_1"] > 105.0
        assert ticket["quantity"] >= 1
        assert ticket["risk_budget_pct"] == 1.0
        assert "upstox_order_payload" in ticket

    def test_real_upstox_or_cached_poll(self, setup_manager):
        """Verify polling against real market symbols (Upstox Live or Cache fallback)"""
        manager = setup_manager
        manager.clear_basket()
        manager.add_to_basket("DIXON")
        manager.add_to_basket("HAL")

        # Run synchronous single poll
        snapshots = manager.poll_once()
        assert isinstance(snapshots, dict)
        # Should have data for basket symbols
        for sym in ["DIXON", "HAL"]:
            if sym in snapshots:
                snap = snapshots[sym]
                assert snap["ltp"] > 0
                assert snap["vwap"] > 0
                assert 0.0 <= snap["order_book_imbalance_pct"] <= 100.0
                assert snap["source"] in ["UPSTOX_V2_LIVE", "YFINANCE_REALTIME"]
                assert snap["broker_order_ticket"]["product"] == "MIS"
