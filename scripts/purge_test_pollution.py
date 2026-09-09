import sqlite3
import os
import shutil

def purge_test_pollution():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "multibagger.db")
    bak_path = os.path.join(base_dir, "multibagger.db.bak")

    # Verify backup exists
    if not os.path.exists(bak_path):
        print(f"Creating backup at {bak_path}...")
        shutil.copy2(db_path, bak_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Find test companies
    cursor.execute("""
        SELECT company_id, nse_symbol, company_name FROM companies
        WHERE nse_symbol LIKE '%TEST%'
           OR nse_symbol LIKE '%LOOK%'
           OR nse_symbol LIKE '%TRACE%'
           OR nse_symbol LIKE '%NOBS%'
           OR company_id LIKE '%test%'
           OR company_id LIKE '%xyz%'
           OR company_id LIKE '%abc%'
    """)
    test_rows = cursor.fetchall()
    print(f"Found {len(test_rows)} test/mock companies to purge:")
    test_cids = []
    for cid, sym, name in test_rows:
        print(f"  - [{sym}] {name} (ID: {cid})")
        test_cids.append(cid)

    if not test_cids:
        print("No test companies found. Database is clean.")
        conn.close()
        return

    # Delete records across all related tables
    tables_to_purge = [
        "bitemporal_financials",
        "daily_prices_raw",
        "quarterly_pit_states",
        "research_feature_snapshots",
        "decision_snapshots",
        "corporate_actions",
        "corporate_announcements",
        "shareholding_history",
        "reinvestment_metrics",
        "data_audit_traces",
        "raw_source_evidence",
        "universe_memberships",
        "truth_predictions",
        "truth_outcomes",
        "multibagger_failure_diagnostics",
        "companies"
    ]

    total_deleted = 0
    placeholders = ",".join(["?"] * len(test_cids))

    for tbl in tables_to_purge:
        try:
            cursor.execute(f"DELETE FROM \"{tbl}\" WHERE company_id IN ({placeholders})", test_cids)
            del_count = cursor.rowcount
            if del_count > 0:
                print(f"  Purged {del_count} rows from {tbl}")
                total_deleted += del_count
        except sqlite3.OperationalError as e:
            # Column might not exist in some table
            pass

    conn.commit()
    conn.close()
    print(f"\nPurge complete! Total {total_deleted} contaminated rows removed from multibagger.db.")

if __name__ == "__main__":
    purge_test_pollution()
