"""T7: air-gap detection [F03-FR-08, F03-AC-12].

03-domain-model section 6: lims_status = 'approved' AND ud_code IS NULL AND now - lims_approved_at >=
threshold_hours. A rejected lot is never an air gap.
"""

from datetime import UTC, datetime, timedelta

import pytest
from r2r_core.airgap import air_gap

NOW = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)
THRESHOLD = 24


def ago(**delta: float) -> datetime:
    return NOW - timedelta(**delta)


def test_f03_ac12_approved_25_hours_ago_without_a_usage_decision_is_an_air_gap() -> None:
    """F03-AC-12: approved 25 h ago, no UD gives (True, 25)."""
    assert air_gap("approved", None, ago(hours=25), NOW, THRESHOLD) == (True, 25)


def test_f03_ac12_approved_23_hours_ago_is_not_yet() -> None:
    assert air_gap("approved", None, ago(hours=23), NOW, THRESHOLD) == (False, 23)


@pytest.mark.parametrize("ud_code", ["A", "A4", "R", "X"])
def test_f03_ac12_any_usage_decision_means_no_air_gap(ud_code: str) -> None:
    """F03-AC-12: an effective UD (A, A4), a rejected UD (R) and a cancelled one (X) are all not air gaps."""
    assert air_gap("approved", ud_code, ago(hours=100), NOW, THRESHOLD)[0] is False


def test_f03_ac12_the_threshold_is_inclusive() -> None:
    assert air_gap("approved", None, ago(hours=24), NOW, THRESHOLD) == (True, 24)
    assert air_gap("approved", None, ago(hours=24, seconds=-1), NOW, THRESHOLD) == (False, 23)


def test_f03_fr08_hours_are_whole_hours_elapsed() -> None:
    assert air_gap("approved", None, ago(hours=25, minutes=59), NOW, THRESHOLD) == (True, 25)


@pytest.mark.parametrize("status", ["rejected", "in_progress", "none"])
def test_f03_fr08_only_approved_lots_can_be_an_air_gap(status: str) -> None:
    """A rejected lot is never an air gap."""
    assert air_gap(status, None, ago(hours=100), NOW, THRESHOLD) == (False, 0)


def test_f03_fr08_approved_without_an_approval_time_is_not_an_air_gap() -> None:
    assert air_gap("approved", None, None, NOW, THRESHOLD) == (False, 0)


def test_f03_fr08_an_approval_in_the_future_never_counts() -> None:
    assert air_gap("approved", None, NOW + timedelta(hours=3), NOW, THRESHOLD) == (False, 0)


def test_f03_fr08_threshold_comes_from_the_caller() -> None:
    assert air_gap("approved", None, ago(hours=5), NOW, 4) == (True, 5)
    assert air_gap("approved", None, ago(hours=5), NOW, 6) == (False, 5)
