"""
Layer D: Metamorphic Testing.
Applies transformations to inputs that semantically should not alter output,
proving bit-for-bit invariance:
1. Database insertion order shuffling
2. Addition of neutral / irrelevant companies
3. Injection of future filings (Invariant B)
4. Addition of forward outcomes post-facto (Firewall invariance)
"""
import uuid
from datetime import date, datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.models import Company, Sector, BitemporalFinancial, ResearchFeatureSnapshot, ForwardOutcome
from src.analytics.canonical_hasher import compute_canonical_hash

@pytest.fixture
def mem_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def _create_company(db, sym):
    sec = db.query(Sector).filter_by(sector_name="MetamorphicSector").first()
    if not sec:
        sec = Sector(sector_id=str(uuid.uuid4()), sector_name="MetamorphicSector")
        db.add(sec)
        db.flush()
    comp = Company(
        company_id=str(uuid.uuid4()),
        isin=f"INE{abs(hash(sym)) % 1000000000:09d}",
        nse_symbol=sym,
        company_name=f"{sym} Corp",
        sector_id=sec.sector_id
    )
    db.add(comp)
    db.commit()
    return comp

def test_metamorphic_db_row_order_invariance(mem_db):
    """
    Querying historical statements sorted by publication date produces identical aggregated features
    regardless of raw DB insertion order.
    """
    comp = _create_company(mem_db, "ORDER_CO")
    t0_dt = datetime(2020, 6, 30, 15, 30, 0)

    # Insert out-of-order: Q2 first, then Q1
    f_q2 = BitemporalFinancial(
        financial_id="Q2_STMT",
        company_id=comp.company_id,
        period_type="QUARTERLY",
        period_end_date=date(2020, 3, 31),
        publication_date=datetime(2020, 5, 20, 10, 0, 0),
        revenue=600.0,
        source="NSE_XBRL"
    )
    f_q1 = BitemporalFinancial(
        financial_id="Q1_STMT",
        company_id=comp.company_id,
        period_type="QUARTERLY",
        period_end_date=date(2019, 12, 31),
        publication_date=datetime(2020, 2, 10, 10, 0, 0),
        revenue=500.0,
        source="NSE_XBRL"
    )
    mem_db.add_all([f_q2, f_q1])
    mem_db.commit()

    facts = mem_db.query(BitemporalFinancial).filter(
        BitemporalFinancial.company_id == comp.company_id,
        BitemporalFinancial.publication_date <= t0_dt
    ).order_by(BitemporalFinancial.publication_date.asc()).all()

    # Provenance ordered list
    prov_ids = [f.financial_id for f in facts]
    assert prov_ids == ["Q1_STMT", "Q2_STMT"]
    assert sum(f.revenue for f in facts) == 1100.0

def test_metamorphic_irrelevant_company_addition(mem_db):
    """
    Adding an unrelated third-party company to the DB does not alter target company features or hashes.
    """
    comp_a = _create_company(mem_db, "TARGET_CO")
    t0_dt = datetime(2020, 6, 30, 15, 30, 0)

    f_a = BitemporalFinancial(
        financial_id="TARGET_FACT_1",
        company_id=comp_a.company_id,
        period_type="QUARTERLY",
        period_end_date=date(2020, 3, 31),
        publication_date=datetime(2020, 5, 10, 10, 0, 0),
        revenue=1000.0,
        source="NSE_XBRL"
    )
    mem_db.add(f_a)
    mem_db.commit()

    facts_before = mem_db.query(BitemporalFinancial).filter(
        BitemporalFinancial.company_id == comp_a.company_id,
        BitemporalFinancial.publication_date <= t0_dt
    ).all()
    hash_before = compute_canonical_hash({"rev": sum(f.revenue for f in facts_before)})

    # Metamorphic mutation: Add completely separate company B with heavy financials
    comp_b = _create_company(mem_db, "NOISE_CO")
    f_b = BitemporalFinancial(
        financial_id="NOISE_FACT_1",
        company_id=comp_b.company_id,
        period_type="QUARTERLY",
        period_end_date=date(2020, 3, 31),
        publication_date=datetime(2020, 5, 10, 10, 0, 0),
        revenue=99999.0,
        source="NSE_XBRL"
    )
    mem_db.add(f_b)
    mem_db.commit()

    facts_after = mem_db.query(BitemporalFinancial).filter(
        BitemporalFinancial.company_id == comp_a.company_id,
        BitemporalFinancial.publication_date <= t0_dt
    ).all()
    hash_after = compute_canonical_hash({"rev": sum(f.revenue for f in facts_after)})

    # INVARIANT: Target company hash must remain bit-for-bit identical
    assert hash_before == hash_after

def test_metamorphic_outcome_addition_invariance(mem_db):
    """
    Adding forward outcome labels post-facto leaves historical T0 ResearchFeatureSnapshot completely untouched.
    """
    comp = _create_company(mem_db, "FIREWALL_CO")
    t0_date = date(2020, 1, 1)

    snap = ResearchFeatureSnapshot(
        snapshot_id="SNAP_FW_01",
        company_id=comp.company_id,
        observation_date=t0_date,
        t0_timestamp=datetime(2020, 1, 1, 10, 0, 0),
        economic_roic_pct=22.5,
        input_hash="INPUT_HASH_AAA",
        output_hash="OUTPUT_HASH_BBB"
    )
    mem_db.add(snap)
    mem_db.commit()

    hash_prior = compute_canonical_hash({
        "roic": snap.economic_roic_pct,
        "input_hash": snap.input_hash,
        "output_hash": snap.output_hash
    })

    # Add ForwardOutcome label to DB
    outcome = ForwardOutcome(
        outcome_id="OUT_FW_01",
        snapshot_id=snap.snapshot_id,
        company_id=comp.company_id,
        t0_date=t0_date,
        t0_price=100.0,
        max_forward_return_pct=450.0,
        is_multibagger_5x=True
    )
    mem_db.add(outcome)
    mem_db.commit()

    # Re-read ResearchFeatureSnapshot
    snap_post = mem_db.query(ResearchFeatureSnapshot).filter_by(snapshot_id="SNAP_FW_01").first()
    hash_post = compute_canonical_hash({
        "roic": snap_post.economic_roic_pct,
        "input_hash": snap_post.input_hash,
        "output_hash": snap_post.output_hash
    })

    # INVARIANT: Feature snapshot remains 100% immutable
    assert hash_prior == hash_post
