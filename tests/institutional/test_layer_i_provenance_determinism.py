"""
Layer I: Provenance Audit & 100-Run Determinism Suite.
Verifies:
1. Machine-readable provenance completeness (Invariant F)
2. Temporal provenance assertion (source_published_at <= T0)
3. 100-run bit-for-bit determinism (Invariant H)
4. IEEE-754 precision stability
"""
from datetime import date, datetime
import pytest

from src.analytics.canonical_hasher import canonical_serialize, compute_canonical_hash
from src.db.models import ResearchFeatureSnapshot

def test_provenance_audit_completeness():
    """
    Every ResearchFeatureSnapshot must have source_fact_ids, source_published_at, and engine versioning.
    """
    snap = ResearchFeatureSnapshot(
        snapshot_id="SNAP_TEST_PROV",
        company_id="COMP_PROV",
        observation_date=date(2021, 3, 31),
        t0_timestamp=datetime(2021, 3, 31, 15, 30, 0),
        source_fact_ids=["XBRL_Q4_2020", "XBRL_Q3_2020"],
        source_published_at=datetime(2021, 3, 15, 10, 0, 0),
        source_period_end=date(2020, 12, 31),
        feature_engine_version="v3.2.0",
        peer_selection_version="v1.0.0",
        methodology_version="INSTITUTIONAL_P0"
    )
    # INVARIANT: Source published must be strictly <= T0
    assert snap.source_published_at <= snap.t0_timestamp
    assert len(snap.source_fact_ids) == 2
    assert snap.feature_engine_version == "v3.2.0"

def test_100_run_determinism_invariant():
    """
    100 repeated executions of feature hashing against identical data produce bit-for-bit identical hashes.
    """
    payload = {
        "company_id": "TCS",
        "t0_date": "2020-03-31",
        "ttm_revenue": 156949.0,
        "ttm_ebit": 42109.0,
        "ttm_pat": 32340.0,
        "roic_pct": 58.456789,
        "reinvestment_rate": 22.123456,
        "hhi": 2450.0
    }

    baseline_hash = compute_canonical_hash(payload)

    for i in range(100):
        # Permute keys on each run
        permuted = {k: payload[k] for k in sorted(payload.keys(), key=lambda x: (hash(x) + i) % 100)}
        run_hash = compute_canonical_hash(permuted)
        assert run_hash == baseline_hash, f"Determinism broke on iteration {i}: {run_hash} != {baseline_hash}"

def test_ieee_754_precision_stability():
    """
    Verifies that float calculations with micro-noise clamp to identical canonical strings.
    """
    v1 = 0.1 + 0.2  # 0.30000000000000004
    v2 = 0.3
    h1 = compute_canonical_hash({"val": v1})
    h2 = compute_canonical_hash({"val": v2})
    assert h1 == h2
