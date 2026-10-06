"""F09 T2 [TDD]: row composition (F09-FR-01), on plain dicts, no database."""

import datetime as dt
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app_api.services.compose import CurrentOverride, compose_row
from r2r_core.profile import SiteProfile, load_profile
from support_f09 import NOW, D, batch


@pytest.fixture(scope="module")
def profile() -> SiteProfile:
    return load_profile("site_a")


def override(value: object, reason: str | None = None, version: int = 1) -> CurrentOverride:
    return CurrentOverride(value, reason, None, version, "pat", NOW)


def test_f09_fr01_without_overrides_the_system_need_by_is_operative(profile: SiteProfile) -> None:
    row = compose_row(batch(), {}, None, 0, profile, NOW)
    assert row.operative_need_by == D(12, 3) and row.adjusted is None and not row.expedite
    assert row.plan.expected_completion == D(10, 15) and row.plan.rag == "green" and not row.plan.compressed
    assert row.plan.days_in_stage == 4 and row.latest_status is None and row.status_log_count == 0


def test_f09_ac02_an_adjusted_need_by_replaces_the_locked_one_and_compresses(profile: SiteProfile) -> None:
    adjusted = {"adjusted_need_by_date": override("2026-11-26", "CAMPAIGN_PULLED_FORWARD")}
    row = compose_row(batch(), adjusted, None, 0, profile, NOW)
    assert row.operative_need_by == D(11, 26) and row.adjusted is not None
    assert row.plan.compressed and row.plan.compression_ratio == Decimal("0.875")
    assert [*row.plan.effective_slas.values()] == [6, 37, 6]
    assert row.plan.expected_completion == D(10, 14) and row.plan.rag == "amber"


def test_f09_fr01_a_cleared_override_restores_the_system_date(profile: SiteProfile) -> None:
    cleared = {"adjusted_need_by_date": override(None)}
    row = compose_row(batch(), cleared, None, 0, profile, NOW)
    assert row.adjusted is None and row.operative_need_by == D(12, 3)


def test_f19_fr05_expedite_latest_status_and_log_count_are_carried(profile: SiteProfile) -> None:
    entry = {
        "status": "blocked", "team": "QC Lab", "reason_code": "equipment_issue", "comment": "Instrument down",
        "author_user_key": "quinn", "at": NOW,
    }  # fmt: skip
    row = compose_row(batch(), {"expedite": override(True)}, entry, 3, profile, NOW)
    assert row.expedite and row.status_log_count == 3
    assert row.latest_status is not None
    assert (row.latest_status.label, row.latest_status.colour, row.latest_status.reason_label) == (
        "Blocked",
        "red",
        "Equipment issue",
    )
    assert row.plan.rag == "green"  # a status never changes the system calculation (OQ-057)


def test_f09_ac08_an_approved_lot_without_a_usage_decision_is_an_air_gap(profile: SiteProfile) -> None:
    approved = NOW - timedelta(hours=30)
    row = compose_row(
        batch("B5003", stage_key="qa_release", lims_status="approved", lims_approved_at=approved,
              current_stage_entry_date=D(10, 11)),
        {}, None, 0, profile, NOW,
    )  # fmt: skip
    assert row.air_gap and row.air_gap_hours == 30


def test_f09_fr01_a_released_row_has_no_plan(profile: SiteProfile) -> None:
    row = compose_row(batch(stage_key="released", ud_effective=True, current_stage_entry_date=D(10, 9)),
                      {}, None, 0, profile, NOW)  # fmt: skip
    assert row.plan.expected_completion is None and row.stage_terminal and not row.plan.late


def test_f09_fr01_today_is_the_site_date_not_the_utc_date(profile: SiteProfile) -> None:
    late_evening = datetime(2026, 10, 12, 23, 30, tzinfo=UTC)  # already the 13th in the site timezone
    row = compose_row(batch(), {}, None, 0, profile, late_evening)
    assert (
        row.plan.days_in_stage
        == (late_evening.astimezone(profile.site.tz).date() - dt.date(2026, 10, 8)).days
    )
