import sqlite3
import os

def migrate():
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "multibagger.db")
    print(f"Opening database at {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(daily_prices_raw)")
    cols = [col[1] for col in cursor.fetchall()]
    if "is_split_adjusted" not in cols:
        print("Adding column is_split_adjusted to daily_prices_raw...")
        cursor.execute("ALTER TABLE daily_prices_raw ADD COLUMN is_split_adjusted BOOLEAN DEFAULT 0")
        conn.commit()
        print("Column added successfully.")
    else:
        print("Column is_split_adjusted already exists.")

    # Backfill: YFINANCE prices are pre-split-adjusted by Yahoo's servers
    cursor.execute("UPDATE daily_prices_raw SET is_split_adjusted = 1 WHERE price_source = 'YFINANCE'")
    updated_count = cursor.rowcount
    conn.commit()
    print(f"Updated {updated_count} YFINANCE rows to is_split_adjusted = 1.")

    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
