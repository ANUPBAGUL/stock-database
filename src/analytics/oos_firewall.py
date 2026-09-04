"""
Locked Out-of-Sample (OOS) Firewall & Partitioning Engine.
Version: M7_OOS_2026_V1
Invariant: OOS_MUTATION_POLICY = FORBIDDEN.

Partitions the historical dataset into:
1. Development: 2015-01-01 to 2021-12-31
2. Validation:  2022-01-01 to 2023-12-31
3. Locked OOS:  2024-01-01 to 2026-12-31

Crucially: Separates Mature OOS from Immature OOS.
An immature observation (e.g. 2025 observation evaluated for 5Y horizon) is NOT a failure;
it is marked ONGOING / RIGHT_CENSORED.
"""
from datetime import date
from typing import Dict, Any, Optional

LOCKED_OOS_VERSION = "M7_OOS_2026_V1"
OOS_MUTATION_POLICY = "FORBIDDEN"

DEV_START = date(2015, 1, 1)
DEV_END = date(2021, 12, 31)

VAL_START = date(2022, 1, 1)
VAL_END = date(2023, 12, 31)

OOS_START = date(2024, 1, 1)
OOS_END = date(2026, 12, 31)

class OOSFirewall:
    """
    Guarantees strict partitioning and prevents post-evaluation model mutation.
    """

    @staticmethod
    def get_partition(t0_date: date) -> str:
        """
        Determines the dataset partition for a given T0 observation date.
        """
        if t0_date <= DEV_END:
            return "DEVELOPMENT"
        elif VAL_START <= t0_date <= VAL_END:
            return "VALIDATION"
        elif OOS_START <= t0_date <= OOS_END:
            return "LOCKED_OOS"
        else:
            return "OUT_OF_BOUNDS"

    @staticmethod
    def classify_censoring(
        t0_date: date,
        horizon_years: float,
        max_available_date: date,
        target_event_occurred: bool
    ) -> Dict[str, Any]:
        """
        Classifies outcome maturity vs censoring.
        If the required horizon exceeds max_available_date and target event hasn't occurred,
        it is marked ONGOING/RIGHT_CENSORED rather than a negative/failure.
        """
        # Calculate expected completion date using exact calendar day offset
        days_in_horizon = int(horizon_years * 365.25)
        expected_end_date = date.fromordinal(t0_date.toordinal() + days_in_horizon)

        if target_event_occurred:
            return {
                "maturity": "MATURE",
                "censoring_status": "EVENT_OBSERVED",
                "is_evaluable_for_binary": True,
                "is_ongoing": False
            }

        if max_available_date >= expected_end_date:
            return {
                "maturity": "MATURE",
                "censoring_status": "HORIZON_COMPLETED_NO_EVENT",
                "is_evaluable_for_binary": True,
                "is_ongoing": False
            }
        else:
            # Administrative / Right Censoring: Required time has not yet elapsed in history!
            return {
                "maturity": "IMMATURE",
                "censoring_status": "RIGHT_CENSORED",
                "is_evaluable_for_binary": False,
                "is_ongoing": True
            }

    @staticmethod
    def assert_mutation_allowed(t0_date: date, action: str = "MUTATION"):
        """
        Enforces OOS_MUTATION_POLICY = FORBIDDEN for Locked OOS records.
        """
        partition = OOSFirewall.get_partition(t0_date)
        if partition == "LOCKED_OOS":
            raise PermissionError(
                f"FORBIDDEN: Mutation action '{action}' on Locked OOS partition ({LOCKED_OOS_VERSION}) is strictly prohibited!"
            )
        return True

    @staticmethod
    def assert_oos_immutability(evaluation_state: Dict[str, Any]):
        """
        Verifies that model parameters or feature definitions have not been mutated
        after inspecting Locked OOS results.
        """
        if evaluation_state.get("oos_evaluated", False):
            if evaluation_state.get("model_modified_post_eval", False):
                raise PermissionError(
                    f"CRITICAL LEAKAGE VIOLATION: Model was modified after inspecting {LOCKED_OOS_VERSION}! "
                    f"Policy: OOS_MUTATION_POLICY = {OOS_MUTATION_POLICY}. Locked test data must never be reused for tuning."
                )
        return True
