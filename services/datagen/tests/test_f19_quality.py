"""F19-FR-03: deviation details, severity vocabulary and change controls in the generated history."""

from collections import Counter

import pytest
from datagen.events import plan_events
from datagen.executor import Databases
from datagen.generate import generate
from datagen.model import Plan
from datagen.params import Params
from datagen.planner import build_plan
from r2r_core.profile import SiteProfile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

STORY_BATCHES = {"B1042", "B2077", "B3150", "B4410", "B5003"}


def test_f19_fr03_severity_mix_is_about_60_30_10_and_b3150_stays_an_open_major(plan: Plan) -> None:
    ordinary = [d for d in plan.deviations if not d.story_id]
    mix = Counter(d.severity for d in ordinary)
    assert set(mix) == {"minor", "moderate", "major"}
    total = sum(mix.values())
    assert 0.48 <= mix["minor"] / total <= 0.72
    assert 0.18 <= mix["moderate"] / total <= 0.42
    assert 0.03 <= mix["major"] / total <= 0.20
    [b3150] = [d for d in plan.deviations if d.story_id == "B3150"]
    assert (b3150.severity, b3150.closed_on, b3150.links) == ("major", None, [("RM10045", "B3150")])


def test_f19_fr03_every_deviation_has_a_causal_factor_and_closed_ones_an_investigation_summary(
    plan: Plan,
) -> None:
    assert all(d.causal_factor for d in plan.deviations)
    assert all(d.investigation_summary for d in plan.deviations if d.closed_on is not None and not d.story_id)
    open_major = [
        d for d in plan.deviations if d.closed_on is None and d.severity == "major" and not d.story_id
    ]
    with_summary = sum(1 for d in open_major if d.investigation_summary)
    assert open_major and 0 < with_summary < len(open_major) + 1


def test_f19_fr03_story_deviations_draw_nothing(profile: SiteProfile, params: Params, plan: Plan) -> None:
    other = build_plan(profile, params, 7)
    assert [d for d in other.deviations if d.story_id] == [d for d in plan.deviations if d.story_id]


def test_f19_fr03_about_forty_change_controls_link_about_15_percent_of_the_batches(plan: Plan) -> None:
    assert 35 <= len(plan.change_controls) <= 45
    linked = {link for cc in plan.change_controls for link in cc.links}
    assert 0.12 <= len(linked) / len(plan.batches) <= 0.18
    assert all(cc.links for cc in plan.change_controls)
    assert not {charg for _, charg in linked} & STORY_BATCHES


def test_f19_fr03_at_least_one_change_control_sits_on_a_batch_with_no_deviation(plan: Plan) -> None:
    with_deviation = {link for d in plan.deviations for link in d.links}
    linked = {link for cc in plan.change_controls for link in cc.links}
    assert linked - with_deviation


def test_f19_fr03_change_controls_have_every_status_and_sensible_dates(plan: Plan) -> None:
    statuses = {cc.status for cc in plan.change_controls}
    assert statuses == {"open", "approved", "closed", "cancelled"}
    first_day = {(b.matnr, b.charg): b.first_day for b in plan.batches}
    last = plan.calendar.last_day
    for cc in plan.change_controls:
        assert cc.opened_on <= last
        assert (cc.effective_on is not None) == (cc.status in ("approved", "closed")), cc
        if cc.status != "open":
            assert cc.opened_on < cc.status_on <= last
        assert all(link in first_day for link in cc.links)


def test_f19_fr03_events_open_each_change_control_and_move_it_to_its_status(plan: Plan) -> None:
    events = plan_events(plan)
    opened = [e for e in events if e.kind == "change_control_opened"]
    moved = [e for e in events if e.kind == "change_control_status"]
    assert len(opened) == len(plan.change_controls)
    assert len(moved) == sum(1 for cc in plan.change_controls if cc.status != "open")
    assert all(e.system == "qms" for e in opened + moved)
    assert all(e.body["status"] == "open" for e in opened)


@pytest.mark.integration
def test_f19_fr03_the_database_holds_change_controls_and_the_new_severities(
    source_databases: Databases, profile: SiteProfile, params: Params
) -> None:
    from qms_sim.models import ChangeControl, ChangeControlLink, Deviation
    from r2r_core.db import make_engine

    generated = generate(profile, params, 4242, source_databases)
    engine = make_engine(source_databases.qms)
    with Session(engine) as session:
        severities = dict(
            session.execute(select(Deviation.severity, func.count()).group_by(Deviation.severity)).all()
        )
        statuses = {s for (s,) in session.execute(select(ChangeControl.status).distinct())}
        links = session.scalar(select(func.count()).select_from(ChangeControlLink)) or 0
        summaries = (
            session.scalar(
                select(func.count())
                .select_from(Deviation)
                .where(Deviation.investigation_summary.is_not(None))
            )
            or 0
        )
    engine.dispose()
    assert set(severities) == {"minor", "moderate", "major"}
    assert statuses == {"open", "approved", "closed", "cancelled"}
    assert links == sum(len(cc.links) for cc in generated.plan.change_controls)
    assert summaries > 0
