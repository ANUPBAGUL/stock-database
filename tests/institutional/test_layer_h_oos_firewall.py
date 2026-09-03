"""
Layer H: Out-of-Sample (OOS) Firewall & Security Suite.
Verifies:
1. Locked OOS partition boundary enforcement (M7_OOS_2026_V1)
2. Immutability policy (OOS_MUTATION_POLICY = FORBIDDEN)
3. Right-censored / immature outcome handling (Ongoing horizons != Failures)
"""
from datetime import date
import pytest

from src.analytics.oos_firewall import (
    OOSFirewall, LOCKED_OOS_VERSION, OOS_MUTATION_POLICY
)

def test_oos_partitioning_rules():
    # Development: 2015-01-01 to 2021-12-31
    assert OOSFirewall.get_partition(date(2015, 1, 1)) == "DEVELOPMENT"
    assert OOSFirewall.get_partition(date(2021, 12, 31)) == "DEVELOPMENT"

    # Validation: 2022-01-01 to 2023-12-31
    assert OOSFirewall.get_partition(date(2022, 1, 1)) == "VALIDATION"
    assert OOSFirewall.get_partition(date(2023, 12, 31)) == "VALIDATION"

    # Locked OOS: 2024-01-01 to 2026-12-31
    assert OOSFirewall.get_partition(date(2024, 1, 1)) == "LOCKED_OOS"
    assert OOSFirewall.get_partition(date(2026, 6, 30)) == "LOCKED_OOS"

def test_oos_immutability_security_policy():
    assert LOCKED_OOS_VERSION == "M7_OOS_2026_V1"
    assert OOS_MUTATION_POLICY == "FORBIDDEN"

    # Attempting to mutate locked OOS records raises PermissionError
    with pytest.raises(PermissionError):
        OOSFirewall.assert_mutation_allowed(date(2025, 1, 1), action="UPDATE_MODEL_WEIGHTS")

def test_immature_outcomes_not_treated_as_failures():
    """
    CRITICAL INVARIANT:
    A 5Y horizon started on 2024-01-01 evaluated as of 2026-01-01 has only had 2 years of history.
    It MUST be classified as IMMATURE / RIGHT_CENSORED and NEVER as a negative failure!
    """
    res = OOSFirewall.classify_censoring(
        t0_date=date(2024, 1, 1),
        horizon_years=5.0,
        max_available_date=date(2026, 1, 1),
        target_event_occurred=False
    )
    assert res["maturity"] == "IMMATURE"
    assert res["censoring_status"] == "RIGHT_CENSORED"
    assert res["is_ongoing"] is True
    assert res["is_evaluable_for_binary"] is False

def test_mature_outcomes_classified_correctly():
    """
    A 5Y horizon started on 2018-01-01 evaluated as of 2026-01-01 has had > 5 years of runway.
    It is fully mature.
    """
    res = OOSFirewall.classify_censoring(
        t0_date=date(2018, 1, 1),
        horizon_years=5.0,
        max_available_date=date(2026, 1, 1),
        target_event_occurred=False
    )
    assert res["maturity"] == "MATURE"
    assert res["censoring_status"] == "HORIZON_COMPLETED_NO_EVENT"
    assert res["is_ongoing"] is False
    assert res["is_evaluable_for_binary"] is True
