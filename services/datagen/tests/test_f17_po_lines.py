"""F17 T3 [TDD]: purchase-order lines in the generated history [F17-FR-02, F17-AC-06]."""

from datetime import timedelta

import pytest
from datagen.events import plan_events
from datagen.executor import Databases
from datagen.generate import generate
from datagen.model import Plan
from datagen.params import Params
from datagen.stats import compute_stats
from erp_sim.models import Ekpo
from r2r_core.profile import SiteProfile
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def test_f17_fr02_every_batch_has_a_po_line_created_two_to_eight_weeks_before_its_receipt(plan: Plan) -> None:
    lines = {line.ref: line for line in plan.po_lines}
    for batch in plan.batches:
        assert batch.po_ref in lines, batch.charg
        line = lines[batch.po_ref]
        lead = (batch.first_day - line.created_on).days
        assert 12 <= lead <= 58, (batch.charg, lead)  # 14-56 days, moved back to a weekday
        assert (line.matnr, line.lifnr, line.lgort) == (batch.matnr, batch.lifnr, batch.lgort)
        assert line.created_on.weekday() < 5


def test_f17_fr02_the_goods_receipt_closes_its_line_and_the_reversal_reopens_it(plan: Plan) -> None:
    events = plan_events(plan)
    receipts = [e for e in events if e.kind == "goods_receipt"]
    assert all(e.body["ebeln"].startswith("@po:") and e.body["ebelp"] == "00010" for e in receipts)
    created = {e.capture for e in events if e.kind == "po_line_created"}
    assert {e.body["ebeln"] for e in receipts} <= created
    first = {e.capture: i for i, e in enumerate(events) if e.kind == "po_line_created"}
    for index, event in enumerate(events):
        if event.kind == "goods_receipt":
            assert first[event.body["ebeln"]] < index


def test_f17_fr02_between_60_and_90_lines_are_open_at_demo_start_and_about_a_tenth_overdue(
    plan: Plan,
) -> None:
    today = plan.calendar.today
    reopened = [b for b in plan.batches if any(lot.reversed_same_day for lot in b.lots)]
    future = [line for line in plan.po_lines if line.open_at_start]
    assert 60 <= len(future) + len(reopened) <= 90
    overdue = [line for line in future if line.scheduled < today]
    share = (len(overdue) + len(reopened)) / (len(future) + len(reopened))
    assert 0.07 <= share <= 0.35  # about 10%; the reopened lines of pending rows are always overdue
    assert all(line.scheduled <= today + timedelta(days=56) for line in future)
    assert all(line.created_on <= plan.calendar.last_day for line in future)


def test_f17_ac06_the_f05_counts_and_the_week_41_percentages_do_not_move(
    plan: Plan, profile: SiteProfile
) -> None:
    stats = compute_stats(plan, profile)
    assert (stats.lots, stats.batches, stats.open_rows, stats.released_rows) == (803, 650, 482, 321)
    last = {metric: (weeks[-1].on_time, weeks[-1].completed) for metric, weeks in stats.weekly.items()}
    assert last == {"M3": (17, 18), "M6": (36, 43), "M7": (9, 13)}  # 94.4 %, 83.7 %, 69.2 %


@pytest.mark.integration
def test_f17_ac06_the_database_holds_the_lines_and_the_f05_counts_do_not_move(
    source_databases: Databases, profile: SiteProfile, params: Params
) -> None:
    from r2r_core.db import make_engine

    generated = generate(profile, params, 4242, source_databases)
    engine = make_engine(source_databases.erp)
    with Session(engine) as session:
        open_lines = session.scalar(select(func.count()).select_from(Ekpo).where(Ekpo.is_open)) or 0
        closed = session.scalar(select(func.count()).select_from(Ekpo).where(~Ekpo.is_open)) or 0
    engine.dispose()
    assert 60 <= open_lines <= 90
    reversed_ = sum(1 for _, lot in generated.plan.lots() if lot.reversed_same_day)
    assert closed == len(generated.plan.batches) - reversed_
