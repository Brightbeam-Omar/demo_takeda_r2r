"""T4 [TDD]: the read-time report maths (F20-FR-03, F20-AC-01, F20-AC-05, F20-AC-06, OQ-117 to OQ-126)."""

from datetime import date
from decimal import Decimal

import pytest
from r2r_core.profile import SiteProfile
from r2r_core.reports import (
    LateCandidate,
    LogEntry,
    NeedByVersion,
    ReleasedLot,
    Trend,
    adherence_by_week,
    coverage,
    expedite_on_time,
    late_items,
    needs_by_adherence,
    release_rate,
    stage_metric_map,
    trend,
)
from r2r_core.sla import PlanResult

D = date
TODAY = D(2026, 10, 12)  # Monday of ISO week 42


def lot(
    key: str, ud: date | None, need_by: date | None = None, due: date | None = None, **kw: object
) -> ReleasedLot:
    return ReleasedLot(
        row_key=key,
        ud_date=ud,
        ud_effective=ud is not None,
        need_by_at_release=need_by,
        expedite_due_date=due,
    )


# --- coverage and release rate (OQ-117, F20-AC-01) ----------------------------------------------


def test_f20_ac01_coverage_runs_in_whole_iso_weeks_from_the_earliest_release_to_the_snapshot_week() -> None:
    rows = [lot("a", D(2026, 4, 15)), lot("b", D(2026, 6, 1)), lot("c", D(2025, 12, 30))]  # c is another year
    first, weeks = coverage(rows, 2026, TODAY)
    assert first == D(2026, 4, 15)  # a Wednesday: its ISO week starts 13 Apr
    assert weeks == 27  # weeks starting 13 Apr .. 12 Oct inclusive


def test_f20_ac01_coverage_is_capped_at_52_and_empty_without_releases() -> None:
    assert coverage([lot("a", D(2026, 1, 1))], 2026, TODAY)[1] == 42  # Jan 1 is in the week of 29 Dec 2025
    assert coverage([lot("a", D(2025, 1, 1))], 2025, TODAY) == (D(2025, 1, 1), 52)  # past year: ends 31 Dec
    assert coverage([], 2026, TODAY) == (None, 0)
    assert coverage([lot("a", None)], 2026, TODAY) == (None, 0)


def test_f20_ac01_release_rate_counts_lots_with_an_effective_ud_in_the_year_and_prorates_the_target() -> None:
    rows = [lot(f"r{i}", D(2026, 4, 13) + (D(2026, 10, 1) - D(2026, 4, 13)) * i // 317) for i in range(318)]
    rows += [lot("old", D(2025, 11, 3)), lot("open", None)]
    rate = release_rate(rows, 2026, TODAY, annual_target=700)
    assert rate.released == 318
    assert (rate.coverage_start, rate.coverage_weeks) == (D(2026, 4, 13), 27)
    assert rate.prorata_target == Decimal(700 * 27) / Decimal(52)
    assert rate.pct_of_prorata == 87  # 318 / 363.46 rounded half up


def test_f20_ac01_a_year_without_releases_has_no_percentage() -> None:
    rate = release_rate([], 2026, TODAY, annual_target=700)
    assert (rate.released, rate.coverage_weeks, rate.prorata_target, rate.pct_of_prorata) == (
        0,
        0,
        Decimal(0),
        None,
    )


def test_f20_ac01_a_rejected_lot_is_not_a_release() -> None:
    rejected = ReleasedLot("x", D(2026, 5, 5), False, None, None)
    assert release_rate([rejected, lot("a", D(2026, 5, 6))], 2026, TODAY, 700).released == 1


# --- needs-by adherence (OQ-119, OQ-121, F20-AC-06) -----------------------------------------------


def test_f20_ac06_a_lot_released_on_or_before_its_need_by_is_on_time() -> None:
    rows = [
        lot("a", D(2026, 8, 10), need_by=D(2026, 8, 10)),  # same day: on time
        lot("b", D(2026, 8, 11), need_by=D(2026, 8, 10)),  # one day over: late
        lot("c", D(2026, 8, 1), need_by=D(2026, 9, 1)),
    ]
    result = needs_by_adherence(rows, [], 2026)
    assert (result.on_time, result.late, result.excluded, result.total) == (2, 1, 0, 3)
    assert result.pct == Decimal("66.7")


def test_f20_ac06_a_lot_with_no_need_by_is_excluded_and_counted() -> None:
    result = needs_by_adherence(
        [lot("a", D(2026, 8, 1), need_by=D(2026, 9, 1)), lot("b", D(2026, 8, 1))], [], 2026
    )
    assert (result.on_time, result.late, result.excluded) == (1, 0, 1)
    assert result.pct == Decimal("100.0")


def test_f20_ac06_no_counted_lots_gives_no_percentage() -> None:
    assert needs_by_adherence([lot("a", D(2026, 8, 1))], [], 2026).pct is None


def test_f20_ac06_a_release_after_its_adjusted_date_counts_as_exceeded() -> None:
    """The fixture of AC-06: the original need-by would be met, the adjusted (earlier) date is missed."""
    rows = [lot("a", D(2026, 8, 20), need_by=D(2026, 9, 30))]
    versions = [NeedByVersion("a", D(2026, 8, 15), D(2026, 8, 1))]  # set before the release
    assert needs_by_adherence(rows, versions, 2026).late == 1
    assert needs_by_adherence(rows, [], 2026).on_time == 1


def test_f20_oq121_the_latest_version_on_or_before_the_release_date_applies() -> None:
    rows = [lot("a", D(2026, 8, 20), need_by=D(2026, 8, 1))]
    versions = [
        NeedByVersion("a", D(2026, 8, 10), D(2026, 8, 5)),
        NeedByVersion("a", D(2026, 8, 25), D(2026, 8, 20)),  # created on the release day: counts
        NeedByVersion("a", D(2026, 8, 1), D(2026, 8, 21)),  # created after the release: ignored
    ]
    assert needs_by_adherence(rows, versions, 2026).on_time == 1


def test_f20_oq121_a_clear_falls_back_to_need_by_at_release() -> None:
    rows = [lot("a", D(2026, 8, 20), need_by=D(2026, 9, 1))]
    versions = [NeedByVersion("a", D(2026, 8, 1), D(2026, 7, 1)), NeedByVersion("a", None, D(2026, 7, 5))]
    assert needs_by_adherence(rows, versions, 2026).on_time == 1


def test_f20_oq121_an_override_can_give_a_need_by_to_a_lot_that_had_none() -> None:
    rows = [lot("a", D(2026, 8, 20))]
    versions = [NeedByVersion("a", D(2026, 8, 30), D(2026, 8, 1))]
    result = needs_by_adherence(rows, versions, 2026)
    assert (result.on_time, result.excluded) == (1, 0)


def test_f20_fr03_adherence_ignores_other_years_and_open_lots() -> None:
    rows = [lot("a", D(2025, 8, 20), need_by=D(2025, 9, 1)), lot("b", None, need_by=D(2026, 9, 1))]
    assert needs_by_adherence(rows, [], 2026).total == 0


def test_f20_fr03_adherence_by_week_splits_within_and_exceeded() -> None:
    rows = [
        lot("a", D(2026, 8, 3), need_by=D(2026, 8, 4)),  # week of 3 Aug: within
        lot("b", D(2026, 8, 7), need_by=D(2026, 8, 6)),  # week of 3 Aug: exceeded
        lot("c", D(2026, 8, 12), need_by=D(2026, 8, 12)),  # week of 10 Aug: within
        lot("d", D(2026, 8, 12)),  # no need-by: not in the chart
    ]
    assert adherence_by_week(rows, [], 2026) == [(D(2026, 8, 3), 1, 1), (D(2026, 8, 10), 1, 0)]


# --- expedite on-time (OQ-120) -----------------------------------------------------------------


def test_f20_oq120_expedite_on_time_uses_the_source_due_date() -> None:
    rows = [
        lot("a", D(2026, 8, 10), due=D(2026, 8, 10)),
        lot("b", D(2026, 8, 11), due=D(2026, 8, 10)),
        lot("c", D(2026, 8, 1), due=D(2026, 9, 1)),
        lot("d", D(2026, 8, 1)),  # not expedited
    ]
    result = expedite_on_time(rows, set(), 2026)
    assert (result.on_time, result.late, result.expedited, result.app_only) == (2, 1, 3, 0)
    assert result.pct == Decimal("66.7")


def test_f20_oq120_app_only_expedites_are_counted_but_not_in_the_ratio() -> None:
    rows = [lot("a", D(2026, 8, 10), due=D(2026, 8, 10)), lot("b", D(2026, 8, 1)), lot("open", None)]
    result = expedite_on_time(rows, {"a", "b", "open"}, 2026)
    assert (result.expedited, result.app_only) == (
        1,
        1,
    )  # "a" has source facts; "b" is app-only; open is not released
    assert result.pct == Decimal("100.0")


def test_f20_oq120_no_expedites_gives_no_percentage_and_other_years_are_ignored() -> None:
    result = expedite_on_time([lot("a", D(2025, 8, 10), due=D(2025, 8, 10))], set(), 2026)
    assert (result.expedited, result.pct) == (0, None)


# --- trend (OQ-126a) ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("last", "previous", "direction", "delta"),
    [
        ("84.0", "80.0", "up", "4.0"),
        ("69.0", "75.5", "down", "-6.5"),
        ("81.0", "80.0", "stable", "1.0"),
        ("80.0", "81.9", "stable", "-1.9"),
        ("82.0", "80.0", "up", "2.0"),  # exactly 2 pp is a change
        ("78.0", "80.0", "down", "-2.0"),
        (None, "80.0", "none", None),
        ("80.0", None, "none", None),
    ],
)
def test_f20_ac03_trend_is_the_difference_in_percentage_points(
    last: str | None, previous: str | None, direction: str, delta: str | None
) -> None:
    result = trend(Decimal(last) if last else None, Decimal(previous) if previous else None)
    assert result == Trend(direction, Decimal(delta) if delta else None)


# --- late items (OQ-123, F20-AC-05) ------------------------------------------------------------

STAGE_METRIC = {"sampling": "M3", "qc_testing": "M6"}
STATUS_REASONS = {"resource_constraint": "Resource constraint"}
CODE_LABELS = {"CAMPAIGN_PULLED_FORWARD": "Campaign pulled forward"}


def cand(key: str, remaining: int | None, *, late: bool = True, stage: str = "sampling", auto: str | None = None,
         material: str = "RM1", batch: str = "B1") -> LateCandidate:  # fmt: skip
    plan = PlanResult(expected_completion=None, days_remaining=remaining, late=late, late_reason_auto=auto)
    return LateCandidate(key, material, batch, "CMP-ALPHA", stage, plan)


def test_f20_ac05_late_items_are_the_late_rows_worst_first() -> None:
    candidates = [
        cand("a", -3, material="RM2"),
        cand("b", -12, material="RM3"),
        cand("c", 4, late=False),
        cand("d", -3, material="RM1"),  # ties: material, then batch
    ]
    items = late_items(candidates, {}, STAGE_METRIC, STATUS_REASONS, CODE_LABELS)
    assert [i.row_key for i in items] == ["b", "d", "a"]
    assert [i.days_over_sla for i in items] == [12, 3, 3]


def test_f20_oq123_metric_breached_is_the_stage_bound_metric_or_a_dash() -> None:
    items = late_items([cand("a", -1), cand("b", -1, stage="qa_release")], {}, STAGE_METRIC, {}, {})
    assert {i.row_key: i.metric_breached for i in items} == {"a": "M3", "b": None}


def test_f20_ac05_the_late_reason_is_the_latest_status_log_reason_label() -> None:
    log = {
        "a": [
            LogEntry("process_delay", 1),
            LogEntry("resource_constraint", 3),
            LogEntry(None, 4),  # a newer entry without a reason does not hide the older reason
        ]
    }
    [item] = late_items(
        [cand("a", -2)], log, STAGE_METRIC, {"process_delay": "Process delay", **STATUS_REASONS}, {}
    )
    assert item.late_reason == "Resource constraint"


def test_f20_oq123_the_auto_late_reason_is_the_fallback_then_a_dash() -> None:
    items = late_items(
        [cand("a", -2, auto="CAMPAIGN_PULLED_FORWARD"), cand("b", -2), cand("c", -2, auto="UNKNOWN_CODE")],
        {"b": [LogEntry(None, 1)]},
        STAGE_METRIC,
        STATUS_REASONS,
        CODE_LABELS,
    )
    reasons = {i.row_key: i.late_reason for i in items}
    assert reasons == {"a": "Campaign pulled forward", "b": None, "c": "UNKNOWN_CODE"}


def test_f20_oq123_a_row_with_no_days_remaining_is_not_listed() -> None:
    assert late_items([cand("a", None)], {}, STAGE_METRIC, {}, {}) == []


def test_f20_oq123_the_stage_metric_map_comes_from_the_profile(profile: SiteProfile) -> None:
    assert stage_metric_map(profile) == {
        "receipt": "M1", "call_off": "M2", "sampling": "M3", "qc_ship": "M4", "qc_testing": "M6", "qa_release": "M7",
    }  # fmt: skip
