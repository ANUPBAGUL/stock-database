"""
Non-destructive ALTER TABLE migrations for Data Truth Audit changes.
Adds all new columns introduced in the 8-fix correctness remediation.
Safe to re-run — skips columns that already exist.
"""
from src.db.base import engine
from sqlalchemy import text, inspect

inspector = inspect(engine)

def safe_add_column(table, col_name, col_type_default):
    existing_cols = [c['name'] for c in inspector.get_columns(table)]
    if col_name not in existing_cols:
        ddl = f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type_default}"
        with engine.begin() as conn:
            conn.execute(text(ddl))
        print(f"  Added: {table}.{col_name}")
    else:
        print(f"  Skip (exists): {table}.{col_name}")

# ── shareholding_history ──
safe_add_column("shareholding_history", "other_dii_holding_pct", "REAL")
safe_add_column("shareholding_history", "consolidation_scope", "TEXT DEFAULT 'SEBI_LODR_PATTERN_FILING'")
safe_add_column("shareholding_history", "data_quality_flag", "TEXT DEFAULT 'HIGH_CONFIDENCE'")

# ── bitemporal_financials ──
safe_add_column("bitemporal_financials", "financial_debt_lt", "REAL")
safe_add_column("bitemporal_financials", "financial_debt_st", "REAL")
safe_add_column("bitemporal_financials", "lease_liabilities_lt", "REAL")
safe_add_column("bitemporal_financials", "lease_liabilities_st", "REAL")
safe_add_column("bitemporal_financials", "current_investments", "REAL")
safe_add_column("bitemporal_financials", "net_debt", "REAL")
safe_add_column("bitemporal_financials", "consolidation_scope", "TEXT DEFAULT 'CONSOLIDATED'")

# ── daily_prices_raw ──
safe_add_column("daily_prices_raw", "exchange", "TEXT DEFAULT 'NSE'")
safe_add_column("daily_prices_raw", "quote_type", "TEXT DEFAULT 'CLOSE'")
safe_add_column("daily_prices_raw", "price_source", "TEXT DEFAULT 'NSE_EOD'")
safe_add_column("daily_prices_raw", "quote_timestamp", "DATETIME")

# ── corporate_announcements ──
safe_add_column("corporate_announcements", "source_published_at", "DATETIME")
safe_add_column("corporate_announcements", "ingested_at", "DATETIME")
safe_add_column("corporate_announcements", "event_occurred_at", "DATETIME")
safe_add_column("corporate_announcements", "source_type", "TEXT DEFAULT 'OFFICIAL_EXCHANGE_FILING'")

# ── company_events ──
safe_add_column("company_events", "source_published_at", "DATETIME")
safe_add_column("company_events", "ingested_at", "DATETIME")
safe_add_column("company_events", "event_occurred_at", "DATETIME")
safe_add_column("company_events", "source_type", "TEXT DEFAULT 'OFFICIAL_EXCHANGE_FILING'")

print("\nAll ALTER TABLE migrations complete.")
