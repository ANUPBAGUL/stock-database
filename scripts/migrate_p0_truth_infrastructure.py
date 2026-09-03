"""
Non-destructive ALTER TABLE migrations for Institutional P0 Truth Infrastructure.
Adds orthogonal universe dimensions, machine-readable feature provenance, 
and wealth compounding / event-interval outcome columns.
Safe to re-run — skips columns that already exist.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

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

print("Running P0 schema migrations...")

# ── companies ──
safe_add_column("companies", "listing_status", "VARCHAR(32) DEFAULT 'ACTIVE'")
safe_add_column("companies", "tradability_status", "VARCHAR(32) DEFAULT 'TRADABLE'")
safe_add_column("companies", "liquidity_status", "VARCHAR(32) DEFAULT 'LIQUID'")
safe_add_column("companies", "research_eligibility", "VARCHAR(32) DEFAULT 'ELIGIBLE'")

# ── research_feature_snapshots ──
safe_add_column("research_feature_snapshots", "source_fact_ids", "JSON")
safe_add_column("research_feature_snapshots", "source_published_at", "DATETIME")
safe_add_column("research_feature_snapshots", "source_period_end", "DATE")
safe_add_column("research_feature_snapshots", "feature_engine_version", "VARCHAR(32) DEFAULT 'v3.2.0'")
safe_add_column("research_feature_snapshots", "peer_selection_version", "VARCHAR(32) DEFAULT 'v1.0.0'")
safe_add_column("research_feature_snapshots", "methodology_version", "VARCHAR(32) DEFAULT 'INSTITUTIONAL_P0'")
safe_add_column("research_feature_snapshots", "input_hash", "VARCHAR(64)")
safe_add_column("research_feature_snapshots", "output_hash", "VARCHAR(64)")

# ── forward_outcomes ──
safe_add_column("forward_outcomes", "wealth_start", "FLOAT DEFAULT 100.0")
safe_add_column("forward_outcomes", "wealth_end", "FLOAT")
safe_add_column("forward_outcomes", "cash_distributions_cr", "FLOAT DEFAULT 0.0")
safe_add_column("forward_outcomes", "corporate_proceeds_cr", "FLOAT DEFAULT 0.0")
safe_add_column("forward_outcomes", "terminal_equity_value_cr", "FLOAT")
safe_add_column("forward_outcomes", "cash_recovery_cr", "FLOAT")
safe_add_column("forward_outcomes", "total_realized_wealth_return_pct", "FLOAT")
safe_add_column("forward_outcomes", "label_start", "DATE")
safe_add_column("forward_outcomes", "label_end", "DATE")
safe_add_column("forward_outcomes", "horizon_type", "VARCHAR(16) DEFAULT '3Y'")
safe_add_column("forward_outcomes", "event_type", "VARCHAR(32)")
safe_add_column("forward_outcomes", "censoring_status", "VARCHAR(32) DEFAULT 'ONGOING'")
safe_add_column("forward_outcomes", "event_time_days", "INTEGER")

print("All P0 migrations complete.")
