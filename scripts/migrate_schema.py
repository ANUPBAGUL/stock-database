"""
Non-Destructive Database Schema Migration Script.

Safely checks existing SQLite tables, adds any missing columns via ALTER TABLE,
and creates all new 6-layer relational tables without losing any existing data.
"""

import os
import sys
import logging
from sqlalchemy import text

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.db.base import engine
from src.db.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("schema_migrator")


def get_existing_columns(conn, table_name: str) -> set:
    """Returns set of existing column names for a given SQLite table."""
    cursor = conn.execute(text(f"PRAGMA table_info({table_name})"))
    return {row[1] for row in cursor.fetchall()}


def migrate_schema():
    logger.info("Starting non-destructive schema migration...")

    # Column additions to check and apply safely if missing
    table_column_definitions = {
        "companies": [
            ("currency", "VARCHAR(8) DEFAULT 'INR'"),
            ("face_value", "FLOAT DEFAULT 10.0")
        ],
        "daily_prices_raw": [
            ("adjusted_close", "FLOAT"),
            ("deliverable_volume", "INTEGER"),
            ("delivery_pct", "FLOAT"),
            ("turnover", "FLOAT"),
            ("number_of_trades", "INTEGER"),
            ("vwap", "FLOAT")
        ],
        "bitemporal_financials": [
            ("period_start_date", "DATE"),
            ("source_document", "VARCHAR(255)"),
            ("data_version", "VARCHAR(16) DEFAULT 'v1'"),
            ("other_income", "FLOAT"),
            ("depreciation", "FLOAT"),
            ("interest_expense", "FLOAT"),
            ("pbt", "FLOAT"),
            ("tax_expense", "FLOAT"),
            ("eps_diluted", "FLOAT"),
            ("trade_receivables", "FLOAT"),
            ("inventories", "FLOAT"),
            ("other_current_assets", "FLOAT"),
            ("total_current_assets", "FLOAT"),
            ("ppe_gross", "FLOAT"),
            ("ppe_net", "FLOAT"),
            ("capital_wip", "FLOAT"),
            ("intangibles", "FLOAT"),
            ("trade_payables", "FLOAT"),
            ("short_term_debt", "FLOAT"),
            ("other_current_liabilities", "FLOAT"),
            ("current_liabilities", "FLOAT"),
            ("long_term_debt", "FLOAT"),
            ("equity_share_capital", "FLOAT"),
            ("reserves_and_surplus", "FLOAT"),
            ("investing_cash_flow", "FLOAT"),
            ("financing_cash_flow", "FLOAT"),
            ("free_cash_flow", "FLOAT")
        ],
        "corporate_announcements": [
            ("execution_timeline_months", "INTEGER"),
            ("document_hash", "VARCHAR(64)")
        ],
        "forward_outcomes": [
            ("market_cap_at_t0_cr", "FLOAT"),
            ("price_at_2x", "FLOAT"),
            ("date_2x", "DATE"),
            ("days_to_2x", "INTEGER"),
            ("price_at_5x", "FLOAT"),
            ("date_5x", "DATE"),
            ("days_to_5x", "INTEGER"),
            ("price_at_10x", "FLOAT"),
            ("date_10x", "DATE"),
            ("days_to_10x", "INTEGER"),
            ("maximum_run_pct", "FLOAT"),
            ("max_drawdown_before_2x", "FLOAT"),
            ("max_drawdown_before_5x", "FLOAT"),
            ("benchmark_nifty500_return_pct", "FLOAT"),
            ("sector_return_pct", "FLOAT"),
            ("alpha_generated_pct", "FLOAT"),
            ("survival_status", "VARCHAR(32) DEFAULT 'ACTIVE'"),
            ("daily_path_payload", "JSON")
        ],
        "multibagger_failure_diagnostics": [
            ("primary_failure_reason", "VARCHAR(64)"),
            ("secondary_failure_reasons", "JSON"),
            ("failure_evidence", "JSON"),
            ("failure_confidence", "FLOAT DEFAULT 0.90"),
            ("failure_detected_at", "DATE")
        ]
    }

    with engine.connect() as conn:
        for table, col_defs in table_column_definitions.items():
            # Check if table exists
            table_check = conn.execute(
                text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            ).fetchone()

            if table_check:
                existing_cols = get_existing_columns(conn, table)
                for col_name, col_type in col_defs:
                    if col_name not in existing_cols:
                        logger.info(f"Adding column '{col_name}' ({col_type}) to table '{table}'...")
                        try:
                            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
                        except Exception as e:
                            logger.warning(f"Note on adding {col_name} to {table}: {e}")

        conn.commit()

    # Create all new tables defined in SQLAlchemy Base metadata
    logger.info("Creating any new tables from Base.metadata...")
    Base.metadata.create_all(bind=engine)
    logger.info("Schema migration completed successfully! All tables up to date.")


if __name__ == "__main__":
    migrate_schema()
