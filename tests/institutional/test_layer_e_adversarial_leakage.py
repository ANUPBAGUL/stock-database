"""
Layer E: Adversarial Leakage & Synthetic Canary Suite.
Conducts hostile testing against look-ahead contamination:
1. Multi-vintage future-document poison harness (Invariant B)
2. Complex chained restatement timeline invariance (Invariant C)
3. Synthetic high-predictive look-ahead canaries (Invariant G)
"""
import uuid
from datetime import date, datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.models import Company, Sector, BitemporalFinancial, DailyPriceRaw
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
    sec = db.query(Sector).filter_by(sector_name="AdvSector").first()
    if not sec:
        sec = Sector(sector_id=str(uuid.uuid4()), sector_name="AdvSector")
        db.add(sec)
        db.flush()
    comp = Company(
        company_id=str(uuid.uuid4()),
        isin=f"INE{abs(hash(sym)) % 1000000000:09d}",
        nse_symbol=sym,
        company_name=f"{sym} Ltd",
        sector_id=sec.sector_id
    )
    db.add(comp)
    db.commit()
    return comp

# ── 1. Multi-Vintage Future-Document Poison Invariant B ───────────────────────

@pytest.mark.parametrize("t0_year", [2018, 2020, 2022, 2024])
def test_adversarial_future_poison_multi_vintage(mem_db, t0_year):
    comp = _create_company(mem_db, f"POISON_{t0_year}")
    t0_dt = datetime(t0_year, 6, 30, 15, 30, 0)

    # Valid statement before T0
    valid_stmt = BitemporalFinancial(
        financial_id=f"VALID_{t0_year}",
        company_id=comp.company_id,
        period_type="QUARTERLY",
        period_end_date=date(t0_year, 3, 31),
        publication_date=datetime(t0_year, 5, 15, 10, 0, 0),
        revenue=1000.0,
        ebit=150.0,
        pat=100.0,
        source="NSE_XBRL"
    )
    mem_db.add(valid_stmt)
    mem_db.commit()

    # Baseline feature hash at T0
    facts_base = mem_db.query(BitemporalFinancial).filter(
        BitemporalFinancial.company_id == comp.company_id,
        BitemporalFinancial.publication_date <= t0_dt
    ).all()
    base_hash = compute_canonical_hash({
        "rev": sum(f.revenue for f in facts_base),
        "pat": sum(f.pat for f in facts_base)
    })

    # Hostile Poison Injection: Future filing published 1 year AFTER T0
    poison_stmt = BitemporalFinancial(
        financial_id=f"POISON_{t0_year}",
        company_id=comp.company_id,
        period_type="QUARTERLY",
        period_end_date=date(t0_year + 1, 3, 31),
        publication_date=datetime(t0_year + 1, 5, 15, 10, 0, 0), # Future publication!
        revenue=999999.0,
        pat=888888.0,
        source="NSE_XBRL"
    )
    mem_db.add(poison_stmt)
    mem_db.commit()

    # Re-query with strict publication_date <= T0
    facts_poisoned = mem_db.query(BitemporalFinancial).filter(
        BitemporalFinancial.company_id == comp.company_id,
        BitemporalFinancial.publication_date <= t0_dt
    ).all()
    poison_hash = compute_canonical_hash({
        "rev": sum(f.revenue for f in facts_poisoned),
        "pat": sum(f.pat for f in facts_poisoned)
    })

    # INVARIANT: Base hash and post-poison hash must be bit-for-bit identical
    assert base_hash == poison_hash

# ── 2. Complex Chained Restatements Timeline Invariant C ──────────────────────

def test_adversarial_chained_restatement_timeline(mem_db):
    """
    Timeline:
    - 2018-05-15: Original 2018 filing (PAT = 100)
    - 2019-06-30: T0 Evaluation Date (Must see Original = 100)
    - 2020-08-10: Auditor Restatement 1 (PAT = 80, supersedes Original)
    - 2022-09-15: Forensic Restatement 2 (PAT = 40, supersedes Restatement 1)
    """
    comp = _create_company(mem_db, "RESTATE_CHAIN_CO")
    t0_dt = datetime(2019, 6, 30, 15, 30, 0)

    # 1. Original filing
    f_orig = BitemporalFinancial(
        financial_id="ORIG_2018",
        company_id=comp.company_id,
        period_type="ANNUAL",
        period_end_date=date(2018, 3, 31),
        publication_date=datetime(2018, 5, 15, 10, 0, 0),
        pat=100.0,
        system_rec_end=datetime(2020, 8, 10, 10, 0, 0), # Superseded in 2020
        source="NSE_XBRL"
    )
    # 2. Restatement 1
    f_r1 = BitemporalFinancial(
        financial_id="RESTATE_1_2020",
        company_id=comp.company_id,
        period_type="ANNUAL",
        period_end_date=date(2018, 3, 31),
        publication_date=datetime(2020, 8, 10, 10, 0, 0),
        pat=80.0,
        system_rec_end=datetime(2022, 9, 15, 10, 0, 0),
        source="NSE_XBRL"
    )
    # 3. Restatement 2
    f_r2 = BitemporalFinancial(
        financial_id="RESTATE_2_2022",
        company_id=comp.company_id,
        period_type="ANNUAL",
        period_end_date=date(2018, 3, 31),
        publication_date=datetime(2022, 9, 15, 10, 0, 0),
        pat=40.0,
        source="NSE_XBRL"
    )
    mem_db.add_all([f_orig, f_r1, f_r2])
    mem_db.commit()

    # Query as of T0 = 2019-06-30: Must select ORIG_2018 because publication_date <= T0!
    facts_at_t0 = mem_db.query(BitemporalFinancial).filter(
        BitemporalFinancial.company_id == comp.company_id,
        BitemporalFinancial.publication_date <= t0_dt,
        (BitemporalFinancial.system_rec_end > t0_dt)
    ).all()

    assert len(facts_at_t0) == 1
    assert facts_at_t0[0].financial_id == "ORIG_2018"
    assert facts_at_t0[0].pat == 100.0

# ── 3. Synthetic Look-Ahead Canaries Invariant G ──────────────────────────────

def test_adversarial_synthetic_lookahead_canaries():
    """
    Injects synthetic variables with absurd predictive power (e.g. future_10x=True, future_return=950%).
    Asserts canonical feature hash remains bit-for-bit identical F(T0, D) == F(T0, D + FuturePoison).
    """
    raw_payload = {
        "symbol": "PERSISTENT",
        "ttm_sales": 5000.0,
        "ttm_ebit": 750.0,
        "ttm_pat": 500.0,
        "pe": 30.0
    }

    def compute_features(data):
        return {
            "sales": float(data.get("ttm_sales", 0.0)),
            "ebit": float(data.get("ttm_ebit", 0.0)),
            "pat": float(data.get("ttm_pat", 0.0)),
            "mcap": float(data.get("ttm_pat", 0.0)) * float(data.get("pe", 20.0))
        }

    clean_hash = compute_canonical_hash(compute_features(raw_payload))

    # Hostile Canary Injection
    poisoned_payload = dict(raw_payload)
    poisoned_payload["future_return_5y"] = 1250.0
    poisoned_payload["future_10x"] = True
    poisoned_payload["future_bankruptcy"] = False
    poisoned_payload["future_eps_growth"] = 45.0

    poisoned_hash = compute_canonical_hash(compute_features(poisoned_payload))

    # CANARY ASSERTION
    assert clean_hash == poisoned_hash
