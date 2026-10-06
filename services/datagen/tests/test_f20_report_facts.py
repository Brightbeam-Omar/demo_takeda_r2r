"""F20-FR-07: adherence and expedite history, on new streams only (OQ-122)."""

import pytest
from datagen import planner
from datagen.events import plan_events
from datagen.model import ACCEPT_CODES, Plan
from datagen.params import Params
from datagen.planner import build_plan
from datagen.report_facts import adherence, released_lots
from r2r_core.profile import SiteProfile


def test_f20_fr07_adherence_lands_between_85_and_89_9_percent(plan: Plan) -> None:
    on_time, late, none = adherence(plan)
    assert none == 0  # every released lot has a need-by
    share = 100 * on_time / (on_time + late)
    assert 85.0 <= share < 90.0, share


def test_f20_fr07_every_released_lot_is_counted(plan: Plan) -> None:
    assert sum(adherence(plan)) == len(released_lots(plan)) == 321  # the F05 released rows


def test_f20_oq122_exactly_four_expedites_three_on_time_and_one_missed(plan: Plan) -> None:
    assert len(plan.expedites) == 4
    batches = {(b.matnr, b.charg): b for b in plan.batches}
    outcomes = []
    for expedite in plan.expedites:
        batch = batches[expedite.matnr, expedite.charg]
        assert (
            len(batch.lots) == 1 and batch.story_id is None
        )  # the source fact applies to every lot of the batch
        lot = batch.lots[0]
        assert lot.ud_code in ACCEPT_CODES and lot.ud_date is not None
        assert lot.start <= expedite.requested_on <= expedite.due_date
        outcomes.append(lot.ud_date <= expedite.due_date)
    assert sorted(outcomes) == [False, True, True, True]


def test_f20_fr07_events_include_the_expedite_requests(plan: Plan) -> None:
    requests = [e for e in plan_events(plan) if e.kind == "expedite_requested"]
    assert len(requests) == 4
    assert set(requests[0].body) == {"matnr", "charg", "requested_on", "due_date"}


def test_f20_fr07_nothing_planned_before_moves(
    profile: SiteProfile, params: Params, plan: Plan, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The F05 counts, every batch and lot, and every earlier demand line are as without the new plans."""
    monkeypatch.setattr(planner, "plan_report_facts", lambda *_: None)
    before = build_plan(profile, params, 4242)
    assert plan.batches == before.batches
    assert plan.deviations == before.deviations and plan.po_lines == before.po_lines
    assert plan.demands[: len(before.demands)] == before.demands
    assert len(plan.demands) > len(before.demands) and not before.expedites
    added = plan.demands[len(before.demands) :]  # closed lines never touch an open lot's need-by
    assert all(d.closed_on is not None for d in added)
    assert (len(plan.batches), sum(len(b.lots) for b in plan.batches)) == (
        len(before.batches),
        sum(len(b.lots) for b in before.batches),
    )
