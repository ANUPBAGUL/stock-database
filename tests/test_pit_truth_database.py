"""
Comprehensive Automated Verification Suite for the 6-Layer 200-IQ Multibagger Database.

Tests:
1. Announcement Scoring & Dual-Track Half-Life Decay Engine
2. PriceAdjuster Split/Bonus Compounding & Volume Inversion
3. Reinvestment Engine (Incremental Capital, Incremental EBIT, Incremental ROCE Trajectories)
4. DecisionSnapshotEngine (Immutable T0 Snapshots, SHA-256 Dataset Hashes)
5. Rich OutcomeLabeler (Milestone prices/days, path volatility, daily trajectories)
6. 8-Stage Company Lifecycle Classifier (Early, Scaling, Operating Leverage, Mature, Declining)
7. Multi-Factor Failed Multibagger & False-Positive Diagnostic Engine
8. Quarterly Point-in-Time State Builder (Q-12, Q-8, Q-4, Q-2 Historical Trajectories)
9. Raw Source Evidence Audit Link & Hash Lookup
10. DataRelevanceDaemon (Information Absorption State Machine)
11. Institutional Risk Engine 5-Gate Compliance
"""

import os
import sys
import math
import unittest
from datetime import date, datetime, timedelta

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.db.base import SessionLocal, Base, engine
from src.db.models import (
    Company, Sector, DailyPriceRaw, CorporateAction, BitemporalFinancial,
    CorporateAnnouncement, BoardMeetingAnnouncement, DecisionSnapshot, ForwardOutcome,
    ReinvestmentMetric, CompanyLifecycleHistory, MultibaggerFailureDiagnostic, RawSourceEvidence,
    QuarterlyPITState
)
from src.analytics.announcement_decay_engine import AnnouncementDecayEngine
from src.analytics.price_adjuster import PriceAdjuster
from src.analytics.feature_engine import FeatureEngine
from src.analytics.reinvestment_calculator import ReinvestmentCalculator
from src.analytics.snapshot_engine import DecisionSnapshotEngine
from src.analytics.outcome_labeler import OutcomeLabeler
from src.analytics.lifecycle_classifier import LifecycleClassifier
from src.analytics.failure_analyzer import FailureAnalyzer
from src.analytics.quarterly_pit_builder import QuarterlyPITBuilder
from src.analytics.data_relevance_daemon import DataRelevanceDaemon
from src.portfolio.risk_engine import InstitutionalRiskEngine


class TestPITTruthDatabase(unittest.TestCase):

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    # ──────────────────────────────────────────────────────────────
    # 1. Announcement Scoring & Half-Life Decay Tests
    # ──────────────────────────────────────────────────────────────

    def test_announcement_materiality_scoring(self):
        """Test regex value extraction, materiality multiplier, and track classification."""
        headline = "Company awarded ₹850 Cr 5-Year Defense Contract by Ministry of Defense"
        summary = "Execution timeline 24 months. Major expansion."
        
        raw_score, val_cr, track = AnnouncementDecayEngine.score_announcement(
            event_type="ORDER_WIN",
            headline=headline,
            summary=summary,
            ttm_revenue_cr=1000.0,
            price_jump_pct=3.0,
            volume_spike_ratio=2.5
        )

        self.assertEqual(val_cr, 850.0)
        self.assertEqual(track, "STRUCTURAL")
        self.assertGreater(raw_score, 80.0)

    def test_announcement_half_life_decay(self):
        """Verify mathematical decay for tactical (48h) and structural (90d) tracks."""
        now = datetime.now()
        pub_time = now - timedelta(hours=48)
        
        decayed_score, status = AnnouncementDecayEngine.calculate_decayed_score(
            raw_score=80.0,
            track_type="TACTICAL",
            publication_time=pub_time,
            current_time=now
        )
        self.assertAlmostEqual(decayed_score, 40.0, places=0)
        self.assertEqual(status, "DECAYING")

        pub_time_old = now - timedelta(days=8)
        decayed_old, status_old = AnnouncementDecayEngine.calculate_decayed_score(
            raw_score=80.0,
            track_type="TACTICAL",
            publication_time=pub_time_old,
            current_time=now
        )
        self.assertLess(decayed_old, 10.0)
        self.assertEqual(status_old, "ABSORBED_INTO_PRICE")

    # ──────────────────────────────────────────────────────────────
    # 2. Corporate Action Split Adjustment & Volume Scaling Tests
    # ──────────────────────────────────────────────────────────────

    def test_price_adjuster_split_and_volume(self):
        """Verify 1:5 stock split divides pre-split price by 5 and multiplies volume by 5."""
        test_comp_id = "comp_test_split_xyz"
        comp = self.db.query(Company).filter_by(company_id=test_comp_id).first()
        if not comp:
            comp = Company(
                company_id=test_comp_id,
                isin="INETEST0101",
                nse_symbol="TESTSPLIT",
                company_name="Test Split Ltd",
                status="ACTIVE"
            )
            self.db.add(comp)
            self.db.commit()

        d1 = date(2026, 1, 10)
        d2 = date(2026, 1, 20)
        ex_dt = date(2026, 1, 15)

        self.db.query(DailyPriceRaw).filter_by(company_id=test_comp_id).delete()
        self.db.query(CorporateAction).filter_by(company_id=test_comp_id).delete()

        p1 = DailyPriceRaw(
            company_id=test_comp_id,
            trading_date=d1,
            open_price=1000.0, high_price=1050.0, low_price=980.0, close_price=1000.0, volume=10000
        )
        p2 = DailyPriceRaw(
            company_id=test_comp_id,
            trading_date=d2,
            open_price=200.0, high_price=210.0, low_price=195.0, close_price=205.0, volume=50000
        )
        action = CorporateAction(
            company_id=test_comp_id,
            ex_date=ex_dt,
            action_type="SPLIT",
            price_factor=0.20, share_factor=5.0, cum_factor=0.20
        )
        self.db.add_all([p1, p2, action])
        self.db.commit()

        adj_prices = PriceAdjuster.get_adjusted_prices(self.db, test_comp_id, d1, d2)
        self.assertEqual(len(adj_prices), 2)
        self.assertEqual(adj_prices[0]["adj_close"], 200.0)
        self.assertEqual(adj_prices[0]["volume"], 50000)
        self.assertEqual(adj_prices[1]["adj_close"], 205.0)

    # ──────────────────────────────────────────────────────────────
    # 3. Reinvestment Engine: Incremental ROCE Trajectory Tests
    # ──────────────────────────────────────────────────────────────

    def test_reinvestment_calculator_incremental_roce(self):
        """Verify incremental ROCE = Delta EBIT / Delta Capital Employed."""
        test_comp_id = "comp_test_reinvest_abc"
        comp = self.db.query(Company).filter_by(company_id=test_comp_id).first()
        if not comp:
            comp = Company(
                company_id=test_comp_id,
                isin="INETESTREINV1",
                nse_symbol="TESTREINV",
                company_name="Test Reinvestment Ltd",
                status="ACTIVE"
            )
            self.db.add(comp)
            self.db.commit()

        self.db.query(BitemporalFinancial).filter_by(company_id=test_comp_id).delete()
        self.db.query(ReinvestmentMetric).filter_by(company_id=test_comp_id).delete()

        # Year 1 (2024): CE = 1000 Cr, EBIT = 200 Cr
        f1 = BitemporalFinancial(
            company_id=test_comp_id,
            period_type="ANNUAL",
            period_end_date=date(2024, 3, 31),
            publication_date=datetime(2024, 5, 15, 18, 0),
            source="TEST_PIT",
            revenue=2000.0, ebit=200.0, total_assets=1500.0, current_liabilities=500.0,
            operating_cash_flow=220.0, capex=100.0
        )
        # Year 2 (2025): CE = 1200 Cr (+200 Cr), EBIT = 280 Cr (+80 Cr) -> Inc ROCE = 40.0%
        f2 = BitemporalFinancial(
            company_id=test_comp_id,
            period_type="ANNUAL",
            period_end_date=date(2025, 3, 31),
            publication_date=datetime(2025, 5, 15, 18, 0),
            source="TEST_PIT",
            revenue=2600.0, ebit=280.0, total_assets=1800.0, current_liabilities=600.0,
            operating_cash_flow=310.0, capex=150.0
        )
        self.db.add_all([f1, f2])
        self.db.commit()

        results = ReinvestmentCalculator.calculate_incremental_roce_trajectory(self.db, test_comp_id)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["incremental_capital_employed"], 200.0)
        self.assertEqual(results[0]["incremental_ebit"], 80.0)
        self.assertEqual(results[0]["incremental_roce_pct"], 40.0)

    # ──────────────────────────────────────────────────────────────
    # 4. Rich Decision Snapshots & Milestone Outcome Labeler Tests
    # ──────────────────────────────────────────────────────────────

    def test_decision_snapshot_and_rich_outcome_labeler(self):
        """Verify immutable T0 snapshot, milestone tracking (days_to_2x), and path payload."""
        test_comp_id = "comp_test_snapshot_xyz"
        comp = self.db.query(Company).filter_by(company_id=test_comp_id).first()
        if not comp:
            comp = Company(
                company_id=test_comp_id,
                isin="INETESTSNAP01",
                nse_symbol="TESTSNAP",
                company_name="Test Snapshot Ltd",
                status="ACTIVE"
            )
            self.db.add(comp)
            self.db.commit()

        self.db.query(ForwardOutcome).filter_by(company_id=test_comp_id).delete()
        self.db.query(DecisionSnapshot).filter_by(company_id=test_comp_id).delete()
        self.db.query(DailyPriceRaw).filter_by(company_id=test_comp_id).delete()

        t0 = datetime(2024, 1, 1, 15, 30)
        features = {"roce_pct": 32.5, "pe_ratio": 24.0, "revenue_yoy_growth_pct": 45.0}

        snapshot = DecisionSnapshotEngine.record_decision_snapshot(
            db=self.db,
            company_id=test_comp_id,
            t0_timestamp=t0,
            feature_vector=features,
            m6_score=88.5,
            verdict="CONVICTION_BUY",
            horizon_ratings={"longterm": 88, "swing": 75},
            why_buy_reasons=["Expanding ROCE", "Capacity addition"],
            why_not_buy_reasons=["Valuation re-rating"],
            invalidation_thresholds={"roce_floor": 15.0}
        )

        self.assertIsNotNone(snapshot.snapshot_id)
        self.assertIsNotNone(snapshot.dataset_hash)

        # Prices: ₹100 -> ₹95 (drawdown -5%) -> ₹220 (day 1, 2x hit) -> ₹350 (day 2)
        p0 = DailyPriceRaw(company_id=test_comp_id, trading_date=date(2024, 1, 1), open_price=100.0, high_price=102.0, low_price=98.0, close_price=100.0, volume=1000)
        p1 = DailyPriceRaw(company_id=test_comp_id, trading_date=date(2024, 1, 2), open_price=95.0, high_price=98.0, low_price=94.0, close_price=95.0, volume=1200)
        p2 = DailyPriceRaw(company_id=test_comp_id, trading_date=date(2024, 6, 1), open_price=220.0, high_price=225.0, low_price=215.0, close_price=220.0, volume=2000)
        p3 = DailyPriceRaw(company_id=test_comp_id, trading_date=date(2025, 1, 1), open_price=350.0, high_price=360.0, low_price=340.0, close_price=350.0, volume=3000)
        self.db.add_all([p0, p1, p2, p3])
        self.db.commit()

        outcome = OutcomeLabeler.evaluate_snapshot_outcome(
            db=self.db,
            snapshot=snapshot,
            as_of_date=date(2025, 1, 2),
            market_cap_at_t0=1200.0
        )

        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.is_multibagger_2x, True)
        self.assertEqual(outcome.days_to_2x, 2)
        self.assertEqual(outcome.price_at_2x, 220.0)
        self.assertEqual(outcome.max_drawdown_before_2x, -5.0)
        self.assertEqual(outcome.max_forward_return_pct, 250.0)
        self.assertIn("trajectory", outcome.daily_path_payload)

    # ──────────────────────────────────────────────────────────────
    # 5. 8-Stage Company Lifecycle Classifier Tests
    # ──────────────────────────────────────────────────────────────

    def test_company_lifecycle_classification(self):
        """Verify deterministic 8-stage lifecycle classification."""
        res_op_lev = LifecycleClassifier.classify_company_stage(
            market_cap_cr=5000.0,
            revenue_cr=1200.0,
            revenue_growth_yoy_pct=25.0,
            ebitda_growth_yoy_pct=38.0,
            pat_growth_yoy_pct=45.0,
            roce_pct=26.0,
            roce_delta_bps=300.0,
            institutional_stake_pct=18.0
        )
        self.assertEqual(res_op_lev["stage"], "4_OPERATING_LEVERAGE")
        self.assertEqual(res_op_lev["stage_numeric_order"], 4)

        res_early = LifecycleClassifier.classify_company_stage(
            market_cap_cr=800.0,
            revenue_cr=150.0,
            revenue_growth_yoy_pct=15.0,
            ebitda_growth_yoy_pct=15.0,
            pat_growth_yoy_pct=15.0,
            roce_pct=16.0,
            roce_delta_bps=0.0,
            institutional_stake_pct=2.0
        )
        self.assertEqual(res_early["stage"], "1_EARLY_SMALL")

    # ──────────────────────────────────────────────────────────────
    # 6. Multi-Factor Failure Diagnostic Engine Tests
    # ──────────────────────────────────────────────────────────────

    def test_failure_analyzer_multi_factor(self):
        """Verify multi-factor compound failure classification and quantitative evidence payloads."""
        test_comp_id = "comp_test_fail_xyz"
        comp = self.db.query(Company).filter_by(company_id=test_comp_id).first()
        if not comp:
            comp = Company(
                company_id=test_comp_id,
                isin="INETESTFAIL01",
                nse_symbol="TESTFAIL",
                company_name="Test Failure Ltd",
                status="ACTIVE"
            )
            self.db.add(comp)
            self.db.commit()

        self.db.query(MultibaggerFailureDiagnostic).filter_by(company_id=test_comp_id).delete()
        self.db.query(ForwardOutcome).filter_by(company_id=test_comp_id).delete()
        self.db.query(DecisionSnapshot).filter_by(company_id=test_comp_id).delete()
        self.db.query(BitemporalFinancial).filter_by(company_id=test_comp_id).delete()

        # High-conviction snapshot at T0
        snapshot = DecisionSnapshot(
            company_id=test_comp_id,
            decision_timestamp=datetime(2024, 1, 1, 15, 30),
            feature_set_version="v2.4.0",
            model_version="M6_FROZEN_EXP004",
            dataset_hash="test_fail_hash",
            raw_features_payload={"roce_pct": 30.0, "revenue_yoy_growth_pct": 35.0},
            m6_score=85.0,
            verdict="CONVICTION_BUY"
        )
        outcome = ForwardOutcome(
            snapshot=snapshot,
            company_id=test_comp_id,
            t0_date=date(2024, 1, 1),
            t0_price=100.0,
            max_drawdown_pct=-55.0,
            is_failure=True
        )
        # Fundamental report post T0 showing ROCE deterioration + Debt explosion (Total Debt = 600 Cr on 200 Cr NW -> D/E = 3.0x)
        f_post = BitemporalFinancial(
            company_id=test_comp_id,
            period_type="ANNUAL",
            period_end_date=date(2025, 3, 31),
            publication_date=datetime(2025, 5, 15, 18, 0),
            source="TEST",
            ebit=80.0, total_assets=1200.0, current_liabilities=200.0,
            total_debt=600.0, net_worth=200.0
        )
        self.db.add_all([snapshot, outcome, f_post])
        self.db.commit()

        diag = FailureAnalyzer.diagnose_snapshot_failure(
            db=self.db,
            snapshot=snapshot,
            outcome=outcome,
            as_of_date=date(2025, 5, 20)
        )

        self.assertIsNotNone(diag)
        self.assertEqual(diag.primary_failure_reason, "ROCE_DETERIORATION")
        self.assertIn("DEBT_EXPLOSION", diag.secondary_failure_reasons["reasons"])
        self.assertGreaterEqual(len(diag.failure_evidence["evidence"]), 2)
        self.assertEqual(diag.failure_confidence, 0.92)

    # ──────────────────────────────────────────────────────────────
    # 7. Quarterly Point-in-Time State Builder Tests
    # ──────────────────────────────────────────────────────────────

    def test_quarterly_pit_state_builder(self):
        """Verify building quarterly consolidated PIT states and tracking multi-quarter trajectories."""
        test_comp_id = "comp_test_qpit_xyz"
        comp = self.db.query(Company).filter_by(company_id=test_comp_id).first()
        if not comp:
            comp = Company(
                company_id=test_comp_id,
                isin="INETESTQPIT01",
                nse_symbol="TESTQPIT",
                company_name="Test Quarterly PIT Ltd",
                status="ACTIVE"
            )
            self.db.add(comp)
            self.db.commit()

        self.db.query(QuarterlyPITState).filter_by(company_id=test_comp_id).delete()
        self.db.query(BitemporalFinancial).filter_by(company_id=test_comp_id).delete()
        self.db.query(DailyPriceRaw).filter_by(company_id=test_comp_id).delete()

        # Ingest 2 Quarters: Q1 (June 2024) and Q2 (Sept 2024)
        q1 = BitemporalFinancial(
            company_id=test_comp_id,
            period_type="QUARTERLY",
            period_end_date=date(2024, 6, 30),
            publication_date=datetime(2024, 8, 14, 18, 0),
            source="TEST",
            revenue=300.0, ebitda=60.0, ebit=50.0, pat=35.0,
            total_assets=800.0, current_liabilities=200.0, net_worth=500.0, shares_outstanding=10.0
        )
        q2 = BitemporalFinancial(
            company_id=test_comp_id,
            period_type="QUARTERLY",
            period_end_date=date(2024, 9, 30),
            publication_date=datetime(2024, 11, 14, 18, 0),
            source="TEST",
            revenue=380.0, ebitda=85.0, ebit=75.0, pat=55.0,
            total_assets=950.0, current_liabilities=220.0, net_worth=550.0, shares_outstanding=10.0
        )
        p0 = DailyPriceRaw(company_id=test_comp_id, trading_date=date(2024, 8, 14), open_price=100.0, high_price=105.0, low_price=98.0, close_price=100.0, volume=1000)
        p1 = DailyPriceRaw(company_id=test_comp_id, trading_date=date(2024, 11, 14), open_price=150.0, high_price=155.0, low_price=145.0, close_price=150.0, volume=1500)
        p_future = DailyPriceRaw(company_id=test_comp_id, trading_date=date(2025, 5, 1), open_price=250.0, high_price=260.0, low_price=240.0, close_price=250.0, volume=2000)
        self.db.add_all([q1, q2, p0, p1, p_future])
        self.db.commit()

        q_states = QuarterlyPITBuilder.build_quarterly_states_for_company(self.db, test_comp_id)
        self.assertEqual(len(q_states), 2)
        
        # Verify Q1 state (base 100 -> 250 is 2.5x => is_multibagger_2x = True)
        state_q1 = next(s for s in q_states if s.quarter_end_date == date(2024, 6, 30))
        self.assertEqual(state_q1.market_cap_cr, 1000.0)
        self.assertEqual(state_q1.is_multibagger_2x, True)
        
        # Verify Q2 state (base 150 -> 250 is +66.67% max run)
        state_q2 = next(s for s in q_states if s.quarter_end_date == date(2024, 9, 30))
        self.assertEqual(state_q2.market_cap_cr, 1500.0) # 150 price * 10 shares
        self.assertEqual(state_q2.roce_pct, round((75.0 / (950.0 - 220.0)) * 100.0, 2))
        self.assertEqual(state_q2.fwd_max_run_pct, 66.67)

    # ──────────────────────────────────────────────────────────────
    # 8. Raw Source Evidence Auditability Tests
    # ──────────────────────────────────────────────────────────────

    def test_raw_source_evidence_audit_link(self):
        """Verify raw source evidence record creation and document hash index lookup."""
        test_comp_id = "comp_test_evidence_xyz"
        comp = self.db.query(Company).filter_by(company_id=test_comp_id).first()
        if not comp:
            comp = Company(
                company_id=test_comp_id,
                isin="INETESTEVID01",
                nse_symbol="TESTEVID",
                company_name="Test Evidence Ltd",
                status="ACTIVE"
            )
            self.db.add(comp)
            self.db.commit()

        doc_hash = "a3f5b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7"
        evidence = RawSourceEvidence(
            entity_table="bitemporal_financials",
            entity_id="fin_rec_123",
            company_id=test_comp_id,
            source_type="NSE_XBRL_FILING",
            source_url="https://www.nseindia.com/corporates/xbrl/fin_123.xml",
            document_hash=doc_hash,
            document_date=date(2026, 6, 30),
            publication_timestamp=datetime(2026, 8, 14, 18, 30),
            parser_version="v2.1.0",
            extracted_fields_payload={"revenue": 1450.5, "ebit": 285.0, "pat": 195.2}
        )
        self.db.add(evidence)
        self.db.commit()

        retrieved = self.db.query(RawSourceEvidence).filter_by(document_hash=doc_hash).first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.entity_table, "bitemporal_financials")
        self.assertEqual(retrieved.extracted_fields_payload["revenue"], 1450.5)

    # ──────────────────────────────────────────────────────────────
    # 9. Data Relevance Daemon: Information Absorption State Tests
    # ──────────────────────────────────────────────────────────────

    def test_relevance_daemon_absorption(self):
        """Verify structural announcement transitions to ABSORBED_INTO_FINANCIALS once quarterly filings exist."""
        test_comp_id = "comp_test_absorb_xyz"
        comp = self.db.query(Company).filter_by(company_id=test_comp_id).first()
        if not comp:
            comp = Company(
                company_id=test_comp_id,
                isin="INETESTABS01",
                nse_symbol="TESTABS",
                company_name="Test Absorption Ltd",
                status="ACTIVE"
            )
            self.db.add(comp)
            self.db.commit()

        self.db.query(CorporateAnnouncement).filter_by(company_id=test_comp_id).delete()
        self.db.query(BitemporalFinancial).filter_by(company_id=test_comp_id).delete()

        now = datetime.now()
        ann = CorporateAnnouncement(
            company_id=test_comp_id,
            symbol="TESTABS",
            publication_timestamp=now - timedelta(days=25),
            event_type="CAPEX",
            track_type="STRUCTURAL",
            headline="New ₹500 Cr Plant Commissioned",
            raw_materiality_score=90.0,
            decayed_score=90.0,
            status="NEW_ACTIVE"
        )
        f1 = BitemporalFinancial(
            company_id=test_comp_id,
            period_type="QUARTERLY",
            period_end_date=(now - timedelta(days=20)).date(),
            publication_date=now - timedelta(days=15),
            source="TEST",
            revenue=500.0, ebit=80.0
        )
        f2 = BitemporalFinancial(
            company_id=test_comp_id,
            period_type="QUARTERLY",
            period_end_date=(now - timedelta(days=10)).date(),
            publication_date=now - timedelta(days=5),
            source="TEST",
            revenue=620.0, ebit=110.0
        )
        self.db.add_all([ann, f1, f2])
        self.db.commit()

        summary = DataRelevanceDaemon.execute_maintenance_cycle(self.db)
        self.assertGreaterEqual(summary["structural_absorbed_into_financials"], 1)

        self.db.refresh(ann)
        self.assertEqual(ann.status, "ABSORBED_INTO_FINANCIALS")

    # ──────────────────────────────────────────────────────────────
    # 10. Institutional Risk Engine Tests
    # ──────────────────────────────────────────────────────────────

    def test_risk_engine_compliance(self):
        """Verify 5% NAV single stock cap and 5% 20D ADV liquidity limits."""
        res = InstitutionalRiskEngine.audit_trade_compliance(
            portfolio_nav_inr=10_000_000.0,
            proposed_investment_inr=1_000_000.0,
            symbol="TCS",
            sector="Technology",
            current_price=4000.0,
            daily_turnover_inr=50_000_000.0,
            existing_stock_holding_inr=0.0
        )

        self.assertEqual(res["compliance_status"], "APPROVED_WITH_CAPACITY_REDUCTION")
        self.assertAlmostEqual(res["approved_investment_inr"], 500_000.0, delta=4000.0)


if __name__ == "__main__":
    unittest.main()
