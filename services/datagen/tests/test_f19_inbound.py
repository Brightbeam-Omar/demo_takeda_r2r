"""F19-FR-02: inbound sub-checks and resolved checks in the generated history [F19-AC-02, F19-AC-07]."""

import pytest
from datagen.events import plan_events
from datagen.executor import Databases
from datagen.generate import generate
from datagen.inbound_items import ITEM_LIST
from datagen.model import Plan, derive_stage
from datagen.params import Params
from datagen.planner import build_plan
from datagen.stats import compute_stats
from r2r_core.profile import SiteProfile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

LABELS = [label for _, label, _ in ITEM_LIST]


def checked(plan: Plan) -> list:  # type: ignore[type-arg]
    return [lot for _, lot in plan.lots() if lot.check != "none" and not lot.reversed_same_day]


def test_f19_fr02_about_eight_percent_of_passed_checks_become_resolved(plan: Plan) -> None:
    resolved = sum(1 for _, lot in plan.lots() if lot.check == "resolved")
    passed = sum(1 for _, lot in plan.lots() if lot.check == "passed")
    assert resolved >= 3
    assert 0.04 <= resolved / (resolved + passed) <= 0.13


def test_f19_fr02_story_batches_are_never_resolved_and_draw_nothing(
    profile: SiteProfile, params: Params, plan: Plan
) -> None:
    assert all(lot.check != "resolved" for _, lot in plan.lots() if lot.story_id)
    other = build_plan(profile, params, 7)
    assert [lot.check_items for _, lot in plan.lots() if lot.story_id] == [
        lot.check_items for _, lot in other.lots() if lot.story_id
    ]


def test_f19_fr02_every_check_has_five_to_nine_items_from_the_fixed_list_in_order(plan: Plan) -> None:
    for lot in checked(plan):
        assert 5 <= len(lot.check_items) <= 9
        assert [label for _, label, _ in lot.check_items] == LABELS[: len(lot.check_items)]


def test_f19_ac02_failed_and_resolved_checks_have_a_fail_and_passed_checks_have_none(plan: Plan) -> None:
    for lot in checked(plan):
        outcomes = [outcome for _, _, outcome in lot.check_items]
        if lot.check in ("failed", "resolved"):
            assert "FAIL" in outcomes, lot.ref
            assert "PENDING" not in outcomes
        elif lot.check == "passed":
            assert set(outcomes) <= {"PASS", "APRV", "NO", "COMP", "DCPS"}, lot.ref
        else:  # open
            assert outcomes[-1] == "PENDING", lot.ref


def test_f19_fr02_lots_without_a_check_have_no_items(plan: Plan) -> None:
    assert all(not lot.check_items for _, lot in plan.lots() if lot.check == "none" or lot.reversed_same_day)


def test_f19_ac07_resolved_checks_change_no_intended_stage_and_no_count(
    plan: Plan, profile: SiteProfile
) -> None:
    assert all(derive_stage(batch, lot) == lot.stage for batch, lot in plan.lots())
    stats = compute_stats(plan, profile)
    assert (stats.lots, stats.batches, stats.open_rows, stats.released_rows) == (803, 650, 482, 321)
    last = {metric: (weeks[-1].on_time, weeks[-1].completed) for metric, weeks in stats.weekly.items()}
    assert last == {"M3": (17, 18), "M6": (36, 43), "M7": (9, 13)}


def test_f19_fr02_events_carry_the_items_and_the_resolved_status(plan: Plan) -> None:
    events = plan_events(plan)
    completions = [e for e in events if e.kind == "inbound_check"]
    assert {e.body["status"] for e in completions} >= {"passed", "failed", "resolved"}
    assert all(e.body["items"] for e in completions)
    receipts = [e for e in events if e.kind == "goods_receipt" and "items" in e.body]
    assert receipts  # open checks carry their (partly pending) items from the receipt


@pytest.mark.integration
def test_f19_fr02_the_database_holds_the_items(
    source_databases: Databases, profile: SiteProfile, params: Params
) -> None:
    from erp_sim.models import Zinbchk, ZinbchkItem
    from r2r_core.db import make_engine

    generated = generate(profile, params, 4242, source_databases)
    engine = make_engine(source_databases.erp)
    with Session(engine) as session:
        statuses = dict(session.execute(select(Zinbchk.status, func.count()).group_by(Zinbchk.status)).all())
        with_items = session.scalar(select(func.count(func.distinct(ZinbchkItem.prueflos)))) or 0
        failed_without_fail = session.scalar(
            select(func.count())
            .select_from(Zinbchk)
            .where(
                Zinbchk.status.in_(["failed", "resolved"]),
                ~select(ZinbchkItem.prueflos)
                .where(ZinbchkItem.prueflos == Zinbchk.prueflos, ZinbchkItem.outcome == "FAIL")
                .exists(),
            )
        )
    engine.dispose()
    assert statuses["resolved"] >= 3
    assert with_items == sum(statuses.values()) - sum(
        1 for _, lot in generated.plan.lots() if lot.reversed_same_day
    )
    assert failed_without_fail == 0


def test_f19_ac07_week_41_percentages_are_94_4_83_7_69_2_and_the_new_draws_are_deterministic(
    plan: Plan, profile: SiteProfile, params: Params
) -> None:
    last = {m: weeks[-1] for m, weeks in compute_stats(plan, profile).weekly.items()}
    assert {m: round(100 * w.on_time / w.completed, 1) for m, w in last.items()} == {
        "M3": 94.4,
        "M6": 83.7,
        "M7": 69.2,
    }
    again = build_plan(profile, params, 4242)
    assert [lot.check_items for _, lot in again.lots()] == [lot.check_items for _, lot in plan.lots()]
    assert [lot.check for _, lot in again.lots()] == [lot.check for _, lot in plan.lots()]
    assert again.change_controls == plan.change_controls
    assert [(d.causal_factor, d.investigation_summary) for d in again.deviations] == [
        (d.causal_factor, d.investigation_summary) for d in plan.deviations
    ]
