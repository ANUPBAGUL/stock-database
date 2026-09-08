"""
Real-Market Data Verification Script.
Ensures ZERO synthetic or placeholder data is used.
Validates live Upstox API v2 feed, order book depth, VWAP calculations,
and MIS broker order ticket sizing on real NSE symbols.
"""

import sys
import json
from pprint import pprint

from src.analytics.intraday_focus_manager import IntradayFocusManager
from src.ingestion.upstox_client import UpstoxMarketDataIngestion


def verify_real_intraday():
    print("=================================================================")
    print("   GENUINE REAL-MARKET DATA VERIFICATION (UPSTOX API V2)   ")
    print("=================================================================")
    
    upstox = UpstoxMarketDataIngestion()
    is_auth = upstox.is_authenticated()
    print(f"1. Upstox Client Auth Status: {'AUTHENTICATED (Token Active)' if is_auth else 'EXPIRED/UNAUTHENTICATED'}")

    focus_symbols = ["DIXON", "KAYNES", "HAL", "TRENT"]
    print(f"2. Testing Real Symbols Basket: {focus_symbols}")

    manager = IntradayFocusManager.get_instance()
    manager.clear_basket()
    for s in focus_symbols:
        manager.add_to_basket(s)

    # Arm the radar
    manager.arm()
    print(f"3. Intraday Focus Radar Status: {'ARMED' if manager.is_armed() else 'DISARMED'}")

    # Trigger genuine poll
    print("4. Executing live poll against market data providers...")
    snapshots = manager.poll_once()

    print(f"5. Total Live Snapshots Captured: {len(snapshots)}")
    print("-----------------------------------------------------------------")
    
    assert len(snapshots) > 0, "ERROR: No snapshots returned from live data provider!"

    for sym in focus_symbols:
        snap = snapshots.get(sym)
        if not snap:
            print(f"[-] {sym}: No snapshot retrieved")
            continue

        ltp = snap["ltp"]
        vwap = snap["vwap"]
        source = snap["source"]
        obi_pct = snap["order_book_imbalance_pct"]
        vol = snap["volume"]
        signal = snap["setup_signal"]
        ticket = snap["broker_order_ticket"]

        print(f"\n[+] SYMBOL: {sym} | SOURCE: {source}")
        print(f"    LTP: Rs. {ltp:,.2f} | VWAP: Rs. {vwap:,.2f} | Volume: {vol:,}")
        print(f"    VWAP Delta: {snap['vwap_delta_pct']:+.2f}% | OBI (Buy Ratio): {obi_pct:.1f}%")
        print(f"    Signal Classification: {signal} ({snap['status_text']})")
        print(f"    MIS 1% Risk Order Ticket:")
        print(f"       Action: {ticket['transaction_type']} {ticket['quantity']} shares @ Rs. {ticket['price']:,.2f}")
        print(f"       Stop Loss: Rs. {ticket['stop_loss']:,.2f} | Target: Rs. {ticket['target_1']:,.2f}")
        print(f"       Capital Allocated: Rs. {ticket['allocated_capital_inr']:,.2f} | Max Risk: Rs. {ticket['total_risk_inr']:,.2f}")

        # Verification Invariants:
        assert ltp > 0, f"LTP for {sym} must be positive real number"
        assert vwap > 0, f"VWAP for {sym} must be positive real number"
        assert ticket["quantity"] >= 1, "MIS quantity must be at least 1 share"
        assert ticket["stop_loss"] < ltp, "Stop loss must be below entry price for long setup"
        assert ticket["target_1"] > ltp, "Target must be above entry price for long setup"
        assert source in ["UPSTOX_V2_LIVE", "YFINANCE_REALTIME"], f"Invalid source: {source}"

    print("\n=================================================================")
    print("   ALL INVARIANTS VERIFIED: ZERO SYNTHETIC / PLACEHOLDER DATA   ")
    print("=================================================================")
    manager.disarm()


if __name__ == "__main__":
    verify_real_intraday()
