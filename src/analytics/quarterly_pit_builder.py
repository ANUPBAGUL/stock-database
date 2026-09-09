"""
Quarterly Point-in-Time State Builder.

Reconstructs the complete consolidated observation state of any company at every historical
quarterly reporting boundary (publication_timestamp) with zero lookahead bias.

Integrates:
- Fundamental accounting primitives (TTM Revenue, EBITDA, Margins, ROCE, ROIC, Reinvestment Rate)
- Ownership trajectories (Promoter, Pledge, Institutional QoQ)
- Active Decayed Catalysts
- 8-Stage Lifecycle Stage
- Model M6 Score & Rank
- Forward Trajectory (Q+1 to Q+12 Returns, Drawdown, 2x/5x/10x Labels)
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

from src.db.models import (
    QuarterlyPITState, BitemporalFinancial, DailyPriceRaw, CorporateAction,
    ShareholdingHistory, CorporateAnnouncement, ReinvestmentMetric, Company
)
from src.analytics.price_adjuster import PriceAdjuster
from src.analytics.lifecycle_classifier import LifecycleClassifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QuarterlyPITBuilder:
    """
    Builds and persists consolidated quarterly point-in-time state observations.
    """

    @classmethod
    def build_quarterly_states_for_company(
        cls,
        db: Session,
        company_id: str
    ) -> List[QuarterlyPITState]:
        """
        Processes all historical quarterly filings for a company and generates
        point-in-time consolidated quarterly state observations.
        """
        filings = db.query(BitemporalFinancial).filter(
            BitemporalFinancial.company_id == company_id,
            BitemporalFinancial.period_type == "QUARTERLY"
        ).order_by(BitemporalFinancial.period_end_date.asc()).all()

        if not filings:
            return []

        # Also fetch all annual audited filings (which contain audited Balance Sheets and Cash Flows)
        annual_filings = db.query(BitemporalFinancial).filter(
            BitemporalFinancial.company_id == company_id,
            BitemporalFinancial.period_type == "ANNUAL"
        ).order_by(BitemporalFinancial.period_end_date.asc()).all()

        # Deduplicate to latest publication per quarter_end_date
        deduped = {}
        for f in filings:
            deduped[f.period_end_date] = f

        sorted_quarters = sorted(deduped.keys())
        created_states = []

        for i, q_date in enumerate(sorted_quarters):
            curr_f = deduped[q_date]
            pub_ts = curr_f.publication_date

            # 1. Fetch T0 Price and Market Cap
            price_rec = db.query(DailyPriceRaw).filter(
                DailyPriceRaw.company_id == company_id,
                DailyPriceRaw.trading_date <= pub_ts.date()
            ).order_by(DailyPriceRaw.trading_date.desc()).first()

            t0_price = price_rec.close_price if price_rec else None
            shares = curr_f.shares_outstanding

            # If shares missing on quarterly filing, resolve from annual filings or equity capital / face value
            if not shares or shares <= 0:
                for af in reversed(annual_filings):
                    if af.publication_date <= pub_ts and af.period_end_date <= q_date:
                        if af.shares_outstanding and af.shares_outstanding > 0:
                            shares = af.shares_outstanding
                            break
                        elif getattr(af, "equity_share_capital", None):
                            comp = db.query(Company).filter_by(company_id=company_id).first()
                            fv = getattr(comp, "face_value", 10.0) or 10.0
                            shares = (af.equity_share_capital * 10_000_000.0) / fv if fv > 0 else None
                            break

            if (not shares or shares <= 0) and getattr(curr_f, "equity_share_capital", None):
                comp = db.query(Company).filter_by(company_id=company_id).first()
                fv = getattr(comp, "face_value", 10.0) or 10.0
                shares = (curr_f.equity_share_capital * 10_000_000.0) / fv if fv > 0 else None

            if t0_price and shares and shares > 0:
                mcap = round((t0_price * shares) / 10_000_000.0, 2) if shares > 100_000 else round(t0_price * shares, 2)
            else:
                mcap = None

            # 2. Compute TTM and YoY Growth across available chronological quarters
            q_slice = [deduped[q] for q in sorted_quarters[max(0, i - 3): i + 1]]
            valid_revs = [q.revenue for q in q_slice if q.revenue is not None]
            valid_ebits = [q.ebit for q in q_slice if q.ebit is not None]
            valid_ebitdas = [q.ebitda for q in q_slice if q.ebitda is not None]
            valid_pats = [q.pat for q in q_slice if q.pat is not None]

            ttm_rev = (sum(valid_revs) * (4.0 / len(valid_revs))) if valid_revs else None
            ttm_ebit = (sum(valid_ebits) * (4.0 / len(valid_ebits))) if valid_ebits else None
            ttm_ebitda = (sum(valid_ebitdas) * (4.0 / len(valid_ebitdas))) if valid_ebitdas else None
            ttm_pat = (sum(valid_pats) * (4.0 / len(valid_pats))) if valid_pats else None

            rev_growth_yoy = None
            pat_growth_yoy = None
            ebitda_growth_yoy = None

            # Calendar-aware YoY matching (matching target year - 1 and quarter month)
            target_yr = q_date.year - 1
            target_m = q_date.month
            target_q = (target_m - 1) // 3

            prev_4q = None
            # Pass 1: exact month in prior year
            for past_q in reversed(sorted_quarters[:i]):
                if past_q.year == target_yr and past_q.month == target_m:
                    prev_4q = deduped.get(past_q)
                    break
            # Pass 2: same calendar quarter in prior year
            if prev_4q is None:
                for past_q in reversed(sorted_quarters[:i]):
                    if past_q.year == target_yr and ((past_q.month - 1) // 3) == target_q:
                        prev_4q = deduped.get(past_q)
                        break

            if prev_4q:
                if prev_4q.revenue and prev_4q.revenue > 0 and curr_f.revenue:
                    rev_growth_yoy = round(((curr_f.revenue - prev_4q.revenue) / abs(prev_4q.revenue)) * 100.0, 2)
                if prev_4q.pat and prev_4q.pat != 0 and curr_f.pat:
                    pat_growth_yoy = round(((curr_f.pat - prev_4q.pat) / abs(prev_4q.pat)) * 100.0, 2)
                if prev_4q.ebitda and prev_4q.ebitda != 0 and curr_f.ebitda:
                    ebitda_growth_yoy = round(((curr_f.ebitda - prev_4q.ebitda) / abs(prev_4q.ebitda)) * 100.0, 2)

            # 3. Margins & Capital Efficiency
            ebitda_margin = round((ttm_ebitda / ttm_rev) * 100.0, 2) if (ttm_ebitda and ttm_rev and ttm_rev > 0) else None
            pat_margin = round((ttm_pat / ttm_rev) * 100.0, 2) if (ttm_pat and ttm_rev and ttm_rev > 0) else None

            # Capital Employed (IND-AS Standard: Assets - CL, or NW + Debt)
            total_assets = curr_f.total_assets
            cl = getattr(curr_f, "current_liabilities", None)
            nw = curr_f.net_worth
            debt = curr_f.total_debt or 0.0

            ce = None
            if total_assets and cl and (total_assets - cl) > 0:
                ce = total_assets - cl
            elif nw and (nw + debt) > 0:
                ce = nw + debt

            # If interim quarter without balance sheet, look back to latest annual or prior balance sheet
            if ce is None:
                for af in reversed(annual_filings):
                    if af.publication_date <= pub_ts and af.period_end_date <= q_date:
                        af_ta = af.total_assets
                        af_cl = getattr(af, "current_liabilities", None)
                        af_nw = af.net_worth
                        af_debt = af.total_debt or 0.0
                        if af_ta and af_cl and (af_ta - af_cl) > 0:
                            ce = af_ta - af_cl
                            if not nw: nw = af_nw
                            if not debt: debt = af_debt
                            break
                        elif af_nw and (af_nw + af_debt) > 0:
                            ce = af_nw + af_debt
                            if not nw: nw = af_nw
                            if not debt: debt = af_debt
                            break

                if ce is None:
                    for past_q in reversed(sorted_quarters[:i]):
                        past_f = deduped[past_q]
                        p_ta = past_f.total_assets
                        p_cl = getattr(past_f, "current_liabilities", None)
                        p_nw = past_f.net_worth
                        p_debt = past_f.total_debt or 0.0
                        if p_ta and p_cl and (p_ta - p_cl) > 0:
                            ce = p_ta - p_cl
                            if not nw: nw = p_nw
                            if not debt: debt = p_debt
                            break
                        elif p_nw and (p_nw + p_debt) > 0:
                            ce = p_nw + p_debt
                            if not nw: nw = p_nw
                            if not debt: debt = p_debt
                            break

            roce = round((ttm_ebit / ce) * 100.0, 2) if (ttm_ebit and ce and ce > 0) else None
            nopat = ttm_ebit * 0.7483 if ttm_ebit is not None else None
            roic = round((nopat / ce) * 100.0, 2) if (nopat is not None and ce and ce > 0) else None
            pe = round(mcap / ttm_pat, 2) if (mcap and ttm_pat and ttm_pat > 0) else None

            # Shareholding pattern lookup as of publication timestamp
            sh = db.query(ShareholdingHistory).filter(
                ShareholdingHistory.company_id == company_id,
                ShareholdingHistory.period_end_date <= q_date,
                ShareholdingHistory.publication_timestamp <= pub_ts
            ).order_by(ShareholdingHistory.period_end_date.desc()).first()

            promoter_h = sh.promoter_holding_pct if sh else None
            promoter_p = sh.promoter_pledge_pct if sh else None
            inst_h = None
            if sh:
                inst_sum = (sh.fii_holding_pct or 0.0) + (sh.dii_holding_pct or 0.0)
                if sh.fii_holding_pct is not None or sh.dii_holding_pct is not None:
                    inst_h = round(inst_sum, 2)

            # Cash flow and reinvestment metrics
            ocf_val = curr_f.operating_cash_flow
            capex_val = curr_f.capex
            if ocf_val is None or capex_val is None:
                for af in reversed(annual_filings):
                    if af.publication_date <= pub_ts and af.period_end_date <= q_date:
                        if af.operating_cash_flow is not None and af.capex is not None:
                            ocf_val = af.operating_cash_flow
                            capex_val = af.capex
                            break

                if ocf_val is None or capex_val is None:
                    for past_q in reversed(sorted_quarters[:i]):
                        past_f = deduped[past_q]
                        if past_f.operating_cash_flow is not None and past_f.capex is not None:
                            ocf_val = past_f.operating_cash_flow
                            capex_val = past_f.capex
                            break

            fcf_conversion = None
            reinvestment_rate = None
            if ocf_val is not None and capex_val is not None:
                fcf_calc = ocf_val - capex_val
                if ttm_pat and ttm_pat > 0:
                    fcf_conversion = round((fcf_calc / ttm_pat) * 100.0, 2)
                if nopat and nopat > 0:
                    reinvestment_rate = round(min(150.0, max(0.0, (capex_val / nopat) * 100.0)), 2)

            dte = round(debt / nw, 2) if (nw and nw > 0) else None

            # 4. Lifecycle Classification
            lifecycle = LifecycleClassifier.classify_company_stage(
                market_cap_cr=mcap or 500.0,
                revenue_cr=ttm_rev or 100.0,
                revenue_growth_yoy_pct=rev_growth_yoy if rev_growth_yoy is not None else 15.0,
                ebitda_growth_yoy_pct=ebitda_growth_yoy if ebitda_growth_yoy is not None else 15.0,
                pat_growth_yoy_pct=pat_growth_yoy if pat_growth_yoy is not None else 15.0,
                roce_pct=roce if roce is not None else 15.0,
                roce_delta_bps=50.0,
                institutional_stake_pct=inst_h if inst_h is not None else 10.0
            )

            # Model M6 Conviction scoring
            m6_score = None
            m6_verdict = None
            try:
                from src.ai.m6_frozen import M6FrozenResearchModel
                fin_feat = {
                    "ttm_revenue": ttm_rev,
                    "revenue_yoy_growth_pct": rev_growth_yoy,
                    "pat_yoy_growth_pct": pat_growth_yoy,
                    "ebitda_margin": ebitda_margin,
                    "pat_margin": pat_margin,
                    "roce_pct": roce,
                    "debt_to_equity": dte,
                }
                pr_feat = {"pe_ratio": pe}
                gov_feat = {
                    "promoter_holding_pct": promoter_h if promoter_h is not None else 50.0,
                    "pledge_pct": promoter_p if promoter_p is not None else 0.0,
                }
                m6_eval = M6FrozenResearchModel.score_company(
                    company_id=company_id,
                    symbol="",
                    as_of_date=pub_ts.date(),
                    financial_features=fin_feat,
                    price_features=pr_feat,
                    governance_features=gov_feat,
                    macro_regime="EXPANSION"
                )
                m6_score = m6_eval.get("m6_conviction_score")
                if m6_score is not None:
                    m6_verdict = "HIGH_CONVICTION" if m6_score >= 70 else ("NEUTRAL" if m6_score >= 50 else "UNDERPERFORM")
            except Exception:
                pass

            # 5. Forward Price Realization post publication (Split-adjusted continuous prices)
            future_prices = PriceAdjuster.get_adjusted_prices(
                db=db,
                company_id=company_id,
                start_date=pub_ts.date(),
                end_date=date.today()
            )

            fwd_1q, fwd_2q, fwd_4q, fwd_8q, fwd_12q = None, None, None, None, None
            max_run, max_dd = 0.0, 0.0
            is_2x, is_5x, is_10x = False, False, False

            if future_prices and len(future_prices) > 1:
                base_p = future_prices[0]["adj_close"]
                if base_p > 0:
                    def _get_return_by_calendar_days(cal_days: int) -> Optional[float]:
                        target_dt = pub_ts.date() + timedelta(days=cal_days)
                        for p_item in future_prices:
                            if p_item["trading_date"] >= target_dt:
                                return round(((p_item["adj_close"] - base_p) / base_p) * 100.0, 2)
                        return None

                    fwd_1q = _get_return_by_calendar_days(90)
                    fwd_2q = _get_return_by_calendar_days(180)
                    fwd_4q = _get_return_by_calendar_days(365)
                    fwd_8q = _get_return_by_calendar_days(730)
                    fwd_12q = _get_return_by_calendar_days(1095)

                    # True Peak-to-Trough Maximum Drawdown & Maximum Upside Run
                    running_peak = base_p
                    peak_drawdown = 0.0
                    peak_run = 0.0

                    for p_item in future_prices:
                        ap = p_item["adj_close"]
                        if ap > running_peak:
                            running_peak = ap
                        dd = ((ap - running_peak) / running_peak) * 100.0
                        if dd < peak_drawdown:
                            peak_drawdown = dd
                        gain = ((ap - base_p) / base_p) * 100.0
                        if gain > peak_run:
                            peak_run = gain

                    max_run = round(peak_run, 2)
                    max_dd = round(peak_drawdown, 2)
                    is_2x = (max_run >= 100.0)
                    is_5x = (max_run >= 400.0)
                    is_10x = (max_run >= 900.0)

            # 6. Persist or Update QuarterlyPITState
            existing = db.query(QuarterlyPITState).filter_by(
                company_id=company_id,
                quarter_end_date=q_date
            ).first()

            if not existing:
                q_state = QuarterlyPITState(
                    company_id=company_id,
                    quarter_end_date=q_date,
                    publication_timestamp=pub_ts,
                    financial_id=curr_f.financial_id,
                    market_cap_cr=round(mcap, 2) if mcap else None,
                    revenue_ttm_cr=round(ttm_rev, 2) if ttm_rev else None,
                    revenue_growth_yoy_pct=rev_growth_yoy,
                    ebitda_growth_yoy_pct=ebitda_growth_yoy,
                    pat_growth_yoy_pct=pat_growth_yoy,
                    ebitda_margin_pct=ebitda_margin,
                    pat_margin_pct=pat_margin,
                    roce_pct=roce,
                    roic_pct=roic,
                    reinvestment_rate_pct=reinvestment_rate,
                    fcf_to_pat_conversion_pct=fcf_conversion,
                    debt_to_equity=dte,
                    pe_ratio=pe,
                    promoter_holding_pct=promoter_h,
                    promoter_pledge_pct=promoter_p,
                    institutional_holding_pct=inst_h,
                    lifecycle_stage=lifecycle["stage"],
                    m6_score=m6_score,
                    m6_verdict=m6_verdict,
                    raw_feature_vector_payload={"roce": roce, "rev_growth": rev_growth_yoy, "mcap": mcap, "pe": pe, "roic": roic},
                    fwd_return_1q_pct=fwd_1q,
                    fwd_return_2q_pct=fwd_2q,
                    fwd_return_4q_pct=fwd_4q,
                    fwd_return_8q_pct=fwd_8q,
                    fwd_return_12q_pct=fwd_12q,
                    fwd_max_run_pct=max_run,
                    fwd_max_drawdown_pct=max_dd,
                    is_multibagger_2x=is_2x,
                    is_multibagger_5x=is_5x,
                    is_multibagger_10x=is_10x,
                    is_failure=(max_dd <= -50.0 and not is_2x)
                )
                db.add(q_state)
                created_states.append(q_state)
            else:
                existing.financial_id = curr_f.financial_id
                existing.market_cap_cr = round(mcap, 2) if mcap else existing.market_cap_cr
                existing.revenue_ttm_cr = round(ttm_rev, 2) if ttm_rev else existing.revenue_ttm_cr
                existing.revenue_growth_yoy_pct = rev_growth_yoy
                existing.ebitda_growth_yoy_pct = ebitda_growth_yoy
                existing.pat_growth_yoy_pct = pat_growth_yoy
                existing.ebitda_margin_pct = ebitda_margin
                existing.pat_margin_pct = pat_margin
                existing.roce_pct = roce
                existing.roic_pct = roic
                existing.reinvestment_rate_pct = reinvestment_rate
                existing.fcf_to_pat_conversion_pct = fcf_conversion
                existing.debt_to_equity = dte
                existing.pe_ratio = pe
                existing.promoter_holding_pct = promoter_h
                existing.promoter_pledge_pct = promoter_p
                existing.institutional_holding_pct = inst_h
                existing.lifecycle_stage = lifecycle["stage"]
                existing.m6_score = m6_score
                existing.m6_verdict = m6_verdict
                existing.raw_feature_vector_payload = {"roce": roce, "rev_growth": rev_growth_yoy, "mcap": mcap, "pe": pe, "roic": roic}
                existing.fwd_return_1q_pct = fwd_1q
                existing.fwd_return_2q_pct = fwd_2q
                existing.fwd_return_4q_pct = fwd_4q
                existing.fwd_return_8q_pct = fwd_8q
                existing.fwd_return_12q_pct = fwd_12q
                existing.is_multibagger_2x = is_2x
                existing.is_multibagger_5x = is_5x
                existing.is_multibagger_10x = is_10x
                existing.fwd_max_run_pct = max_run
                existing.fwd_max_drawdown_pct = max_dd
                existing.is_failure = (max_dd <= -50.0 and not is_2x)
                created_states.append(existing)

        db.commit()
        logger.info(f"[Quarterly PIT Builder] Generated {len(created_states)} quarterly PIT states for company {company_id}.")
        return created_states
