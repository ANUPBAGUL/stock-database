import os
import sys
import logging

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.db.base import engine
from src.db.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db(reset: bool = False):
    if reset:
        logger.info("Dropping existing database tables...")
        Base.metadata.drop_all(bind=engine)
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully!")

if __name__ == "__main__":
    init_db()
