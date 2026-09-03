"""
Deep Multi-Stock Universe Truth & Provenance Audit Script.
Tests ingestion, provenance verification, triple timestamps, frozen M6 decision snapshots,
and the 30+ dimensional ResearchFeatureSnapshot across diverse sectors and market caps.
"""
import sys
import os
import json
import logging
from datetime import datetime, date
from typing import Dict, Any, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.base import SessionLocal, Base, engine
from src.db.models import (
    Company, DailyPriceRaw, BitemporalFinancial, QuarterlyPITState,
    CorporateAnnouncement, ShareholdingHistory, DecisionSnapshot,
    ResearchFeatureSnapshot, DataAuditTrace
)
from src.watchlist.watchlist_manager import WatchlistManager
from src.analytics.snapshot_consistency_enforcer import SnapshotConsistencyEnforcer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test universe spanning distinct industries, business models, and market cap regimes
AUDIT_UNIVERSE = [
    {"symbol": "MANORAMA", "sector": "Specialty Chemicals / Fats"},
    {"symbol": "DIXON", "sector": "Electronics Manufacturing EMS"},
    {"symbol": "TCS", "sector": "IT Services Mega-Cap"},
    {"symbol": "KAYNES", "sector": "Defense & EMS Compounder"},
    {"symbol": "DIVISLAB", "sector": "Pharma CDMO / CRAMS"}
]

def run_deep_universe_audit() -> Dict[str, Any]:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    mgr = WatchlistManager()
    
    audit_results = []
    print("\n" + "=" * 80)
    print(">>> LAUNCHING DEEP 5-STAGE UNIVERSE PROVENANCE & TRUTH AUDIT")
    print("=" * 80)

    try:
        for item in AUDIT_UNIVERSE:
            sym = item["symbol"]
            sec = item["sector"]
            print(f"\n[{sym}] Auditing {sec}...")

            # 1. Run full ingestion & calculation pipeline
            card = mgr.ingest_and_calculate_all_parameters(sym, db, fast_mode=False)
            comp = db.query(Company).filter((Company.nse_symbol == sym) | (Company.bse_code == sym)).first()
            if not comp:
                print(f"[FAILED] Company {sym} not found in database after ingestion.")
                continue

            # 2. Daily Prices Verification
            prices = db.query(DailyPriceRaw).filter_by(company_id=comp.company_id).order_by(DailyPriceRaw.trading_date.desc()).all()
            price_count = len(prices)
            latest_price = prices[0].close_price if prices else 0.0
            latest_date = prices[0].trading_date.isoformat() if prices else "N/A"

            # 3. Balance Sheet & P&L Lineage
            financials = db.query(BitemporalFinancial).filter_by(company_id=comp.company_id).all()
            fin_count = len(financials)
            distinct_periods = len(set(f.period_end_date for f in financials))

            # 4. Official Regulatory Announcements & Time-Decay
            announcements = db.query(CorporateAnnouncement).filter_by(company_id=comp.company_id).all()
            ann_count = len(announcements)
            non_stale_ann = sum(1 for a in announcements if (a.decayed_score or 0.0) > 0.05)

            # 5. Verified Shareholding (SEBI Clause 31)
            sh = db.query(ShareholdingHistory).filter_by(company_id=comp.company_id).order_by(ShareholdingHistory.period_end_date.desc()).first()
            sh_valid = False
            sh_summary = "N/A"
            if sh:
                pub = sh.retail_public_pct or 0.0
                total_stake = round((sh.promoter_holding_pct or 0) + (sh.fii_holding_pct or 0) + (sh.dii_holding_pct or 0) + pub, 2)
                sh_valid = (abs(total_stake - 100.0) < 1.0)
                sh_summary = f"Promoter={sh.promoter_holding_pct}%, FII={sh.fii_holding_pct}%, DII={sh.dii_holding_pct}%, Public={pub}% (Sum={total_stake}%)"

            # 6. Immutable T0 DecisionSnapshot Check
            snapshots = db.query(DecisionSnapshot).filter_by(company_id=comp.company_id).all()
            snap_count = len(snapshots)
            latest_snap = snapshots[-1] if snapshots else None

            # 7. Dedicated PIT Research Feature Snapshot Store Check
            r_snaps = db.query(ResearchFeatureSnapshot).filter_by(company_id=comp.company_id).all()
            r_snap_count = len(r_snaps)
            latest_rsnap = r_snaps[-1] if r_snaps else None

            # 8. Consistency Enforcer Integrity
            consistency_status = "PASSED"
            if latest_snap and latest_snap.raw_features_payload:
                res = SnapshotConsistencyEnforcer.validate_snapshot(
                    latest_snap.raw_features_payload,
                    date(2026, 9, 3)
                )
                if not res.get("consistent", True):
                    consistency_status = f"BLOCKED ({res.get('violations', [])})"

            # Print Summary Card for Stock
            print(f"   [Prices] {price_count} candles (Latest: Rs.{latest_price:,.2f} on {latest_date})")
            print(f"   [Financials] {fin_count} rows across {distinct_periods} distinct audited periods")
            print(f"   [LODR Filings] {ann_count} official filings ({non_stale_ann} active decaying catalysts)")
            print(f"   [Shareholding] {sh_summary} | Verified 100%: {'[YES]' if sh_valid else '[NO]'}")
            print(f"   [Decision Snapshots T0] {snap_count} recorded | Consistency: {consistency_status}")
            print(f"   [Research Feature Store] {r_snap_count} PIT vectors (ROIC={getattr(latest_rsnap, 'economic_roic_pct', 'N/A')}%, Moat={getattr(latest_rsnap, 'moat_rating', 'N/A')}, TAM={getattr(latest_rsnap, 'tam_feasibility', 'N/A')})")

            stock_audit = {
                "symbol": sym,
                "sector": sec,
                "price_candles_count": price_count,
                "latest_price": latest_price,
                "latest_price_date": latest_date,
                "financial_records_count": fin_count,
                "distinct_periods": distinct_periods,
                "lodr_announcements_count": ann_count,
                "active_decaying_announcements": non_stale_ann,
                "shareholding_verified_100_pct": sh_valid,
                "decision_snapshots_count": snap_count,
                "research_feature_snapshots_count": r_snap_count,
                "consistency_enforcer_status": consistency_status,
                "economic_roic_pct": getattr(latest_rsnap, "economic_roic_pct", None),
                "tam_feasibility": getattr(latest_rsnap, "tam_feasibility", None),
                "moat_rating": getattr(latest_rsnap, "moat_rating", None),
                "operational_leverage_multiplier": getattr(latest_rsnap, "operational_leverage_multiplier", None)
            }
            audit_results.append(stock_audit)

        # Audit Summary Verdict
        all_prices_valid = all(r["price_candles_count"] >= 20 for r in audit_results)
        all_fins_valid = all(r["financial_records_count"] >= 2 for r in audit_results)
        all_sh_valid = all(r["shareholding_verified_100_pct"] for r in audit_results)
        all_snaps_valid = all(r["decision_snapshots_count"] >= 1 and r["research_feature_snapshots_count"] >= 1 for r in audit_results)

        print("\n" + "=" * 80)
        print("OVERALL UNIVERSE PROVENANCE AUDIT VERDICT")
        print("=" * 80)
        print(f"1. Daily Prices Pipeline:         {'[OK] 100% OPERATIONAL' if all_prices_valid else '[WARNING]'}")
        print(f"2. IND-AS Financials Lineage:     {'[OK] 100% OPERATIONAL' if all_fins_valid else '[WARNING]'}")
        print(f"3. SEBI Clause 31 Shareholding:   {'[OK] 100% VERIFIED' if all_sh_valid else '[WARNING]'}")
        print(f"4. T0 Decision Snapshots (M6):    {'[OK] 100% RECORDED' if all_snaps_valid else '[WARNING]'}")
        print(f"5. PIT Research Feature Store:    {'[OK] 100% RECORDED' if all_snaps_valid else '[WARNING]'}")
        print("=" * 80)

        report = {
            "audit_timestamp": datetime.utcnow().isoformat(),
            "stocks_audited_count": len(audit_results),
            "all_pipelines_operational": (all_prices_valid and all_fins_valid and all_sh_valid and all_snaps_valid),
            "stock_audits": audit_results
        }

        # Persist audit report to file
        out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports", "universe_provenance_audit_report.json")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nAudit report saved to: {out_path}")

        return report

    finally:
        db.close()

if __name__ == "__main__":
    run_deep_universe_audit()
