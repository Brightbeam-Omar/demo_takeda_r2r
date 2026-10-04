"""T6: exceptions-first ordering and the period filter [F03-FR-06, F03-FR-07, F03-AC-10, F03-AC-11].

03-domain-model sections 5.5 and 5.6, with the OQ-021 decisions (Flags dataclass, groups 0 to 4,
period None meaning All dates).
"""

from collections.abc import Callable
from datetime import date

from r2r_core.domain import RowFacts
from r2r_core.profile import SiteProfile
from r2r_core.sla import Flags, PlanResult, exception_sort_key, in_period, plan

FactsFactory = Callable[..., RowFacts]
TODAY = date(2026, 10, 12)


def d(text: str) -> date:
    return date.fromisoformat(text)


def result(expected: str | None, late: bool = False) -> PlanResult:
    return PlanResult(expected_completion=None if expected is None else d(expected), late=late)


def ordered(entries: dict[str, tuple[PlanResult, Flags]], facts: FactsFactory) -> list[str]:
    """Row keys in sort order. The dict key is used as the row_key."""
    keyed = {
        name: exception_sort_key(facts(row_key=name), plan_result, flags)
        for name, (plan_result, flags) in entries.items()
    }
    return sorted(keyed, key=lambda name: keyed[name])


# --- exceptions-first ordering -----------------------------------------------------------------


def test_f03_ac10_exceptions_sort_in_the_documented_order(facts: FactsFactory) -> None:
    """F03-AC-10: late (most overdue first) < ud_rejected < on_hold < air_gap < rest by expected, NULL last."""
    entries = {
        "RM1|B01|1": (result("2026-12-01"), Flags()),  # rest, later
        "RM1|B02|1": (result("2026-10-20"), Flags()),  # rest, sooner
        "RM1|B03|1": (result(None), Flags()),  # rest, no expected date
        "RM1|B04|1": (result("2026-10-30"), Flags(air_gap=True)),
        "RM1|B05|1": (result("2026-10-25"), Flags(on_hold=True)),
        "RM1|B06|1": (result("2026-10-28"), Flags(ud_rejected=True)),
        "RM1|B07|1": (result("2026-10-09", late=True), Flags()),  # 3 days overdue
        "RM1|B08|1": (result("2026-10-01", late=True), Flags()),  # 11 days overdue, so first
    }
    assert ordered(entries, facts) == [
        "RM1|B08|1", "RM1|B07|1", "RM1|B06|1", "RM1|B05|1", "RM1|B04|1", "RM1|B02|1", "RM1|B01|1", "RM1|B03|1",
    ]  # fmt: skip


def test_f03_ac10_a_late_row_beats_a_rejected_row_even_if_the_rejected_one_is_sooner(
    facts: FactsFactory,
) -> None:
    entries = {
        "RM1|B01|1": (result("2026-10-01"), Flags(ud_rejected=True)),
        "RM1|B02|1": (result("2026-10-10", late=True), Flags()),
    }
    assert ordered(entries, facts) == ["RM1|B02|1", "RM1|B01|1"]


def test_f03_ac10_a_row_with_several_flags_goes_in_the_lowest_numbered_group(facts: FactsFactory) -> None:
    late_and_rejected = exception_sort_key(facts(), result("2026-10-10", late=True), Flags(ud_rejected=True))
    rejected_and_hold = exception_sort_key(
        facts(), result("2026-10-10"), Flags(ud_rejected=True, on_hold=True)
    )
    hold_and_air_gap = exception_sort_key(facts(), result("2026-10-10"), Flags(on_hold=True, air_gap=True))
    assert late_and_rejected[0] == 0
    assert rejected_and_hold[0] == 1
    assert hold_and_air_gap[0] == 2
    assert exception_sort_key(facts(), result("2026-10-10"), Flags(air_gap=True))[0] == 3
    assert exception_sort_key(facts(), result("2026-10-10"), Flags())[0] == 4


def test_f03_ac10_rows_without_an_expected_date_sort_last_within_their_group(facts: FactsFactory) -> None:
    entries = {
        "RM1|B01|1": (result(None), Flags(on_hold=True)),
        "RM1|B02|1": (result("2027-06-01"), Flags(on_hold=True)),
        "RM1|B03|1": (result(None), Flags(air_gap=True)),
    }
    assert ordered(entries, facts) == ["RM1|B02|1", "RM1|B01|1", "RM1|B03|1"]


def test_f03_ac10_ties_break_on_material_then_batch(facts: FactsFactory) -> None:
    same = result("2026-11-01")
    entries = {
        "RM10002|B1|1": (same, Flags()),
        "RM10001|B9|1": (same, Flags()),
        "RM10001|B2|7": (same, Flags()),
    }
    assert ordered(entries, facts) == ["RM10001|B2|7", "RM10001|B9|1", "RM10002|B1|1"]


def test_f03_ac10_works_on_real_plan_output(profile: SiteProfile, facts: FactsFactory) -> None:
    overdue = plan(facts(row_key="RM1|B1|1", current_stage_entry_date=d("2026-09-01")), profile, TODAY)
    fresh = plan(facts(row_key="RM1|B2|1", current_stage_entry_date=d("2026-10-10")), profile, TODAY)
    key_overdue = exception_sort_key(facts(row_key="RM1|B1|1"), overdue, Flags())
    key_fresh = exception_sort_key(facts(row_key="RM1|B2|1"), fresh, Flags())
    assert overdue.late and not fresh.late
    assert key_overdue < key_fresh


# --- period filter -----------------------------------------------------------------------------

THIS_WEEK = (d("2026-10-12"), d("2026-10-18"))


def test_f03_ac11_an_overdue_row_is_in_the_current_window() -> None:
    """F03-AC-11: overdue rows roll into every current window."""
    assert in_period(result("2026-10-05", late=True), stage_terminal=False, period=THIS_WEEK) is True


def test_f03_ac11_a_row_expected_next_month_is_not() -> None:
    assert in_period(result("2026-11-10"), stage_terminal=False, period=THIS_WEEK) is False


def test_f03_ac11_terminal_rows_are_never_in_a_period() -> None:
    assert in_period(result("2026-10-14"), stage_terminal=True, period=THIS_WEEK) is False
    assert in_period(result(None), stage_terminal=True, period=THIS_WEEK) is False


def test_f03_ac11_window_end_is_inclusive_and_the_start_does_not_exclude() -> None:
    assert in_period(result("2026-10-18"), stage_terminal=False, period=THIS_WEEK) is True
    assert in_period(result("2026-10-19"), stage_terminal=False, period=THIS_WEEK) is False
    assert in_period(result("2025-01-01"), stage_terminal=False, period=THIS_WEEK) is True


def test_f03_oq021_all_dates_includes_every_row_even_terminal_and_undated() -> None:
    assert in_period(result("2030-01-01"), stage_terminal=False, period=None) is True
    assert in_period(result(None), stage_terminal=False, period=None) is True
    assert in_period(result(None), stage_terminal=True, period=None) is True


def test_f03_oq021_a_row_with_no_expected_date_is_excluded_from_a_real_period() -> None:
    assert in_period(result(None), stage_terminal=False, period=THIS_WEEK) is False
