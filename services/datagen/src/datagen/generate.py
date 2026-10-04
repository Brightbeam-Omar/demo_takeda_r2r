"""``datagen generate``: plan the site history, wipe the source databases, replay it."""

import time as clock_time
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from pathlib import Path

from erp_sim.models import Base as ErpBase
from lims_sim.models import Base as LimsBase
from qms_sim.models import Base as QmsBase
from r2r_core.profile import SiteProfile
from sqlalchemy import create_engine, text

from datagen.events import Event, plan_events
from datagen.executor import Databases, ExecutionResult, Executor
from datagen.model import Plan
from datagen.oracle import oracle_rows, write_oracle
from datagen.params import Params
from datagen.planner import build_plan
from datagen.report import render_report
from datagen.stats import compute_stats


@dataclass
class Generated:
    plan: Plan
    events: list[Event]
    result: ExecutionResult
    elapsed_seconds: float


def generate(
    profile: SiteProfile,
    params: Params,
    seed: int,
    databases: Databases,
    artifacts: Path | None = None,
) -> Generated:
    started = clock_time.perf_counter()  # elapsed time only: business time always comes from the demo clock
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
    elapsed = clock_time.perf_counter() - started
    if artifacts is not None:
        write_artifacts(plan, profile, params, databases, result, elapsed, artifacts)
    return Generated(plan, events, result, elapsed)


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


def table_counts(databases: Databases) -> dict[str, int]:
    """Row count of every table of the three source databases, as "database.table"."""
    counts: dict[str, int] = {}
    for name, dsn, base in (
        ("erp_sim", databases.erp, ErpBase),
        ("lims_sim", databases.lims, LimsBase),
        ("qms_sim", databases.qms, QmsBase),
    ):
        engine = create_engine(dsn)
        try:
            with engine.connect() as connection:
                for table in base.metadata.sorted_tables:
                    total = connection.execute(text(f"SELECT count(*) FROM {table.name}")).scalar_one()
                    counts[f"{name}.{table.name}"] = int(total)
        finally:
            engine.dispose()
    return counts


def write_artifacts(
    plan: Plan,
    profile: SiteProfile,
    params: Params,
    databases: Databases,
    result: ExecutionResult,
    elapsed: float,
    artifacts: Path,
) -> None:
    """The oracle ``expected_stages.csv`` and the report ``datagen_report.md``."""
    write_oracle(artifacts / "expected_stages.csv", oracle_rows(plan, result))
    numbers = {lot.ref: result.lot_number(lot.ref) for _, lot in plan.lots()}
    report = render_report(
        plan,
        profile,
        params,
        compute_stats(plan, profile),
        numbers,
        table_counts(databases),
        result.per_kind,
        elapsed,
    )
    (artifacts / "datagen_report.md").write_text(report, encoding="utf-8")
