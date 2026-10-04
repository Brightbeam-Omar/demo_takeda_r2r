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
