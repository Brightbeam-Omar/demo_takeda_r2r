"""``datagen generate``: plan the site history, wipe the source databases, replay it."""

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from pathlib import Path

from r2r_core.profile import SiteProfile

from datagen.events import Event, plan_events
from datagen.executor import Databases, ExecutionResult, Executor
from datagen.model import Plan
from datagen.oracle import oracle_rows, write_oracle
from datagen.params import Params
from datagen.planner import build_plan


@dataclass
class Generated:
    plan: Plan
    events: list[Event]
    result: ExecutionResult


def generate(
    profile: SiteProfile,
    params: Params,
    seed: int,
    databases: Databases,
    artifacts: Path | None = None,
) -> Generated:
    plan = build_plan(profile, params, seed)
    events = plan_events(plan)
    executor = Executor(databases)
    try:
        executor.wipe()
        first = datetime.combine(events[0].day, time(0, 0), tzinfo=UTC) - timedelta(days=1)
        executor.seed_master_data(plan.world, first)
        result = executor.replay(events)
    finally:
        executor.close()
    if artifacts is not None:
        write_oracle(artifacts / "expected_stages.csv", oracle_rows(plan, result))
    return Generated(plan, events, result)


def lot_numbers_from_db(plan: Plan, erp_dsn: str) -> dict[str, str]:
    """Inspection lot numbers of an already generated ERP database, keyed by the plan's lot refs.

    A lot is found by its batch, lot type and start date, which are unique per lot. Lots the database does
    not have are left out (the caller then falls back to the plan's own ref).
    """
    from erp_sim.models import Qals
    from r2r_core.db import make_engine
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    engine = make_engine(erp_dsn)
    try:
        with Session(engine) as session:
            found = {
                (row.matnr, row.charg, row.art, row.pastrterm): row.prueflos
                for row in session.scalars(select(Qals))
            }
    finally:
        engine.dispose()
    out: dict[str, str] = {}
    for batch, lot in plan.lots():
        number = found.get((batch.matnr, batch.charg, lot.lot_type, lot.start))
        if number is not None:
            out[lot.ref] = number
    return out
