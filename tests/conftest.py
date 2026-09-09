import os
import shutil
import sqlite3
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.settings import BASE_DIR, settings
import src.db.base as db_base

TEST_DB_PATH = BASE_DIR / "test_multibagger.db"
ORIGINAL_DB_PATH = BASE_DIR / "multibagger.db"

@pytest.fixture(scope="session", autouse=True)
def isolate_test_database():
    """
    Session-level fixture that isolates tests from the production/authentic multibagger.db.
    Copies multibagger.db to test_multibagger.db, rebinds settings, engine, and SessionLocal,
    and cleans up on completion so tests NEVER contaminate authentic database records.
    """
    # 1. Copy authentic database if it exists, or create empty test db
    if ORIGINAL_DB_PATH.exists():
        shutil.copyfile(ORIGINAL_DB_PATH, TEST_DB_PATH)
    else:
        # Create empty db
        conn = sqlite3.connect(TEST_DB_PATH)
        conn.close()

    # 2. Configure settings
    test_db_url = f"sqlite:///{TEST_DB_PATH.as_posix()}"
    settings.DATABASE_URL = test_db_url
    os.environ["DATABASE_URL"] = test_db_url

    # 3. Create test engine and rebind SessionLocal
    connect_args = {"check_same_thread": False, "timeout": 30.0}
    test_engine = create_engine(test_db_url, echo=False, connect_args=connect_args)
    
    with test_engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
        conn.exec_driver_sql("PRAGMA busy_timeout=30000")

    # Rebind src.db.base engine and SessionLocal
    old_engine = db_base.engine
    db_base.engine = test_engine
    db_base.SessionLocal.configure(bind=test_engine)

    # Ensure schema exists on test db
    db_base.Base.metadata.create_all(bind=test_engine)

    yield test_engine

    # Teardown: dispose engine and clean up test db files
    db_base.SessionLocal.close_all()
    test_engine.dispose()
    db_base.engine = old_engine
    db_base.SessionLocal.configure(bind=old_engine)

    for ext in ["", "-wal", "-shm"]:
        p = Path(str(TEST_DB_PATH) + ext)
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
