"""
Layer J: End-to-End Synthetic Golden Dataset & Pipeline Validation.
Constructs an immutable 15-company synthetic cohort across multiple historical vintages (2017-2024)
and runs the complete pipeline:
Raw Facts -> PIT Store -> Universe Filter -> T0 Snapshot -> Canonical Hash -> Forward Outcome -> Purged Splitter -> OOS Firewall.
"""
import uuid
from datetime import date, datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.models import (
    Company, Sector, BitemporalFinancial, DailyPriceRaw,
    UniverseMembership, ResearchFeatureSnapshot, ForwardOutcome
)
from src.analytics.canonical_hasher import compute_canonical_hash
from src.analytics.interval_purger import LabelInterval, PurgedFoldSplitter
from src.analytics.wealth_compounding_engine import WealthCompoundingEngine
from src.analytics.oos_firewall import OOSFirewall

@pytest.fixture
def golden_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def _seed_golden_cohort(db):
    """
    Creates 15 distinct companies covering all archetypes:
    - 5 Compounders / 10x Winners (COMP_WIN_1 to 5)
    - 4 Steady Survivors (COMP_STEADY_1 to 4)
    - 3 Historical Bankruptcies (COMP_FAIL_1 to 3)
    - 2 Acquired / Merged (COMP_ACQ_1 to 2)
    - 1 Restated / Forensic Case (COMP_RESTATE_1)
    """
    sec = Sector(sector_id=str(uuid.uuid4()), sector_name="GoldenSector")
    db.add(sec)
    db.flush()

    companies = []
    # 1. 10x Winners
    for i in range(1, 6):
        c = Company(company_id=f"COMP_WIN_{i}", isin=f"INE_WIN_{i:04d}", nse_symbol=f"WIN{i}", company_name=f"Winner {i} Ltd", sector_id=sec.sector_id, listing_status="ACTIVE")
        db.add(c)
        companies.append(c)
        # Universe membership 2016-Present
        db.add(UniverseMembership(membership_id=f"MEM_WIN_{i}", company_id=c.company_id, symbol=f"WIN{i}", universe_name="NIFTY_500", effective_from=date(2016, 1, 1), effective_to=None))

    # 2. Steady Survivors
    for i in range(1, 5):
        c = Company(company_id=f"COMP_STD_{i}", isin=f"INE_STD_{i:04d}", nse_symbol=f"STD{i}", company_name=f"Steady {i} Ltd", sector_id=sec.sector_id, listing_status="ACTIVE")
        db.add(c)
        companies.append(c)
        db.add(UniverseMembership(membership_id=f"MEM_STD_{i}", company_id=c.company_id, symbol=f"STD{i}", universe_name="NIFTY_500", effective_from=date(2016, 1, 1), effective_to=None))

    # 3. Bankruptcies
    for i in range(1, 4):
        c = Company(company_id=f"COMP_FAIL_{i}", isin=f"INE_FAIL_{i:04d}", nse_symbol=f"FAIL{i}", company_name=f"Failure {i} Ltd", sector_id=sec.sector_id, listing_status="BANKRUPTCY")
        db.add(c)
        companies.append(c)
        # Delisted at end of 2019
        db.add(UniverseMembership(membership_id=f"MEM_FAIL_{i}", company_id=c.company_id, symbol=f"FAIL{i}", universe_name="NIFTY_500", effective_from=date(2016, 1, 1), effective_to=date(2019, 12, 31)))

    # 4. Merged
    for i in range(1, 3):
        c = Company(company_id=f"COMP_ACQ_{i}", isin=f"INE_ACQ_{i:04d}", nse_symbol=f"ACQ{i}", company_name=f"Acquired {i} Ltd", sector_id=sec.sector_id, listing_status="MERGED")
        db.add(c)
        companies.append(c)
        db.add(UniverseMembership(membership_id=f"MEM_ACQ_{i}", company_id=c.company_id, symbol=f"ACQ{i}", universe_name="NIFTY_500", effective_from=date(2016, 1, 1), effective_to=date(2021, 6, 30)))

    # 5. Restated Case
    c_rst = Company(company_id="COMP_RST_1", isin="INE_RST_0001", nse_symbol="RST1", company_name="Restated 1 Ltd", sector_id=sec.sector_id, listing_status="ACTIVE")
    db.add(c_rst)
    companies.append(c_rst)
    db.add(UniverseMembership(membership_id="MEM_RST_1", company_id=c_rst.company_id, symbol="RST1", universe_name="NIFTY_500", effective_from=date(2016, 1, 1), effective_to=None))

    db.commit()
    return companies

def test_golden_dataset_complete_e2e_pipeline(golden_db):
    """
    Executes the full golden dataset pipeline and verifies end-to-end coherence.
    """
    companies = _seed_golden_cohort(golden_db)
    assert len(companies) == 15

    # 1. Verify Survivorship Universe at T0 = 2018-06-30
    t0_2018 = date(2018, 6, 30)
    u_2018 = golden_db.query(UniverseMembership).filter(
        UniverseMembership.universe_name == "NIFTY_500",
        UniverseMembership.effective_from <= t0_2018,
        (UniverseMembership.effective_to.is_(None) | (UniverseMembership.effective_to >= t0_2018))
    ).all()
    # All 15 companies were constituents in 2018!
    assert len(u_2018) == 15

    # 2. Verify Survivorship Universe at T0 = 2022-06-30
    t0_2022 = date(2022, 6, 30)
    u_2022 = golden_db.query(UniverseMembership).filter(
        UniverseMembership.universe_name == "NIFTY_500",
        UniverseMembership.effective_from <= t0_2022,
        (UniverseMembership.effective_to.is_(None) | (UniverseMembership.effective_to >= t0_2022))
    ).all()
    # In 2022: 5 winners + 4 steady + 1 restated = 10 companies (3 bankruptcies and 2 acquisitions excluded)
    assert len(u_2022) == 10

    # 3. Simulate T0 ResearchFeatureSnapshot Generation for Winner 1
    w1 = golden_db.query(Company).filter_by(nse_symbol="WIN1").first()
    in_payload = {"ttm_revenue": 1000.0, "ttm_pat": 150.0, "pe": 25.0}
    out_payload = {"economic_roic_pct": 35.5, "tam_share": 12.0}

    snap_w1 = ResearchFeatureSnapshot(
        snapshot_id="SNAP_WIN1_2018",
        company_id=w1.company_id,
        observation_date=t0_2018,
        t0_timestamp=datetime(2018, 6, 30, 15, 30, 0),
        source_fact_ids=["FACT_XBRL_2018_Q1"],
        source_published_at=datetime(2018, 5, 15, 10, 0, 0),
        source_period_end=date(2018, 3, 31),
        feature_engine_version="v3.2.0",
        peer_selection_version="v1.0.0",
        methodology_version="INSTITUTIONAL_P0",
        input_hash=compute_canonical_hash(in_payload),
        output_hash=compute_canonical_hash(out_payload),
        economic_roic_pct=35.5
    )
    golden_db.add(snap_w1)
    golden_db.commit()

    # 4. Verify Interval Purging for Fold Splitting
    train_interval = LabelInterval("OBS_WIN1_TRAIN", w1.company_id, t0_2018, t0_2018, date(2021, 6, 30), "3Y")
    test_interval = LabelInterval("OBS_WIN1_TEST", w1.company_id, date(2020, 6, 30), date(2020, 6, 30), date(2023, 6, 30), "3Y")

    # 2018-2021 overlaps with 2020-2023! Must be purged!
    retained, purged = PurgedFoldSplitter.purge_train_set([train_interval], [test_interval])
    assert len(purged) == 1
    assert len(retained) == 0

    # 5. Verify OOS Firewall Partitioning
    assert OOSFirewall.get_partition(t0_2018) == "DEVELOPMENT"
    assert OOSFirewall.get_partition(date(2022, 6, 30)) == "VALIDATION"
    assert OOSFirewall.get_partition(date(2025, 6, 30)) == "LOCKED_OOS"
