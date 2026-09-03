"""
8-Stage Company Growth Lifecycle Classifier.

Evaluates where a company sits in its growth trajectory at any Point-in-Time T0:
1. 1_EARLY_SMALL (Small scale, finding product-market expansion)
2. 2_SCALING (Aggressive revenue growth & capex investment)
3. 3_RAPID_EARNINGS_EXPANSION (EBITDA margins expanding, inflection in profitability)
4. 4_OPERATING_LEVERAGE (Fixed cost dilution, PAT growth > 1.5x revenue growth, high ROCE)
5. 5_INSTITUTIONAL_DISCOVERY (FII/DII accumulation, liquidity inflection)
6. 6_RERATING (Valuation multiples expanding alongside earnings compounding)
7. 7_MATURE (Stable cash cow, modest growth, high dividend payout)
8. 8_DECLINING (Structural margin/ROCE deterioration)
"""

import logging
from typing import Dict, Any, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session

from src.db.models import CompanyLifecycleHistory, Company

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LifecycleClassifier:
    """
    Deterministic rule engine for classifying company lifecycle stage.
    """

    STAGE_NUMERIC_MAP = {
        "1_EARLY_SMALL": 1,
        "2_SCALING": 2,
        "3_RAPID_EARNINGS_EXPANSION": 3,
        "4_OPERATING_LEVERAGE": 4,
        "5_INSTITUTIONAL_DISCOVERY": 5,
        "6_RERATING": 6,
        "7_MATURE": 7,
        "8_DECLINING": 8
    }

    @classmethod
    def classify_company_stage(
        cls,
        market_cap_cr: float,
        revenue_cr: float,
        revenue_growth_yoy_pct: float,
        ebitda_growth_yoy_pct: float,
        pat_growth_yoy_pct: float,
        roce_pct: float,
        roce_delta_bps: float, # Delta in ROCE over 1 year
        institutional_stake_pct: float,
        dividend_payout_pct: float = 0.0,
        pe_ratio: float = 20.0
    ) -> Dict[str, Any]:
        """
        Determines the exact 8-stage lifecycle classification.
        """
        stage = "2_SCALING"
        trigger = "REVENUE_GROWTH_REINVESTMENT"

        # 8. Declining Stage
        if roce_delta_bps < -500.0 and revenue_growth_yoy_pct < 5.0 and roce_pct < 12.0:
            stage = "8_DECLINING"
            trigger = "ROCE_AND_GROWTH_DETERIORATION"

        # 7. Mature Stage
        elif revenue_growth_yoy_pct < 10.0 and dividend_payout_pct > 35.0 and market_cap_cr > 20000.0:
            stage = "7_MATURE"
            trigger = "MATURE_CASH_COW_HIGH_DIVIDEND"

        # 1. Early Small Stage
        elif market_cap_cr < 1500.0 and revenue_cr < 300.0:
            stage = "1_EARLY_SMALL"
            trigger = "SMALL_SCALE_EARLY_EXPANSION"

        # 4. Operating Leverage Stage
        elif pat_growth_yoy_pct > (revenue_growth_yoy_pct * 1.4) and roce_pct >= 22.0 and revenue_growth_yoy_pct > 15.0:
            stage = "4_OPERATING_LEVERAGE"
            trigger = "PAT_GROWTH_OUTPACING_REVENUE_WITH_HIGH_ROCE"

        # 3. Rapid Earnings Expansion Stage
        elif ebitda_growth_yoy_pct > 30.0 and roce_delta_bps > 200.0:
            stage = "3_RAPID_EARNINGS_EXPANSION"
            trigger = "EBITDA_GROWTH_AND_MARGIN_INFLECTION"

        # 5. Institutional Discovery Stage
        elif 5.0 <= institutional_stake_pct <= 25.0 and revenue_growth_yoy_pct > 20.0 and market_cap_cr >= 2000.0:
            stage = "5_INSTITUTIONAL_DISCOVERY"
            trigger = "INSTITUTIONAL_STAKE_EXPANSION"

        # 6. Rerating Stage
        elif pe_ratio > 35.0 and revenue_growth_yoy_pct > 25.0 and roce_pct > 25.0:
            stage = "6_RERATING"
            trigger = "VALUATION_EXPANSION_WITH_HIGH_COMPOUNDING"

        # 2. Scaling (Default Growth Stage)
        else:
            stage = "2_SCALING"
            trigger = "STEADY_BUSINESS_SCALING"

        return {
            "stage": stage,
            "stage_numeric_order": cls.STAGE_NUMERIC_MAP[stage],
            "transition_trigger": trigger,
            "market_cap_cr": market_cap_cr,
            "roce_pct": roce_pct,
            "revenue_growth_yoy_pct": revenue_growth_yoy_pct,
            "institutional_stake_pct": institutional_stake_pct,
            "stage_confidence": 1.00
        }

    @classmethod
    def record_lifecycle_state(
        cls,
        db: Session,
        company_id: str,
        observation_date: date,
        publication_timestamp: datetime,
        metrics: Dict[str, Any]
    ) -> CompanyLifecycleHistory:
        """
        Computes and stores the company lifecycle record in the database.
        """
        classification = cls.classify_company_stage(
            market_cap_cr=metrics.get("market_cap_cr", 1000.0),
            revenue_cr=metrics.get("revenue_cr", 500.0),
            revenue_growth_yoy_pct=metrics.get("revenue_growth_yoy_pct", 20.0),
            ebitda_growth_yoy_pct=metrics.get("ebitda_growth_yoy_pct", 25.0),
            pat_growth_yoy_pct=metrics.get("pat_growth_yoy_pct", 30.0),
            roce_pct=metrics.get("roce_pct", 20.0),
            roce_delta_bps=metrics.get("roce_delta_bps", 100.0),
            institutional_stake_pct=metrics.get("institutional_stake_pct", 10.0),
            dividend_payout_pct=metrics.get("dividend_payout_pct", 0.0),
            pe_ratio=metrics.get("pe_ratio", 25.0)
        )

        existing = db.query(CompanyLifecycleHistory).filter_by(
            company_id=company_id,
            observation_date=observation_date
        ).first()

        if not existing:
            rec = CompanyLifecycleHistory(
                company_id=company_id,
                observation_date=observation_date,
                publication_timestamp=publication_timestamp,
                stage=classification["stage"],
                stage_numeric_order=classification["stage_numeric_order"],
                transition_trigger=classification["transition_trigger"],
                market_cap_cr=classification["market_cap_cr"],
                roce_pct=classification["roce_pct"],
                revenue_growth_yoy_pct=classification["revenue_growth_yoy_pct"],
                institutional_stake_pct=classification["institutional_stake_pct"],
                stage_confidence=classification["stage_confidence"]
            )
            db.add(rec)
        else:
            rec.stage = classification["stage"]
            rec.stage_numeric_order = classification["stage_numeric_order"]
            rec.transition_trigger = classification["transition_trigger"]
            rec.market_cap_cr = classification["market_cap_cr"]
            rec.roce_pct = classification["roce_pct"]
            rec.revenue_growth_yoy_pct = classification["revenue_growth_yoy_pct"]

        db.commit()
        return rec
