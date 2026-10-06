"""T4 [TDD]: realism quirks (F05-FR-05, F05-AC-03)."""

from collections import Counter
from datetime import timedelta

import pytest
from datagen.model import Plan, derive_stage
from datagen.params import Params
from datagen.quirks import QUIRKS, quirk_counts
from r2r_core.profile import SiteProfile


def test_f05_ac03_every_quirk_occurs_at_least_three_times(plan: Plan, profile: SiteProfile) -> None:
    counts = quirk_counts(plan, profile)
    assert set(counts) == set(QUIRKS)
    assert {name: n for name, n in counts.items() if n < 3} == {}


def test_f05_fr05_the_configured_numbers_are_created(
    plan: Plan, profile: SiteProfile, params: Params
) -> None:
    counts = quirk_counts(plan, profile)
    assert counts["failed_inbound_check"] >= params.quirks.failed_inbound_checks
    assert counts["rejected_ud"] >= params.quirks.rejected_uds
    assert counts["on_hold_batch"] >= params.quirks.on_hold_batches
    assert counts["erp_blocked_stock"] >= params.quirks.erp_blocked_batches
    assert counts["open_deviation_in_qa_release"] >= params.deviations.open_on_qa_release


def test_f05_fr05_the_quirks_leave_the_intended_stages_intact(plan: Plan) -> None:
    wrong = [lot.ref for batch, lot in plan.lots() if derive_stage(batch, lot) != lot.stage]
    assert wrong == []


def test_f05_fr05_a_rejected_ud_lot_waits_in_qa_release(plan: Plan) -> None:
    rejected = [(b, lot) for b, lot in plan.lots() if lot.ud_code == "R"]
    assert rejected
    for _, lot in rejected:
        assert lot.stage == "qa_release"
        assert lot.latest is not None and lot.ud_date is not None and lot.latest.closed_on is not None
        assert lot.ud_date > lot.latest.closed_on


def test_f05_fr05_failed_checks_sit_in_receipt(plan: Plan) -> None:
    failed = [lot for _, lot in plan.lots() if lot.check == "failed"]
    assert failed
    assert {lot.stage for lot in failed} == {"receipt"}
    assert all(lot.check_done is not None and lot.check_done > lot.start for lot in failed)


def test_f05_fr02_deviation_volume_and_open_share(plan: Plan, params: Params) -> None:
    total = len(plan.deviations)
    open_count = sum(1 for d in plan.deviations if d.closed_on is None)
    assert abs(total - params.volumes.deviations) <= 0.1 * params.volumes.deviations
    assert abs(open_count / total - params.volumes.deviation_open_share) <= 0.05
    severities = Counter(d.severity for d in plan.deviations)
    assert set(severities) == {"minor", "moderate", "major"}  # F19-FR-03
    assert severities["minor"] > severities["moderate"] > severities["major"]


def test_f05_fr01_deviations_link_to_real_batches_and_make_sense(plan: Plan) -> None:
    first_day = {(b.matnr, b.charg): b.first_day for b in plan.batches}
    last_day = plan.calendar.last_day
    for deviation in plan.deviations:
        assert deviation.links and len(deviation.links) <= 2
        assert all(link in first_day for link in deviation.links)
        assert deviation.opened_on >= max(first_day[link] for link in deviation.links)
        assert deviation.opened_on <= last_day
        if deviation.closed_on is not None:
            assert deviation.opened_on < deviation.closed_on <= last_day


def test_f05_fr01_open_deviations_sit_on_batches_still_in_flight(plan: Plan) -> None:
    lots_of = {(b.matnr, b.charg): b.lots for b in plan.batches}
    for deviation in plan.deviations:
        if deviation.closed_on is None:
            assert any(lot.stage not in ("released",) for link in deviation.links for lot in lots_of[link]), (
                deviation
            )


def test_f05_fr01_no_business_event_is_dated_after_the_last_business_day(plan: Plan) -> None:
    from datagen.events import plan_events

    last = plan.calendar.last_day
    late = [e for e in plan_events(plan) if e.at is None and e.day > last]
    assert late == []
    assert plan.calendar.today - last <= timedelta(days=3)


@pytest.mark.parametrize("tag", ["lims_retest", "lims_rejected"])
def test_f05_realism_lims_retests_exist(plan: Plan, tag: str) -> None:
    assert sum(1 for _, lot in plan.lots() if tag in lot.tags) >= 3


def test_f05_oq039_the_air_gap_count_is_three_to_five_and_is_exactly_the_withheld_transfers(
    plan: Plan, profile: SiteProfile
) -> None:
    from datetime import UTC, datetime, time

    assert 3 <= quirk_counts(plan, profile)["air_gap"] <= 5
    now = profile.demo.start_datetime
    missing = []
    for batch, lot in plan.lots():
        sample = lot.latest
        if sample is None or sample.outcome != "approved" or sample.closed_on is None:
            continue
        approved = sample.approved_at or datetime.combine(sample.closed_on, time(6), tzinfo=UTC)
        if (
            lot.ud_code is None
            and lot.results_recorded is None
            and (now - approved).total_seconds() >= 24 * 3600
        ):
            missing.append(batch.charg)
        if lot.results_recorded is not None:
            delay = (lot.results_recorded - approved).total_seconds() / 3600
            assert 1 <= delay <= 7, (batch.charg, delay)
    air_gaps = [b.charg for b, lot in plan.lots() if "air_gap" in lot.tags]
    assert sorted(missing) == sorted(air_gaps)
    assert "B5003" in air_gaps


def test_f10_review_every_air_gap_is_between_24_and_96_hours_old_at_demo_start(
    plan: Plan, profile: SiteProfile
) -> None:
    from datetime import UTC, datetime, time

    now = profile.demo.start_datetime
    ages = {}
    for batch, lot in plan.lots():
        sample = lot.latest
        if "air_gap" in lot.tags and sample is not None and sample.closed_on is not None:
            approved = sample.approved_at or datetime.combine(sample.closed_on, time(6), tzinfo=UTC)
            ages[batch.charg] = (now - approved).total_seconds() / 3600
    assert len(ages) >= 3 and all(24 <= hours <= 96 for hours in ages.values()), ages
    assert round(ages["B5003"]) == 30
    # The withheld lots are approved at different times, so the air-gap alert shows a spread of ages.
    assert len({round(hours) for hours in ages.values()}) == len(ages), ages
    assert sorted(round(hours) for hours in ages.values()) == [30, 62, 70, 90]
