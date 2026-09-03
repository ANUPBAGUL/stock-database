"""
Generic Half-Open Label-Interval Purging Engine.
Fulfills Institutional Acceptance Invariant E: Fold-Boundary Label Overlap Invariance.

Rule:
For any observation pair across a fold boundary (e.g. Train vs Test):
overlap(a, b) <=> a.label_start < b.label_end and b.label_start < a.label_end.
Any training observation whose outcome interval overlaps the validation/test outcome interval
must be purged to prevent temporal label contamination.
"""
from dataclasses import dataclass
from datetime import date
from typing import List, Tuple, Optional, Set

@dataclass(frozen=True)
class LabelInterval:
    """
    Immutable specification of an observation's forward outcome evaluation interval.
    """
    observation_id: str
    company_id: str
    t0: date
    label_start: date
    label_end: date
    horizon_type: str = "3Y" # '1Y', '3Y', '5Y', 'SURVIVAL'
    event_type: Optional[str] = None # '10X', 'BANKRUPTCY', etc.
    censoring_status: str = "MATURE" # 'MATURE', 'RIGHT_CENSORED', 'ONGOING'

    def overlaps_with(self, other: "LabelInterval") -> bool:
        """
        Generic half-open interval overlap predicate:
        [a.start, a.end) intersects [b.start, b.end) <=> a.start < b.end and b.start < a.end
        """
        return self.label_start < other.label_end and other.label_start < self.label_end


class PurgedFoldSplitter:
    """
    Fold Splitter enforcing the fold-boundary label-interval purging invariant.
    """

    @staticmethod
    def check_intervals_overlap(interval_a: LabelInterval, interval_b: LabelInterval) -> bool:
        return interval_a.overlaps_with(interval_b)

    @staticmethod
    def purge_train_set(
        train_intervals: List[LabelInterval],
        test_intervals: List[LabelInterval]
    ) -> Tuple[List[LabelInterval], List[LabelInterval]]:
        """
        Purges any training interval that has an overlapping outcome interval
        with ANY test interval across the fold boundary.

        Returns:
            (retained_train_intervals, purged_train_intervals)
        """
        purged_ids: Set[str] = set()

        for train_item in train_intervals:
            for test_item in test_intervals:
                if train_item.overlaps_with(test_item):
                    purged_ids.add(train_item.observation_id)
                    break # Purged, no need to check further test items

        retained = [item for item in train_intervals if item.observation_id not in purged_ids]
        purged = [item for item in train_intervals if item.observation_id in purged_ids]
        return retained, purged

    @staticmethod
    def assert_zero_fold_overlap(
        train_intervals: List[LabelInterval],
        test_intervals: List[LabelInterval]
    ) -> bool:
        """
        Acceptance assertion for Invariant E:
        Verifies that no train/test observation pair has an overlapping outcome interval.
        Raises AssertionError with offending pair if violation is found.
        """
        for train_item in train_intervals:
            for test_item in test_intervals:
                if train_item.overlaps_with(test_item):
                    raise AssertionError(
                        f"Fold-boundary interval overlap detected!\n"
                        f"Train Obs: {train_item.observation_id} [{train_item.label_start} -> {train_item.label_end}]\n"
                        f"Test Obs:  {test_item.observation_id} [{test_item.label_start} -> {test_item.label_end}]"
                    )
        return True
