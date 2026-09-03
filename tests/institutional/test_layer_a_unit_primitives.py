"""
Layer A: Unit Tests for Core Mathematical & Serialization Primitives.
Verifies:
1. Deterministic canonical serialization across all JSON/Python types
2. Generic half-open interval overlap mathematics [start, end)
3. Herfindahl-Hirschman Index (HHI) mathematical bounds & scale
4. Shareholder wealth compounding formula primitives
5. Terminal economic recovery calculations (CIRP / Restructuring)
"""
import math
from datetime import date, datetime
from decimal import Decimal
import pytest

from src.analytics.canonical_hasher import (
    canonical_serialize_value, canonical_serialize, compute_canonical_hash
)
from src.analytics.interval_purger import LabelInterval, PurgedFoldSplitter
from src.analytics.competitive_engine import CompetitivePositionEngine
from src.analytics.wealth_compounding_engine import (
    WealthCompoundingEngine, TerminalEventRecord
)

# ── 1. Canonical Serialization & Hashing Primitives ──────────────────────────

def test_canonical_serialize_scalar_types():
    assert canonical_serialize({"val": None}) == '{"val":null}'
    assert canonical_serialize({"val": True}) == '{"val":true}'
    assert canonical_serialize({"val": False}) == '{"val":false}'
    assert canonical_serialize({"val": 42}) == '{"val":42}'
    assert canonical_serialize({"val": "test_symbol"}) == '{"val":"test_symbol"}'
    assert canonical_serialize({"val": date(2020, 1, 1)}) == '{"val":"2020-01-01"}'
    assert canonical_serialize({"val": datetime(2020, 1, 1, 12, 0, 0)}) == '{"val":"2020-01-01T12:00:00Z"}'

def test_canonical_serialize_float_precision_clamping():
    # Micro-noise beyond 6 decimals must serialize to identical JSON string
    f1 = 12.3456781111
    f2 = 12.3456782222
    assert canonical_serialize({"val": f1}) == '{"val":12.345678}'
    assert canonical_serialize({"val": f2}) == '{"val":12.345678}'
    assert canonical_serialize({"val": f1}) == canonical_serialize({"val": f2})

def test_canonical_serialize_dict_key_sorting():
    d1 = {"z_score": 1.5, "alpha": 0.2, "beta": 1.1}
    d2 = {"alpha": 0.2, "beta": 1.1, "z_score": 1.5}
    assert canonical_serialize(d1) == canonical_serialize(d2)
    assert compute_canonical_hash(d1) == compute_canonical_hash(d2)

def test_canonical_serialize_nested_structures():
    nested1 = {"outer": [1, {"k2": 2, "k1": 1}, 3], "name": "TEST"}
    nested2 = {"name": "TEST", "outer": [1, {"k1": 1, "k2": 2}, 3]}
    assert canonical_serialize(nested1) == canonical_serialize(nested2)
    assert compute_canonical_hash(nested1) == compute_canonical_hash(nested2)

# ── 2. Half-Open Interval Overlap Mathematics ────────────────────────────────

def test_half_open_interval_adjacent_disjoint():
    # [2020-01-01 -> 2021-01-01) and [2021-01-01 -> 2022-01-01) DO NOT overlap!
    inv1 = LabelInterval("OBS1", "COMP1", date(2020, 1, 1), date(2020, 1, 1), date(2021, 1, 1), "1Y")
    inv2 = LabelInterval("OBS2", "COMP2", date(2021, 1, 1), date(2021, 1, 1), date(2022, 1, 1), "1Y")
    assert inv1.overlaps_with(inv2) is False
    assert inv2.overlaps_with(inv1) is False

def test_half_open_interval_partial_overlap():
    # [2020-01-01 -> 2022-01-01) and [2021-06-01 -> 2023-06-01) overlap!
    inv1 = LabelInterval("OBS1", "COMP1", date(2020, 1, 1), date(2020, 1, 1), date(2022, 1, 1), "2Y")
    inv2 = LabelInterval("OBS2", "COMP2", date(2021, 6, 1), date(2021, 6, 1), date(2023, 6, 1), "2Y")
    assert inv1.overlaps_with(inv2) is True
    assert inv2.overlaps_with(inv1) is True

def test_half_open_interval_complete_containment():
    # [2020-01-01 -> 2025-01-01) contains [2021-01-01 -> 2022-01-01)
    inv1 = LabelInterval("OBS1", "COMP1", date(2020, 1, 1), date(2020, 1, 1), date(2025, 1, 1), "5Y")
    inv2 = LabelInterval("OBS2", "COMP2", date(2021, 1, 1), date(2021, 1, 1), date(2022, 1, 1), "1Y")
    assert inv1.overlaps_with(inv2) is True
    assert inv2.overlaps_with(inv1) is True

def test_half_open_interval_identical():
    inv1 = LabelInterval("OBS1", "COMP1", date(2020, 1, 1), date(2020, 1, 1), date(2023, 1, 1), "3Y")
    inv2 = LabelInterval("OBS2", "COMP2", date(2020, 1, 1), date(2020, 1, 1), date(2023, 1, 1), "3Y")
    assert inv1.overlaps_with(inv2) is True

# ── 3. Herfindahl-Hirschman Index (HHI) Mathematical Bounds ──────────────────

def test_hhi_pure_monopoly():
    # 100% share for 1 player: HHI = 10000 * (1.0^2) = 10000
    res = CompetitivePositionEngine.calculate_rigorous_hhi({"PlayerA": 100.0})
    assert res["hhi_observed"] == 10000.0
    assert res["market_structure"] == "CONCENTRATED_OLIGOPOLY"

def test_hhi_equal_duopoly():
    # Two 50% players: HHI = 10000 * (0.5^2 + 0.5^2) = 5000
    res = CompetitivePositionEngine.calculate_rigorous_hhi({"PlayerA": 50.0, "PlayerB": 50.0})
    assert res["hhi_observed"] == 5000.0

def test_hhi_perfectly_fragmented_bounds():
    # Ten 10% players: HHI = 10000 * 10 * 0.01 = 1000
    shares = {f"Player_{i}": 10.0 for i in range(10)}
    res = CompetitivePositionEngine.calculate_rigorous_hhi(shares)
    assert res["hhi_observed"] == 1000.0
    assert res["market_structure"] == "FRAGMENTED_COMMODITY"

def test_hhi_uncertainty_bounds_with_residual():
    # 3 identified players with 30%, 20%, 10% (Sum = 60%). Residual = 40%.
    res = CompetitivePositionEngine.calculate_rigorous_hhi(
        {"P1": 30.0, "P2": 20.0, "P3": 10.0},
        n_unidentified_min=2,
        n_unidentified_max=10
    )
    assert res["identified_share_pct"] == 60.0
    assert res["residual_unidentified_share_pct"] == 40.0
    # Base identified HHI = 10000 * (0.09 + 0.04 + 0.01) = 1400.0
    assert res["hhi_observed"] == 1400.0
    # HHI min (residual split equally among 10 players) <= HHI max (residual concentrated in 2 players)
    assert res["hhi_min"] <= res["hhi_max"]
    assert res["hhi_min"] >= 1400.0

# ── 4. Wealth Compounding & Terminal Economic Recovery Primitives ─────────────

def test_wealth_compounding_single_step():
    # Day 0: Price = 100. Day 1: Price = 110, Dividend = 5, Corporate proceeds = 0
    prices = [
        {"date": date(2020, 1, 1), "close": 100.0, "dividend": 0.0, "corporate_proceeds": 0.0},
        {"date": date(2020, 1, 2), "close": 110.0, "dividend": 5.0, "corporate_proceeds": 0.0}
    ]
    res = WealthCompoundingEngine.compute_compounded_wealth(100.0, prices, reinvest_distributions=True)
    # Price gain = 10%, dividend yield = 5/100 = 5%. Total return = 15%
    assert res["wealth_start"] == 100.0
    assert res["wealth_end"] == 115.0
    assert res["total_return_pct"] == 15.0

def test_terminal_economic_recovery_restructuring():
    # Initial investment at Rs 100. CIRP gives Rs 20 cash recovery + Rs 10 equity consideration.
    event = TerminalEventRecord(
        event_date=date(2022, 1, 1),
        event_type="BANKRUPTCY",
        status="RESTRUCTURING_RESOLVED",
        terminal_equity_value_per_share=10.0,
        cash_recovery_per_share=20.0
    )
    rec = WealthCompoundingEngine.compute_terminal_economic_recovery(100.0, 10.0, event)
    # Total recovery = Rs 30 / share. Initial = Rs 100. Realized return = -70.0%
    assert rec["total_recovery_per_share"] == 30.0
    assert rec["terminal_return_pct"] == -70.0
    assert rec["is_total_loss"] is False
