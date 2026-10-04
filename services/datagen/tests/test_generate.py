"""T3: the plan replays through the F04 event functions (F05-FR-01). Needs Postgres (integration)."""

import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path

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


def test_f05_fr08_fr11_generate_writes_the_report_and_the_oracle(
    source_databases: Databases, tmp_path: Path
) -> None:
    generated = generate(load_profile("site_a"), load_params(), 4242, source_databases, tmp_path)
    report = (tmp_path / "datagen_report.md").read_text(encoding="utf-8")
    for heading in (
        "## Volumes",
        "## Rows by table",
        "## Open-row stage mix",
        "## RAG mix",
        "## Quirks",
        "## Story batches",
    ):
        assert heading in report
    for story in ("B1042", "B2077", "B3150", "B4410", "B5003"):
        assert story in report
    assert "**NO**" not in report  # every target in the report is met
    lines = (tmp_path / "expected_stages.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "row_key,intended_stage,story_id"
    assert len(lines) == 1 + len(generated.plan.lots())
    assert any(line.endswith(",B5003") and ",qa_release," in line for line in lines)
    assert generated.elapsed_seconds < 60  # F05-AC-07


def test_f05_oracle_is_a_sidecar_and_not_loaded_into_any_source_database(source_databases: Databases) -> None:
    from sqlalchemy import inspect

    for dsn in (source_databases.erp, source_databases.lims, source_databases.qms):
        tables = set(inspect(create_engine(dsn)).get_table_names())
        assert not any("expected" in name or "oracle" in name for name in tables)


def test_f05_ac03_ac04_quirks_and_stories_reach_the_databases(
    source_databases: Databases, tmp_path: Path
) -> None:
    from datetime import UTC, datetime

    from erp_sim.models import Mchb
    from lims_sim.models import TestResult
    from qms_sim.models import Deviation, DeviationLink

    generate(load_profile("site_a"), load_params(), 4242, source_databases, tmp_path)
    erp, lims, qms = (
        create_engine(d) for d in (source_databases.erp, source_databases.lims, source_databases.qms)
    )
    with Session(erp) as session:
        assert session.scalar(select(func.count()).select_from(Mcha).where(Mcha.zstat == "H")) >= 3
        assert session.scalar(select(func.count()).select_from(Mchb).where(Mchb.speme > 0)) >= 3
        assert session.scalar(select(func.count()).select_from(Qals).where(Qals.vcode == "R")) >= 3
    with Session(lims) as session:
        sample = session.scalars(select(Sample).where(Sample.batch_no == "B5003")).one()
        assert sample.approved_at == datetime(2026, 10, 11, 1, 0, tzinfo=UTC)
        assert count(source_databases.lims, TestResult) == 5
    with Session(qms) as session:
        linked = session.scalars(select(DeviationLink).where(DeviationLink.batch_no == "B3150")).all()
        deviation = session.get(Deviation, linked[0].deviation_no)
        assert deviation is not None and (deviation.severity, deviation.status) == ("major", "open")
    report = (tmp_path / "datagen_report.md").read_text(encoding="utf-8")
    for text in ("M3 sampling done", "Batches (distinct)", "Inspection lots (rows)"):
        assert text in report or text.replace("Tier 1 pipeline", "In Tier 1 the pipeline") in report


def test_f05_oq039_only_the_air_gap_lots_lack_the_erp_results_record(
    source_databases: Databases, tmp_path: Path
) -> None:
    generate(load_profile("site_a"), load_params(), 4242, source_databases, tmp_path)
    erp, lims = create_engine(source_databases.erp), create_engine(source_databases.lims)
    with Session(lims) as session:
        approved = set(
            session.scalars(select(Sample.inspection_lot_no).where(Sample.status == "approved")).all()
        )
        b5003 = session.scalars(select(Sample.inspection_lot_no).where(Sample.batch_no == "B5003")).one()
    with Session(erp) as session:
        lots = session.scalars(select(Qals).where(Qals.vcode.is_(None))).all()
        gaps = {lot.prueflos for lot in lots if lot.prueflos in approved and lot.zresrec is None}
        recorded = [lot for lot in lots if lot.prueflos in approved and lot.zresrec is not None]
    assert 3 <= len(gaps) <= 5
    assert b5003 in gaps
    assert recorded  # normal approvals have their results recorded


def test_f05_generate_leaves_the_app_database_including_demo_clock_unchanged(
    source_databases: Databases, make_test_database: Callable[[str], str]
) -> None:
    from app_api.db import migrate as migrate_app
    from sqlalchemy import text

    app_dsn = make_test_database("datagen_app")
    migrate_app(app_dsn)
    engine = create_engine(app_dsn)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO demo_clock (id, now_utc, frozen) VALUES (1, '2026-10-12T07:00:00+00', false)")
        )

    def snapshot() -> list[tuple[object, ...]]:
        with engine.connect() as connection:
            tables = connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1")
            )
            return [
                (name, *row)
                for (name,) in tables.fetchall()
                for row in connection.execute(text(f"SELECT * FROM {name}")).fetchall()
            ]

    before = snapshot()
    assert any(row[0] == "demo_clock" for row in before)
    generate(load_profile("site_a"), load_params(), 4242, source_databases)
    assert snapshot() == before
    engine.dispose()
