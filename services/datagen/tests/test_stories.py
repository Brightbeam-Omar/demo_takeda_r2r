"""T5 [TDD]: the five story batches (F05-FR-06, F05-AC-04)."""

from datetime import UTC, date, timedelta

import pytest
from datagen.events import plan_events
from datagen.model import BatchPlan, LotPlan, Plan, current_stage_entry
from datagen.params import Params
from datagen.planner import build_plan, facts_of
from r2r_core.airgap import air_gap
from r2r_core.profile import SiteProfile
from r2r_core.sla import plan as plan_dates

STORY_IDS = ["B1042", "B2077", "B3150", "B4410", "B5003"]


def story(plan: Plan, charg: str) -> BatchPlan:
    return next(b for b in plan.batches if b.charg == charg)


def open_lot(batch: BatchPlan) -> LotPlan:
    return batch.lots[-1]


def test_f05_ac04_all_five_story_batches_exist_with_their_fixed_materials(plan: Plan) -> None:
    found = {b.charg: (b.matnr, b.lifnr, b.story_id) for b in plan.batches if b.story_id}
    assert found == {
        "B1042": ("RM10023", "SUP003", "B1042"),
        "B2077": ("RM10031", "SUP007", "B2077"),
        "B3150": ("RM10045", "SUP011", "B3150"),
        "B4410": ("RM10052", "SUP021", "B4410"),
        "B5003": ("RM10067", "SUP030", "B5003"),
    }
    assert all(lot.story_id == b.story_id for b in plan.batches if b.story_id for lot in b.lots)


def test_f05_ac04_other_batches_never_take_a_story_number_or_material(plan: Plan) -> None:
    story_materials = {"RM10023", "RM10031", "RM10045", "RM10052", "RM10067"}
    for batch in plan.batches:
        if not batch.story_id:
            assert batch.charg not in STORY_IDS
            assert batch.matnr not in story_materials


def test_f05_fr06_the_stories_are_the_same_whatever_the_seed(
    profile: SiteProfile, params: Params, plan: Plan
) -> None:
    other = build_plan(profile, params, 7)
    assert [b for b in other.batches if b.story_id] == [b for b in plan.batches if b.story_id]
    assert [d for d in other.deviations if d.story_id] == [d for d in plan.deviations if d.story_id]


def test_f05_ac04_b1042_is_in_qc_testing_with_all_tests_done_and_lims_not_approved(plan: Plan) -> None:
    batch = story(plan, "B1042")
    lot = open_lot(batch)
    assert (lot.lot_type, lot.stage, batch.received_location_type) == ("01", "qc_testing", "onsite")
    sample = lot.latest
    assert sample is not None and not sample.offsite
    assert sample.outcome == "open" and sample.started is not None
    assert len(sample.results) == 5 and {t.status for t in sample.results} == {"pass"}
    assert lot.ud_code is None


def test_f05_ac04_b2077_is_in_sampling_since_8_oct_and_expected_on_15_oct_with_no_compression(
    plan: Plan, profile: SiteProfile
) -> None:
    batch = story(plan, "B2077")
    lot = open_lot(batch)
    assert (lot.lot_type, lot.stage, batch.received_location_type, lot.samples) == (
        "01",
        "sampling",
        "onsite",
        [],
    )
    assert current_stage_entry(batch, lot) == date(2026, 10, 8)
    assert plan.need_by["RM10031"] == date(2026, 12, 3)
    assert any(d.matnr == "RM10031" and d.campaign == "CMP-BRAVO" for d in plan.demands)
    result = plan_dates(facts_of(batch, lot, plan.need_by["RM10031"]), profile, plan.calendar.today)
    assert (result.expected_completion, str(result.rag), result.compressed) == (
        date(2026, 10, 15),
        "green",
        False,
    )
    assert any(p.material == "RM10031" and p.supplier == "SUP007" for p in profile.full_spec_pairs)


def test_f05_ac04_b3150_waits_in_qa_release_with_an_open_major_deviation(plan: Plan) -> None:
    batch = story(plan, "B3150")
    lot = open_lot(batch)
    assert lot.stage == "qa_release" and lot.ud_code is None
    assert (batch.holds, batch.blocks) == ([], [])
    deviation = next(d for d in plan.deviations if d.story_id == "B3150")
    assert (deviation.severity, deviation.closed_on, deviation.links) == (
        "major",
        None,
        [("RM10045", "B3150")],
    )
    assert deviation.opened_on >= lot.start


def test_f05_ac04_b4410_has_an_initial_lot_three_released_re_evals_and_an_open_one_in_sampling(
    plan: Plan,
) -> None:
    batch = story(plan, "B4410")
    assert [lot.lot_type for lot in batch.lots] == ["01", "09", "09", "09", "09"]
    assert [lot.stage for lot in batch.lots] == ["released"] * 4 + ["sampling"]
    current = open_lot(batch)
    starts = [lot.start for lot in batch.lots[1:]]
    assert [(current.start - start).days for start in starts] == [168, 112, 56, 0]
    assert all(lot.ud_code in ("A", "A4") for lot in batch.lots[:-1])
    assert batch.received_location_type == "onsite"


def test_f05_ac04_b5003_was_approved_30_hours_before_demo_start_with_no_ud(
    plan: Plan, profile: SiteProfile
) -> None:
    batch = story(plan, "B5003")
    lot = open_lot(batch)
    sample = lot.latest
    assert lot.stage == "qa_release" and lot.ud_code is None and sample is not None
    expected = profile.demo.start_datetime.astimezone(UTC) - timedelta(hours=30)
    assert sample.approved_at == expected
    flagged, hours = air_gap("approved", None, sample.approved_at, profile.demo.start_datetime, 24)
    assert (flagged, hours) == (True, 30)
    approval = next(e for e in plan_events(plan) if e.kind == "approved" and e.at == expected)
    assert approval.day == expected.astimezone(profile.site.tz).date()


@pytest.mark.parametrize(
    ("charg", "rag"),
    [("B1042", "amber"), ("B2077", "green"), ("B3150", "amber"), ("B4410", "green"), ("B5003", "green")],
)
def test_f05_fr06_story_rag_at_demo_start(plan: Plan, profile: SiteProfile, charg: str, rag: str) -> None:
    batch = story(plan, charg)
    lot = open_lot(batch)
    result = plan_dates(facts_of(batch, lot, plan.need_by[batch.matnr]), profile, plan.calendar.today)
    assert str(result.rag) == rag


def test_f05_fr06_story_dates_are_offsets_from_demo_start(plan: Plan) -> None:
    today = plan.calendar.today
    assert story(plan, "B2077").lots[0].check_done == today - timedelta(days=4)
    assert plan.need_by["RM10031"] == today + timedelta(days=52)
