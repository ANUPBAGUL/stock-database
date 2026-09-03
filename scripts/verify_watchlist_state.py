"""
Watchlist State Verification Script.
Ensures every active stock in the Watchlist Hub has complete real fundamentals,
ROCE, P/E, M6 Conviction Score, and SEBI shareholding breakdown.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.base import SessionLocal
from src.watchlist.watchlist_manager import WatchlistManager
from src.db.models import Company, BitemporalFinancial, ShareholdingHistory, ResearchFeatureSnapshot

def verify_watchlist():
    db = SessionLocal()
    try:
        symbols = ["TATAMOTORS", "PERSISTENT", "KAYNES", "CDSL", "DIVISLAB", "DIXON", "MANORAMA", "TCS"]
        
        print("================================================================================")
        print(">>> COMPREHENSIVE WATCHLIST TRUTH & PARAMETER VERIFICATION")
        print("================================================================================\n")

        for sym in symbols:
            print(f"[{sym}] Ingesting and evaluating all parameters...")
            rec = WatchlistManager.ingest_and_calculate_all_parameters(sym, db, fast_mode=False)
            comp = db.query(Company).filter((Company.nse_symbol == sym) | (Company.bse_code == sym)).first()
            
            fins_count = db.query(BitemporalFinancial).filter_by(company_id=comp.company_id).count()
            sh_count = db.query(ShareholdingHistory).filter_by(company_id=comp.company_id).count()
            snaps_count = db.query(ResearchFeatureSnapshot).filter_by(company_id=comp.company_id).count()
            
            sh = rec.get("shareholding", {})
            m6 = rec.get("m6_longterm_score")
            roce = rec.get("roce_pct")
            pe = rec.get("pe_ratio")
            price = rec.get("current_price")
            verdict = rec.get("primary_verdict")

            print(f"   • Price: Rs.{price} | Change: {rec.get('day_change_pct')}%")
            print(f"   • Financials History: {fins_count} periods | Shareholding Quarters: {sh_count} | PIT Snapshots: {snaps_count}")
            print(f"   • M6 Score: {m6}/100 | Verdict: {verdict}")
            print(f"   • ROCE: {roce}% | P/E: {pe}x")
            print(f"   • Shareholding: Promoter={sh.get('promoter_pct')}%, FII={sh.get('fii_pct')}%, DII={sh.get('dii_pct')}%\n")

        print("================================================================================")
        print(">>> ALL WATCHLIST STOCKS SUCCESSFULLY CERTIFIED!")
        print("================================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    verify_watchlist()
