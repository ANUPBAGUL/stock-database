"""
Layer G: Survivorship & 4-Tier Universe System Suite.
Verifies:
1. Historical universe reconstruction with defunct/bankrupt companies (Invariant D)
2. Four orthogonal universe dimensions (listing, tradability, liquidity, research)
3. Precise date boundary conditions (entering/leaving exactly on T0)
"""
import uuid
from datetime import date
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.models import Company, Sector, UniverseMembership

@pytest.fixture
def mem_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def _add_cohort_company(db, sym, name, listing, tradability, liquidity, research):
    sec = db.query(Sector).filter_by(sector_name="General").first()
    if not sec:
        sec = Sector(sector_id=str(uuid.uuid4()), sector_name="General")
        db.add(sec)
        db.flush()
    comp = Company(
        company_id=str(uuid.uuid4()),
        isin=f"INE{abs(hash(sym)) % 1000000000:09d}",
        nse_symbol=sym,
        company_name=name,
        sector_id=sec.sector_id,
        listing_status=listing,
        tradability_status=tradability,
        liquidity_status=liquidity,
        research_eligibility=research
    )
    db.add(comp)
    db.commit()
    return comp

def test_survivorship_historical_cohort_reconstruction(mem_db):
    """
    Constructs a 2017 cohort:
    - SURVIVOR: Active through 2026
    - BANKRUPT_2019: Constituent 2016-2019, delisted 2019-11-01
    - ACQUIRED_2021: Constituent 2016-2021, merged 2021-05-01
    - LATE_ENTRANT_2022: IPO in 2022
    """
    c_surv = _add_cohort_company(mem_db, "SURVIVOR", "Survivor Ltd", "ACTIVE", "TRADABLE", "HIGH", "ELIGIBLE")
    c_bank = _add_cohort_company(mem_db, "DHFL_MOCK", "DHFL Mock Ltd", "BANKRUPTCY", "SUSPENDED", "ILLIQUID", "ELIGIBLE")
    c_acq = _add_cohort_company(mem_db, "MINDTREE_MOCK", "Mindtree Mock Ltd", "MERGED", "SUSPENDED", "HIGH", "ELIGIBLE")
    c_late = _add_cohort_company(mem_db, "ZOMATO_MOCK", "Zomato Mock Ltd", "ACTIVE", "TRADABLE", "HIGH", "ELIGIBLE")

    m_surv = UniverseMembership(membership_id="M1", company_id=c_surv.company_id, symbol="SURVIVOR", universe_name="NIFTY_500", effective_from=date(2016, 1, 1), effective_to=None)
    m_bank = UniverseMembership(membership_id="M2", company_id=c_bank.company_id, symbol="DHFL_MOCK", universe_name="NIFTY_500", effective_from=date(2016, 1, 1), effective_to=date(2019, 11, 1))
    m_acq = UniverseMembership(membership_id="M3", company_id=c_acq.company_id, symbol="MINDTREE_MOCK", universe_name="NIFTY_500", effective_from=date(2016, 1, 1), effective_to=date(2021, 5, 1))
    m_late = UniverseMembership(membership_id="M4", company_id=c_late.company_id, symbol="ZOMATO_MOCK", universe_name="NIFTY_500", effective_from=date(2022, 1, 1), effective_to=None)
    mem_db.add_all([m_surv, m_bank, m_acq, m_late])
    mem_db.commit()

    # Query investable universe as of 2017-06-30
    t0_2017 = date(2017, 6, 30)
    u_2017 = mem_db.query(UniverseMembership).filter(
        UniverseMembership.universe_name == "NIFTY_500",
        UniverseMembership.effective_from <= t0_2017,
        (UniverseMembership.effective_to.is_(None) | (UniverseMembership.effective_to >= t0_2017))
    ).all()
    syms_2017 = {u.symbol for u in u_2017}

    # INVARIANT: 2017 universe MUST contain survivor, bankrupt firm, and acquired firm, but NOT late entrant
    assert "SURVIVOR" in syms_2017
    assert "DHFL_MOCK" in syms_2017
    assert "MINDTREE_MOCK" in syms_2017
    assert "ZOMATO_MOCK" not in syms_2017

    # Query investable universe as of 2024-06-30
    t0_2024 = date(2024, 6, 30)
    u_2024 = mem_db.query(UniverseMembership).filter(
        UniverseMembership.universe_name == "NIFTY_500",
        UniverseMembership.effective_from <= t0_2024,
        (UniverseMembership.effective_to.is_(None) | (UniverseMembership.effective_to >= t0_2024))
    ).all()
    syms_2024 = {u.symbol for u in u_2024}

    # INVARIANT: 2024 universe MUST contain survivor and late entrant, but NOT bankrupt or merged firm
    assert "SURVIVOR" in syms_2024
    assert "ZOMATO_MOCK" in syms_2024
    assert "DHFL_MOCK" not in syms_2024
    assert "MINDTREE_MOCK" not in syms_2024

def test_orthogonal_dimensions_independence(mem_db):
    """
    Verifies that changing tradability or liquidity does not mutate listing or research status.
    """
    comp = _add_cohort_company(mem_db, "ORTHO_CO", "Ortho Corp", "ACTIVE", "TRADABLE", "HIGH", "ELIGIBLE")
    assert comp.listing_status == "ACTIVE"
    assert comp.tradability_status == "TRADABLE"
    assert comp.liquidity_status == "HIGH"
    assert comp.research_eligibility == "ELIGIBLE"

    # Stock temporarily enters ASM/GSM circuit or illiquidity
    comp.tradability_status = "RESTRICTED"
    comp.liquidity_status = "LOW"
    mem_db.commit()

    refreshed = mem_db.query(Company).filter_by(nse_symbol="ORTHO_CO").first()
    assert refreshed.listing_status == "ACTIVE"  # Unchanged!
    assert refreshed.tradability_status == "RESTRICTED"
    assert refreshed.liquidity_status == "LOW"
    assert refreshed.research_eligibility == "ELIGIBLE"  # Unchanged!

def test_universe_exact_boundary_dates(mem_db):
    """
    Tests exact boundary convention:
    effective_from = 2020-01-01, effective_to = 2020-12-31.
    Query at 2020-01-01 -> Included.
    Query at 2020-12-31 -> Included.
    Query at 2021-01-01 -> Excluded.
    """
    comp = _add_cohort_company(mem_db, "BOUND_CO", "Boundary Corp", "ACTIVE", "TRADABLE", "HIGH", "ELIGIBLE")
    m = UniverseMembership(membership_id="MB1", company_id=comp.company_id, symbol="BOUND_CO", universe_name="NIFTY_500", effective_from=date(2020, 1, 1), effective_to=date(2020, 12, 31))
    mem_db.add(m)
    mem_db.commit()

    def is_member_on(d):
        return mem_db.query(UniverseMembership).filter(
            UniverseMembership.company_id == comp.company_id,
            UniverseMembership.effective_from <= d,
            (UniverseMembership.effective_to.is_(None) | (UniverseMembership.effective_to >= d))
        ).count() > 0

    assert is_member_on(date(2020, 1, 1)) is True
    assert is_member_on(date(2020, 12, 31)) is True
    assert is_member_on(date(2021, 1, 1)) is False
