"""T6 [TDD]: the same seed gives the same history (F05-FR-09, F05-AC-01)."""

from typing import Any

import pytest
from datagen.events import plan_events
from datagen.executor import Databases
from datagen.generate import generate
from datagen.model import Plan
from datagen.params import Params
from datagen.planner import build_plan
from erp_sim.models import Base as ErpBase
from lims_sim.models import Base as LimsBase
from qms_sim.models import Base as QmsBase
from r2r_core.profile import SiteProfile
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase


def test_f05_ac01_the_plan_and_its_events_are_identical_for_the_same_seed(
    profile: SiteProfile, params: Params, plan: Plan
) -> None:
    again = build_plan(profile, params, 4242)
    assert again == plan
    assert plan_events(again) == plan_events(plan)


def test_f05_ac01_another_seed_gives_another_history(
    profile: SiteProfile, params: Params, plan: Plan
) -> None:
    other = build_plan(profile, params, 7)
    assert [b.charg for b in other.batches if not b.story_id] != [
        b.charg for b in plan.batches if not b.story_id
    ]
    assert other.batches != plan.batches


# Sequence-generated surrogate ids restart with every wipe, but they are the only thing allowed to differ.
SURROGATE_COLUMNS = {"test_result": {"id"}}


def dump(dsn: str, base: type[DeclarativeBase]) -> dict[str, list[tuple[Any, ...]]]:
    engine = create_engine(dsn)
    out: dict[str, list[tuple[Any, ...]]] = {}
    with engine.connect() as connection:
        for table in base.metadata.sorted_tables:
            skip = SURROGATE_COLUMNS.get(table.name, set())
            columns = [c.name for c in table.columns if c.name not in skip]
            order = ", ".join(columns)
            rows = connection.execute(text(f"SELECT {order} FROM {table.name} ORDER BY {order}")).fetchall()
            out[table.name] = [tuple(row) for row in rows]
    engine.dispose()
    return out


@pytest.mark.integration
def test_f05_ac01_two_runs_with_the_same_seed_give_identical_database_dumps(
    source_databases: Databases, profile: SiteProfile, params: Params
) -> None:
    def snapshot() -> list[dict[str, list[tuple[Any, ...]]]]:
        return [
            dump(source_databases.erp, ErpBase),
            dump(source_databases.lims, LimsBase),
            dump(source_databases.qms, QmsBase),
        ]

    generate(profile, params, 4242, source_databases)
    first = snapshot()
    generate(profile, params, 4242, source_databases)
    second = snapshot()
    assert first == second
    assert sum(len(rows) for db in first for rows in db.values()) > 5000
    generate(profile, params, 4243, source_databases)
    assert snapshot() != first
