"""T3: the plan replays through the F04 event functions (F05-FR-01). Needs Postgres (integration)."""

import time
from collections import Counter

import pytest
from datagen.executor import Databases
from datagen.generate import generate
from datagen.params import load_params
from erp_sim.models import Mara, Mcha, Mdez, Qals
from lims_sim.models import Sample
from r2r_core.profile import load_profile
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def count(dsn: str, model: type) -> int:
    with Session(create_engine(dsn)) as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def test_f05_fr01_generate_populates_the_sources_through_the_event_functions(
    source_databases: Databases,
) -> None:
    started = time.perf_counter()
    generated = generate(load_profile("site_a"), load_params(), 4242, source_databases)
    elapsed = time.perf_counter() - started
    plan = generated.plan
    assert count(source_databases.erp, Mara) == 300
    assert count(source_databases.erp, Mcha) == len(plan.batches)
    assert count(source_databases.erp, Qals) == len(plan.lots())
    assert count(source_databases.erp, Mdez) == len(plan.demands)
    assert count(source_databases.lims, Sample) == sum(len(lot.samples) for _, lot in plan.lots())
    assert generated.result.event_count == len(generated.events)
    print(f"replayed {len(generated.events)} events in {elapsed:.1f}s", Counter(generated.result.per_kind))
    assert elapsed < 60
