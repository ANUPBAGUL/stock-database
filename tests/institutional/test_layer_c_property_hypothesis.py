"""
Layer C: Property-Based Testing with Hypothesis.
Formally verifies mathematical invariants across infinite randomly generated input spaces:
1. Non-negativity of compounded wealth (W_T >= 0)
2. HHI market concentration mathematical range [0, 10000] and uncertainty ordering (HHI_min <= HHI_max)
3. Symmetry and boundary correctness of half-open interval purging
4. Invariance of canonical hashes to key insertion permutations
"""
import math
from datetime import date, timedelta
from hypothesis import given, strategies as st, settings, assume

from src.analytics.canonical_hasher import canonical_serialize, compute_canonical_hash
from src.analytics.interval_purger import LabelInterval
from src.analytics.competitive_engine import CompetitivePositionEngine
from src.analytics.wealth_compounding_engine import WealthCompoundingEngine

# ── 1. Property: Wealth Compounding Invariants ────────────────────────────────

@settings(max_examples=50)
@given(
    w0=st.floats(min_value=1.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    price_multipliers=st.lists(
        st.floats(min_value=0.01, max_value=5.0, allow_nan=False, allow_infinity=False),
        min_size=1, max_size=20
    ),
    dividends=st.lists(
        st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False),
        min_size=1, max_size=20
    )
)
def test_property_wealth_non_negativity(w0, price_multipliers, dividends):
    # Construct sequence of trading days
    n = min(len(price_multipliers), len(dividends))
    current_price = 100.0
    price_series = [{"date": date(2020, 1, 1), "close": current_price, "dividend": 0.0, "corporate_proceeds": 0.0}]

    for i in range(n):
        current_price = current_price * price_multipliers[i]
        price_series.append({
            "date": date(2020, 1, 1) + timedelta(days=i+1),
            "close": max(0.01, current_price),
            "dividend": dividends[i],
            "corporate_proceeds": 0.0
        })

    res = WealthCompoundingEngine.compute_compounded_wealth(w0, price_series, reinvest_distributions=True)
    # INVARIANT: Compounded wealth must never be negative for valid economic inputs
    assert res["wealth_end"] >= 0.0
    assert not math.isnan(res["wealth_end"])

# ── 2. Property: HHI Range and Bounds Ordering ───────────────────────────────

@settings(max_examples=50)
@given(
    shares=st.lists(
        st.floats(min_value=0.1, max_value=50.0, allow_nan=False, allow_infinity=False),
        min_size=1, max_size=5
    )
)
def test_property_hhi_bounds_ordering(shares):
    # Scale shares so their sum is strictly <= 100%
    total = sum(shares)
    if total > 95.0:
        shares = [s * (90.0 / total) for s in shares]

    share_dict = {f"Firm_{i}": s for i, s in enumerate(shares)}
    res = CompetitivePositionEngine.calculate_rigorous_hhi(share_dict, n_unidentified_min=2, n_unidentified_max=10)

    # INVARIANT 1: Observed HHI must be strictly in [0, 10000]
    assert 0.0 <= res["hhi_observed"] <= 10000.0
    # INVARIANT 2: HHI minimum must be <= HHI maximum
    assert res["hhi_min"] <= res["hhi_max"]
    assert 0.0 <= res["hhi_min"] <= 10000.0
    assert 0.0 <= res["hhi_max"] <= 10000.0

# ── 3. Property: Half-Open Interval Overlap Symmetry ─────────────────────────

@settings(max_examples=50)
@given(
    start1=st.integers(min_value=0, max_value=1000),
    len1=st.integers(min_value=1, max_value=500),
    start2=st.integers(min_value=0, max_value=1000),
    len2=st.integers(min_value=1, max_value=500),
)
def test_property_interval_overlap_symmetry(start1, len1, start2, len2):
    base_date = date(2020, 1, 1)
    inv1 = LabelInterval("O1", "C1", base_date + timedelta(days=start1), base_date + timedelta(days=start1), base_date + timedelta(days=start1 + len1), "H1")
    inv2 = LabelInterval("O2", "C2", base_date + timedelta(days=start2), base_date + timedelta(days=start2), base_date + timedelta(days=start2 + len2), "H2")

    # INVARIANT: Overlap relation is strictly symmetric: overlaps(a, b) == overlaps(b, a)
    assert inv1.overlaps_with(inv2) == inv2.overlaps_with(inv1)

    # INVARIANT: If a.end == b.start, half-open intervals [a.start, a.end) and [b.start, b.end) must NOT overlap
    if inv1.label_end == inv2.label_start and inv1.label_start < inv1.label_end:
        assert inv1.overlaps_with(inv2) is False

# ── 4. Property: Canonical Hash Permutation Invariance ───────────────────────

@settings(max_examples=50)
@given(
    int_val=st.integers(min_value=-1000, max_value=1000),
    float_val=st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    str_val=st.text(min_size=1, max_size=20),
    bool_val=st.booleans()
)
def test_property_canonical_hash_dict_permutation_invariance(int_val, float_val, str_val, bool_val):
    d_order1 = {
        "a_int": int_val,
        "b_float": float_val,
        "c_str": str_val,
        "d_bool": bool_val
    }
    d_order2 = {
        "d_bool": bool_val,
        "c_str": str_val,
        "a_int": int_val,
        "b_float": float_val
    }

    # INVARIANT: Serialized string and SHA-256 hash must be identical regardless of insertion order
    assert canonical_serialize(d_order1) == canonical_serialize(d_order2)
    assert compute_canonical_hash(d_order1) == compute_canonical_hash(d_order2)
