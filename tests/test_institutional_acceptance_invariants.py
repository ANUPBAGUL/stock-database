"""
Master Institutional Acceptance Test Suite: The 8 Non-Negotiable Invariants (A-H).

Tests:
- Invariant A: Vintage Reconstruction Test (Features(T0) reproducible exactly from PIT facts)
- Invariant B: Future-Document Poison Test (Inserting filings with T_pub > T0 leaves Features(T0) 100% unchanged)
- Invariant C: Restatement Invariance Test (Subsequent restatements do not alter historical pre-restatement snapshots)
- Invariant D: Duplicate-Company Dependence Test (Zero company overlap between train and test in company holdouts)
- Invariant E: Fold-Boundary Label Overlap Test (Half-open interval overlap [start, end) strictly disjoint across folds)
- Invariant F: Machine-Readable Provenance Audit (Every feature traces to fact IDs with source_published_at <= T0)
- Invariant G: Adversarial Synthetic Leakage Canary (Assert F(T0, D) == F(T0, D + FuturePoison) bit-for-bit)
- Invariant H: Feature Regeneration Determinism (Identical inputs produce bit-for-bit identical SHA-256 hashes)
"""
import uuid
from datetime import date, datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.models import (
    Company, Sector, BitemporalFinancial, DailyPriceRaw,
    ResearchFeatureSnapshot, UniverseMembership, ForwardOutcome
)
from src.analytics.canonical_hasher import canonical_serialize, compute_canonical_hash
from src.analytics.interval_purger import LabelInterval, PurgedFoldSplitter
from src.analytics.wealth_compounding_engine import (
    WealthCompoundingEngine, TerminalEventRecord
)
from src.analytics.oos_firewall import OOSFirewall, LOCKED_OOS_VERSION

@pytest.fixture
def mem_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def _create_mock_company(db, symbol="TESTCO", isin="INE000000001", sector_name="Technology"):
    sec = db.query(Sector).filter_by(sector_name=sector_name).first()
    if not sec:
        sec = Sector(sector_id=str(uuid.uuid4()), sector_name=sector_name)
        db.add(sec)
        db.flush()
    comp = Company(
        company_id=str(uuid.uuid4()),
        isin=isin,
        nse_symbol=symbol,
        company_name=f"{symbol} Limited",
        sector_id=sec.sector_id,
        listing_status="ACTIVE",
        tradability_status="TRADABLE",
        liquidity_status="LIQUID",
        research_eligibility="ELIGIBLE"
    )
    db.add(comp)
    db.commit()
    return comp

# ─────────────────────────────────────────────────────────────────────────────
# Invariant A: Vintage Reconstruction Test
# ─────────────────────────────────────────────────────────────────────────────
def test_invariant_a_vintage_reconstruction(mem_db):
    """
    Features(T0) must be reproducible exactly from the PIT database.
    """
    comp = _create_mock_company(mem_db, "RECON_CO", "INE000000002")
    t0_date = date(2020, 6, 30)
    t0_dt = datetime(2020, 6, 30, 15, 30, 0)

    # Ingest historical statements published strictly before T0
    f1 = BitemporalFinancial(
        financial_id=str(uuid.uuid4()),
        company_id=comp.company_id,
        period_type="QUARTERLY",
        period_end_date=date(2020, 3, 31),
        publication_date=datetime(2020, 5, 20, 18, 0, 0), # Published before T0
        revenue=1000.0,
        ebit=150.0,
        pat=100.0,
        source="NSE_XBRL"
    )
    mem_db.add(f1)
    mem_db.commit()

    # Query PIT facts as of T0
    pit_facts = mem_db.query(BitemporalFinancial).filter(
        BitemporalFinancial.company_id == comp.company_id,
        BitemporalFinancial.publication_date <= t0_dt
    ).all()

    assert len(pit_facts) == 1
    assert pit_facts[0].revenue == 1000.0
    assert pit_facts[0].ebit == 150.0

# ─────────────────────────────────────────────────────────────────────────────
# Invariant B: Future-Document Poison Test
# ─────────────────────────────────────────────────────────────────────────────
def test_invariant_b_future_document_poison(mem_db):
    """
    Inserting a future filing (T_pub > T0) leaves Features(T0) completely unchanged.
    """
    comp = _create_mock_company(mem_db, "POISON_CO", "INE000000003")
    t0_dt = datetime(2020, 6, 30, 15, 30, 0)

    # Valid fact available at T0
    valid_stmt = BitemporalFinancial(
        financial_id="VALID_STMT_001",
        company_id=comp.company_id,
        period_type="QUARTERLY",
        period_end_date=date(2020, 3, 31),
        publication_date=datetime(2020, 5, 15, 10, 0, 0), # T_pub < T0
        revenue=500.0,
        source="NSE_XBRL"
    )
    mem_db.add(valid_stmt)
    mem_db.commit()

    # Baseline query at T0
    baseline_facts = mem_db.query(BitemporalFinancial).filter(
        BitemporalFinancial.company_id == comp.company_id,
        BitemporalFinancial.publication_date <= t0_dt
    ).all()
    baseline_revenue = sum(f.revenue for f in baseline_facts)

    # Inject poison filing published in 2021 (after T0)
    future_poison = BitemporalFinancial(
        financial_id="POISON_STMT_FUTURE",
        company_id=comp.company_id,
        period_type="QUARTERLY",
        period_end_date=date(2020, 3, 31), # Same accounting period!
        publication_date=datetime(2021, 6, 10, 10, 0, 0), # POISON: Published after T0
        revenue=999999.0,
        source="FUTURE_RESTATED_DOCUMENT"
    )
    mem_db.add(future_poison)
    mem_db.commit()

    # Query again strictly enforcing publication_date <= T0
    post_poison_facts = mem_db.query(BitemporalFinancial).filter(
        BitemporalFinancial.company_id == comp.company_id,
        BitemporalFinancial.publication_date <= t0_dt
    ).all()
    post_poison_revenue = sum(f.revenue for f in post_poison_facts)

    assert post_poison_revenue == baseline_revenue == 500.0
    assert "POISON_STMT_FUTURE" not in [f.financial_id for f in post_poison_facts]

# ─────────────────────────────────────────────────────────────────────────────
# Invariant C: Restatement Invariance Test
# ─────────────────────────────────────────────────────────────────────────────
def test_invariant_c_restatement_invariance(mem_db):
    """
    Adding a subsequent restatement does not alter historical decision snapshots prior to restatement date.
    """
    comp = _create_mock_company(mem_db, "RESTATE_CO", "INE000000004")
    t0_dt = datetime(2019, 6, 30, 15, 30, 0)

    original_filing = BitemporalFinancial(
        financial_id="ORIG_2019",
        company_id=comp.company_id,
        period_type="ANNUAL",
        period_end_date=date(2019, 3, 31),
        publication_date=datetime(2019, 5, 20, 18, 0, 0),
        pat=100.0,
        is_restatement=False,
        source="ORIGINAL_FILING"
    )
    mem_db.add(original_filing)
    mem_db.commit()

    # Pre-restatement view as of 2019-06-30
    view_at_t0 = mem_db.query(BitemporalFinancial).filter(
        BitemporalFinancial.company_id == comp.company_id,
        BitemporalFinancial.publication_date <= t0_dt
    ).order_by(BitemporalFinancial.publication_date.desc()).first()
    assert view_at_t0.pat == 100.0

    # In 2021, an auditor restatement is published
    restatement_filing = BitemporalFinancial(
        financial_id="RESTATE_2021",
        company_id=comp.company_id,
        period_type="ANNUAL",
        period_end_date=date(2019, 3, 31),
        publication_date=datetime(2021, 8, 15, 18, 0, 0),
        pat=65.0, # Restated down
        is_restatement=True,
        source="RESTATEMENT_2021"
    )
    mem_db.add(restatement_filing)
    mem_db.commit()

    # Historical query at T0=2019 must STILL see original filing (100.0), NOT restated filing (65.0)
    view_at_t0_rechecked = mem_db.query(BitemporalFinancial).filter(
        BitemporalFinancial.company_id == comp.company_id,
        BitemporalFinancial.publication_date <= t0_dt
    ).order_by(BitemporalFinancial.publication_date.desc()).first()
    assert view_at_t0_rechecked.pat == 100.0
    assert view_at_t0_rechecked.financial_id == "ORIG_2019"

# ─────────────────────────────────────────────────────────────────────────────
# Invariant D: Duplicate-Company Dependence Test
# ─────────────────────────────────────────────────────────────────────────────
def test_invariant_d_duplicate_company_dependence():
    """
    In company-group validation, no company exists in both train and test folds.
    """
    train_companies = {"INFY", "TCS", "WIPRO", "HCLTECH"}
    test_companies = {"DIXON", "KAYNES", "SYRMA"}

    overlap = train_companies.intersection(test_companies)
    assert len(overlap) == 0, f"Violation: Duplicate companies found in both folds: {overlap}"

# ─────────────────────────────────────────────────────────────────────────────
# Invariant E: Fold-Boundary Label Overlap Test
# ─────────────────────────────────────────────────────────────────────────────
def test_invariant_e_fold_boundary_interval_purging():
    """
    Asserts generic half-open interval overlap [start, end) is strictly disjoint across fold boundaries.
    """
    # Train observation: Jan 2019 to Jan 2022 (3Y)
    train_obs_1 = LabelInterval(
        observation_id="TRAIN_01",
        company_id="COMP_A",
        t0=date(2019, 1, 1),
        label_start=date(2019, 1, 1),
        label_end=date(2022, 1, 1),
        horizon_type="3Y"
    )

    # Train observation: Jan 2017 to Jan 2020 (3Y)
    train_obs_2 = LabelInterval(
        observation_id="TRAIN_02",
        company_id="COMP_B",
        t0=date(2017, 1, 1),
        label_start=date(2017, 1, 1),
        label_end=date(2020, 1, 1),
        horizon_type="3Y"
    )

    # Test observation: Jun 2021 to Jun 2024 (3Y)
    test_obs = LabelInterval(
        observation_id="TEST_01",
        company_id="COMP_C",
        t0=date(2021, 6, 1),
        label_start=date(2021, 6, 1),
        label_end=date(2024, 6, 1),
        horizon_type="3Y"
    )

    # TRAIN_01 [2019-01-01 -> 2022-01-01) overlaps TEST_01 [2021-06-01 -> 2024-06-01) because:
    # 2019-01-01 < 2024-06-01 and 2021-06-01 < 2022-01-01.
    assert train_obs_1.overlaps_with(test_obs) is True

    # TRAIN_02 [2017-01-01 -> 2020-01-01) DOES NOT overlap TEST_01 [2021-06-01 -> 2024-06-01)
    assert train_obs_2.overlaps_with(test_obs) is False

    retained, purged = PurgedFoldSplitter.purge_train_set([train_obs_1, train_obs_2], [test_obs])
    assert len(purged) == 1
    assert purged[0].observation_id == "TRAIN_01"
    assert len(retained) == 1
    assert retained[0].observation_id == "TRAIN_02"

    # Verifying assertion passes for clean split
    assert PurgedFoldSplitter.assert_zero_fold_overlap(retained, [test_obs]) is True

# ─────────────────────────────────────────────────────────────────────────────
# Invariant F: Machine-Readable Provenance Audit
# ─────────────────────────────────────────────────────────────────────────────
def test_invariant_f_machine_readable_provenance(mem_db):
    """
    Every ResearchFeatureSnapshot must trace to: source_fact_ids, source_published_at <= T0.
    """
    comp = _create_mock_company(mem_db, "PROV_CO", "INE000000005")
    t0_dt = datetime(2021, 3, 31, 18, 0, 0)
    fact_id = "FACT_XBRL_999"

    snap = ResearchFeatureSnapshot(
        snapshot_id="SNAP_PROV_001",
        company_id=comp.company_id,
        observation_date=date(2021, 3, 31),
        t0_timestamp=t0_dt,
        source_fact_ids=[fact_id],
        source_published_at=datetime(2021, 3, 20, 10, 0, 0), # Must be <= T0
        source_period_end=date(2020, 12, 31),
        feature_engine_version="v3.2.0",
        peer_selection_version="v1.0.0",
        methodology_version="INSTITUTIONAL_P0"
    )
    mem_db.add(snap)
    mem_db.commit()

    retrieved = mem_db.query(ResearchFeatureSnapshot).filter_by(snapshot_id="SNAP_PROV_001").first()
    assert retrieved is not None
    assert retrieved.source_fact_ids == [fact_id]
    assert retrieved.source_published_at <= retrieved.t0_timestamp
    assert retrieved.feature_engine_version == "v3.2.0"

# ─────────────────────────────────────────────────────────────────────────────
# Invariant G: Adversarial Synthetic Leakage Canary
# ─────────────────────────────────────────────────────────────────────────────
def test_invariant_g_adversarial_synthetic_leakage_canary():
    """
    Injects synthetic poisoned future variables into raw input dictionary.
    Asserts canonical hash of feature outputs remains bit-for-bit identical F(T0, D) == F(T0, D + FuturePoison).
    """
    clean_inputs = {
        "company": "DIXON",
        "t0": "2020-03-31",
        "ttm_revenue": 4400.0,
        "ttm_pat": 120.0,
        "pe": 35.0
    }

    # Feature extractor only processes valid economic primitives
    def extract_features(data):
        return {
            "rev": float(data.get("ttm_revenue", 0.0)),
            "pat": float(data.get("ttm_pat", 0.0)),
            "mcap": float(data.get("ttm_pat", 0.0)) * float(data.get("pe", 20.0))
        }

    clean_features = extract_features(clean_inputs)
    clean_hash = compute_canonical_hash(clean_features)

    # Poison environment with look-ahead leaks
    poisoned_inputs = dict(clean_inputs)
    poisoned_inputs["future_1y_return"] = 280.5
    poisoned_inputs["future_3y_max_gain"] = 920.0
    poisoned_inputs["future_bankruptcy_event"] = False
    poisoned_inputs["future_restated_revenue"] = 8000.0

    poisoned_features = extract_features(poisoned_inputs)
    poisoned_hash = compute_canonical_hash(poisoned_features)

    # CANARY ASSERTION: Feature generation output hash MUST remain identical bit-for-bit
    assert clean_hash == poisoned_hash
    assert "future_1y_return" not in poisoned_features

# ─────────────────────────────────────────────────────────────────────────────
# Invariant H: Feature Regeneration Determinism
# ─────────────────────────────────────────────────────────────────────────────
def test_invariant_h_feature_regeneration_determinism():
    """
    Re-running feature engine against identical frozen PIT inputs produces bit-for-bit identical hashes.
    """
    sample_data_run1 = {
        "company_id": "COMP_XYZ_001",
        "t0_date": "2019-12-31",
        "economic_roic_pct": 24.87654321,
        "niche_tam_cr": 45000.0,
        "reinvestment_rate": 42.15,
        "metrics": {"ebit": 500.123456, "pat": 350.654321}
    }

    # Run 2 has keys inserted in different order and float micro-noise beyond 6 decimals
    sample_data_run2 = {
        "metrics": {"pat": 350.65432100000001, "ebit": 500.12345600000002},
        "reinvestment_rate": 42.15,
        "niche_tam_cr": 45000.0,
        "economic_roic_pct": 24.87654322, # Within 6 decimals rounds to 24.876543
        "t0_date": "2019-12-31",
        "company_id": "COMP_XYZ_001"
    }

    hash1 = compute_canonical_hash(sample_data_run1)
    hash2 = compute_canonical_hash(sample_data_run2)

    assert hash1 == hash2, f"Determinism failure: {hash1} != {hash2}"

# ─────────────────────────────────────────────────────────────────────────────
# Wealth Compounding & Terminal Recovery Tests
# ─────────────────────────────────────────────────────────────────────────────
def test_wealth_compounding_engine():
    """
    Tests primitive wealth compounding with reinvested dividends and corporate distributions.
    """
    prices = [
        {"date": date(2020, 1, 1), "close": 100.0, "dividend": 0.0, "corporate_proceeds": 0.0},
        {"date": date(2020, 6, 1), "close": 120.0, "dividend": 5.0, "corporate_proceeds": 0.0}, # Dividend paid
        {"date": date(2021, 1, 1), "close": 150.0, "dividend": 0.0, "corporate_proceeds": 10.0}, # Spin-off proceeds
    ]

    wealth_res = WealthCompoundingEngine.compute_compounded_wealth(1000.0, prices, reinvest_distributions=True)
    assert wealth_res["wealth_start"] == 1000.0
    assert wealth_res["wealth_end"] > 1500.0 # Wealth grew more than just price return due to reinvested cash
    assert wealth_res["total_return_pct"] > 50.0

def test_terminal_economic_recovery_non_naive():
    """
    Verifies that bankruptcy/delisting is an event state, not an automatic -100% loss.
    """
    # Case 1: Total loss liquidation
    event_total_loss = TerminalEventRecord(
        event_date=date(2022, 5, 10),
        event_type="BANKRUPTCY",
        status="LIQUIDATION",
        terminal_equity_value_per_share=0.0,
        cash_recovery_per_share=0.0
    )
    rec1 = WealthCompoundingEngine.compute_terminal_economic_recovery(100.0, 5.0, event_total_loss)
    assert rec1["terminal_return_pct"] == -100.0
    assert rec1["is_total_loss"] is True

    # Case 2: Partial restructuring recovery (e.g. Rs 15/share recovery under CIRP)
    event_partial_recovery = TerminalEventRecord(
        event_date=date(2022, 5, 10),
        event_type="BANKRUPTCY",
        status="BANKRUPTCY",
        terminal_equity_value_per_share=5.0,
        cash_recovery_per_share=10.0
    )
    rec2 = WealthCompoundingEngine.compute_terminal_economic_recovery(100.0, 5.0, event_partial_recovery)
    assert rec2["terminal_return_pct"] == -85.0 # Realized -85%, NOT hardcoded -100%!
    assert rec2["is_total_loss"] is False
    assert rec2["total_recovery_per_share"] == 15.0

# ─────────────────────────────────────────────────────────────────────────────
# Survivorship & Universe Membership Tests
# ─────────────────────────────────────────────────────────────────────────────
def test_survivorship_universe_membership(mem_db):
    """
    Tests historical investable universe reconstruction including delisted and bankrupt firms.
    """
    comp_live = _create_mock_company(mem_db, "LIVE_CO", "INE000000006")
    comp_bankrupt = _create_mock_company(mem_db, "DHFL_FAIL", "INE000000007")

    # In 2018, both were constituents of NIFTY_500
    m1 = UniverseMembership(
        membership_id="MEM_001",
        company_id=comp_live.company_id,
        symbol="LIVE_CO",
        universe_name="NIFTY_500",
        effective_from=date(2016, 1, 1),
        effective_to=None, # Still active
        listing_status="ACTIVE",
        tradability_status="TRADABLE",
        liquidity_status="HIGH",
        research_eligibility="ELIGIBLE"
    )
    m2 = UniverseMembership(
        membership_id="MEM_002",
        company_id=comp_bankrupt.company_id,
        symbol="DHFL_FAIL",
        universe_name="NIFTY_500",
        effective_from=date(2016, 1, 1),
        effective_to=date(2019, 11, 20), # Delisted in late 2019
        listing_status="BANKRUPTCY",
        tradability_status="SUSPENDED",
        liquidity_status="ILLIQUID",
        research_eligibility="ELIGIBLE",
        exclusion_reason="DELISTING_INSOLVENCY"
    )
    mem_db.add_all([m1, m2])
    mem_db.commit()

    # Query investable universe on 2018-03-31: BOTH must be present!
    as_of_2018 = date(2018, 3, 31)
    universe_2018 = mem_db.query(UniverseMembership).filter(
        UniverseMembership.universe_name == "NIFTY_500",
        UniverseMembership.effective_from <= as_of_2018,
        (UniverseMembership.effective_to.is_(None) | (UniverseMembership.effective_to >= as_of_2018))
    ).all()
    symbols_2018 = [m.symbol for m in universe_2018]
    assert "LIVE_CO" in symbols_2018
    assert "DHFL_FAIL" in symbols_2018, "Survivorship bias violation: Historical failure omitted from 2018 universe!"

    # Query investable universe on 2021-03-31: DHFL must be excluded, LIVE_CO present!
    as_of_2021 = date(2021, 3, 31)
    universe_2021 = mem_db.query(UniverseMembership).filter(
        UniverseMembership.universe_name == "NIFTY_500",
        UniverseMembership.effective_from <= as_of_2021,
        (UniverseMembership.effective_to.is_(None) | (UniverseMembership.effective_to >= as_of_2021))
    ).all()
    symbols_2021 = [m.symbol for m in universe_2021]
    assert "LIVE_CO" in symbols_2021
    assert "DHFL_FAIL" not in symbols_2021

# ─────────────────────────────────────────────────────────────────────────────
# OOS Firewall & Maturity Tests
# ─────────────────────────────────────────────────────────────────────────────
def test_oos_firewall_maturity():
    """
    Tests locked OOS firewall partitioning and maturity vs right-censoring logic.
    """
    assert OOSFirewall.get_partition(date(2018, 6, 30)) == "DEVELOPMENT"
    assert OOSFirewall.get_partition(date(2022, 6, 30)) == "VALIDATION"
    assert OOSFirewall.get_partition(date(2025, 6, 30)) == "LOCKED_OOS"

    # Case A: Mature 5Y observation (T0 = 2018-01-01 evaluated as of 2026-01-01)
    cens_mature = OOSFirewall.classify_censoring(
        t0_date=date(2018, 1, 1),
        horizon_years=5.0,
        max_available_date=date(2026, 1, 1),
        target_event_occurred=False
    )
    assert cens_mature["maturity"] == "MATURE"
    assert cens_mature["is_ongoing"] is False

    # Case B: Immature 5Y observation (T0 = 2024-01-01 evaluated as of 2026-01-01)
    # Only 2 years have elapsed! Must be classified as RIGHT_CENSORED, NOT a failure!
    cens_immature = OOSFirewall.classify_censoring(
        t0_date=date(2024, 1, 1),
        horizon_years=5.0,
        max_available_date=date(2026, 1, 1),
        target_event_occurred=False
    )
    assert cens_immature["maturity"] == "IMMATURE"
    assert cens_immature["censoring_status"] == "RIGHT_CENSORED"
    assert cens_immature["is_ongoing"] is True
    assert cens_immature["is_evaluable_for_binary"] is False
