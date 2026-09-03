import logging
from datetime import date
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from src.db.models import HistoricalMultibaggerCase, Company

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HISTORICAL_CASES = [
    {
        "symbol": "VBL",
        "tag": "WINNER_10X",
        "start_date": date(2018, 1, 1),
        "end_date": date(2024, 6, 30),
        "initial_market_cap_crores": 12000.0,
        "peak_return_pct": 1250.0,
        "max_drawdown_pct": -22.5,
        "primary_catalysts": {
            "drivers": ["Territory expansion", "PepsiCo backward integration", "Energy drink Pepsico distribution", "Volume growth > 20%"]
        }
    },
    {
        "symbol": "TRENT",
        "tag": "WINNER_10X",
        "start_date": date(2019, 1, 1),
        "end_date": date(2024, 8, 1),
        "initial_market_cap_crores": 11000.0,
        "peak_return_pct": 1800.0,
        "max_drawdown_pct": -28.0,
        "primary_catalysts": {
            "drivers": ["Zudio rapid store addition", "Westside profitability", "High asset turnover", "Zero net debt retail model"]
        }
    },
    {
        "symbol": "DIXON",
        "tag": "WINNER_10X",
        "start_date": date(2019, 6, 1),
        "end_date": date(2024, 8, 1),
        "initial_market_cap_crores": 3500.0,
        "peak_return_pct": 2100.0,
        "max_drawdown_pct": -35.0,
        "primary_catalysts": {
            "drivers": ["PLI scheme beneficiary", "Mobile manufacturing shift to India", "EMS scale advantage"]
        }
    },
    {
        "symbol": "BEL",
        "tag": "WINNER_5X",
        "start_date": date(2020, 4, 1),
        "end_date": date(2024, 8, 1),
        "initial_market_cap_crores": 22000.0,
        "peak_return_pct": 650.0,
        "max_drawdown_pct": -18.0,
        "primary_catalysts": {
            "drivers": ["Defense indigenization push", "Order book to sales > 3x", "Operating margin expansion"]
        }
    }
]

def load_historical_dataset(db: Session) -> int:
    added = 0
    for case in HISTORICAL_CASES:
        comp = db.query(Company).filter_by(nse_symbol=case["symbol"]).first()
        if not comp:
            continue

        existing = db.query(HistoricalMultibaggerCase).filter_by(
            company_id=comp.company_id, start_date=case["start_date"]
        ).first()

        if not existing:
            rec = HistoricalMultibaggerCase(
                company_id=comp.company_id,
                tag=case["tag"],
                start_date=case["start_date"],
                end_date=case["end_date"],
                initial_market_cap_crores=case["initial_market_cap_crores"],
                peak_return_pct=case["peak_return_pct"],
                max_drawdown_pct=case["max_drawdown_pct"],
                primary_catalysts=case["primary_catalysts"]
            )
            db.add(rec)
            added += 1

    db.commit()
    logger.info(f"Loaded {added} historical winner/negative cases into dataset.")
    return added
