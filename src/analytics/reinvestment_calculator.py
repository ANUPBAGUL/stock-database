"""
Reinvestment Engine & Incremental Capital Allocation Trajectory Calculator.

Computes:
1. Incremental Capital Employed: Delta Capital Employed between Period(T) and Period(T-1)
2. Incremental EBIT: Delta Operating Earnings between Period(T) and Period(T-1)
3. Incremental ROCE: (Incremental EBIT / Incremental Capital Employed) * 100
4. Reinvestment Rate: (CapEx + Delta Working Capital) / CFO
5. Multi-Year Compounding Runway Assessment
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session

from src.db.models import BitemporalFinancial, ReinvestmentMetric, Company

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReinvestmentCalculator:
    """
    Computes empirical reinvestment efficiency and incremental returns on capital over time.
    """

    @staticmethod
    def calculate_incremental_roce_trajectory(
        db: Session, company_id: str
    ) -> List[Dict[str, Any]]:
        """
        Extracts annual / TTM bitemporal filings sorted chronologically and calculates
        the year-over-year incremental ROCE, incremental ROIC, and reinvestment rate.
        """
        filings = db.query(BitemporalFinancial).filter(
            BitemporalFinancial.company_id == company_id
        ).order_by(BitemporalFinancial.period_end_date.asc()).all()

        if len(filings) < 2:
            return []

        # Deduplicate to 1 statement per period_end_date (most recent publication)
        deduped = {}
        for f in filings:
            deduped[f.period_end_date] = f
        sorted_periods = sorted(deduped.keys())

        results = []
        for i in range(1, len(sorted_periods)):
            curr_f = deduped[sorted_periods[i]]
            prev_f = deduped[sorted_periods[i - 1]]

            # Compute Capital Employed for current and previous period
            # Capital Employed = Total Assets - Current Liabilities (or Net Worth + Total Debt)
            curr_assets = curr_f.total_assets or 0.0
            curr_cl = curr_f.current_liabilities or 0.0
            curr_nw = curr_f.net_worth or 0.0
            curr_debt = curr_f.total_debt or 0.0
            
            prev_assets = prev_f.total_assets or 0.0
            prev_cl = prev_f.current_liabilities or 0.0
            prev_nw = prev_f.net_worth or 0.0
            prev_debt = prev_f.total_debt or 0.0

            curr_ce = (curr_assets - curr_cl) if (curr_assets - curr_cl) > 50.0 else (curr_nw + curr_debt)
            prev_ce = (prev_assets - prev_cl) if (prev_assets - prev_cl) > 50.0 else (prev_nw + prev_debt)

            inc_cap = curr_ce - prev_ce
            inc_ebit = (curr_f.ebit or 0.0) - (prev_f.ebit or 0.0)
            inc_rev = (curr_f.revenue or 0.0) - (prev_f.revenue or 0.0)

            # Incremental ROCE
            inc_roce = None
            if inc_cap > 10.0: # Minimum ₹10 Cr incremental capital deployed
                calc_val = (inc_ebit / inc_cap) * 100.0
                inc_roce = round(min(200.0, max(-100.0, calc_val)), 2)

            # Reinvestment Rate: CapEx / CFO
            reinvest_rate = None
            if curr_f.operating_cash_flow and curr_f.operating_cash_flow > 0:
                reinvest_rate = round(((curr_f.capex or 0.0) / curr_f.operating_cash_flow) * 100.0, 2)

            metric_entry = {
                "company_id": company_id,
                "period_end_date": curr_f.period_end_date,
                "publication_timestamp": curr_f.publication_date,
                "incremental_capital_employed": round(inc_cap, 2),
                "incremental_ebit": round(inc_ebit, 2),
                "incremental_revenue": round(inc_rev, 2),
                "incremental_roce_pct": inc_roce,
                "reinvestment_rate": reinvest_rate,
                "fcf_reinvestment_rate": round(min(150.0, max(0.0, ((curr_f.capex or 0.0) / max(0.1, curr_f.revenue or 1.0)) * 100)), 2)
            }
            results.append(metric_entry)

            # Persist to reinvestment_metrics table
            existing = db.query(ReinvestmentMetric).filter_by(
                company_id=company_id,
                period_end_date=curr_f.period_end_date
            ).first()

            if not existing:
                rec = ReinvestmentMetric(
                    company_id=company_id,
                    period_end_date=curr_f.period_end_date,
                    publication_timestamp=curr_f.publication_date,
                    reinvestment_rate=reinvest_rate,
                    incremental_capital_employed=round(inc_cap, 2),
                    incremental_ebit=round(inc_ebit, 2),
                    incremental_revenue=round(inc_rev, 2),
                    incremental_roce_pct=inc_roce,
                    fcf_reinvestment_rate=metric_entry["fcf_reinvestment_rate"]
                )
                db.add(rec)
            else:
                existing.incremental_capital_employed = round(inc_cap, 2)
                existing.incremental_ebit = round(inc_ebit, 2)
                existing.incremental_revenue = round(inc_rev, 2)
                existing.incremental_roce_pct = inc_roce
                existing.reinvestment_rate = reinvest_rate

        db.commit()
        logger.info(f"Computed {len(results)} incremental reinvestment periods for company {company_id}.")
        return results
