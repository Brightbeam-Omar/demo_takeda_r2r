"""T3 [TDD]: weekly metrics SQL and the contributing rows (F07-FR-02, F07-AC-04)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fixture_world import World
from r2r_core.profile import SiteProfile
from r2r_pipeline.context import new_context
from r2r_pipeline.lake import read_delta
from r2r_pipeline.metrics import metric_weeks, pipeline_metrics
from r2r_pipeline.snapshot import snapshot_aggregate
from r2r_pipeline.transform import transform

D = date
MONDAY = D(2026, 10, 12)  # the demo's opening Monday
LAST_WEEK = D(2026, 10, 5)


def run(world: World, lake: Path, profile: SiteProfile, day: date = MONDAY) -> None:
    world.write(lake)
    ctx = new_context(profile, lake, run_id="run-1", snapshot_date=day)
    transform(ctx)
    snapshot_aggregate(ctx)


def weekly(lake: Path) -> list[dict[str, Any]]:
    return read_delta(lake, "intelligence.weekly_metrics").to_pylist()


def contributing(lake: Path) -> list[dict[str, Any]]:
    return read_delta(lake, "intelligence.weekly_metric_rows").to_pylist()


def figures(lake: Path, metric: str, week: date) -> dict[str, Any]:
    [row] = [r for r in weekly(lake) if r["metric_id"] == metric and r["week_start"] == week]
    return row


def sampling_world() -> World:
    """Ten sampling completions in the week of 5 Oct: eight within the 7-day SLA, two over."""
    world = World()
    for i in range(10):
        lot, batch = f"1000{i:04d}", f"B{i}"
        late = i >= 8
        entry = D(2026, 9, 20) if late else D(2026, 10, 1)
        world.receive(batch, lot, D(2026, 9, 18))
        world.check(lot, "passed", entry)  # the sampling stage starts when the inbound check completes
        world.sample(lot, collected=D(2026, 10, 6 + i % 3), status="in_progress", matnr="RM1", charg=batch)
    return world


@pytest.mark.usefixtures("demo_clock")
def test_f07_ac04_ten_sampling_completions_eight_on_time_gives_eighty_percent(
    tmp_path: Path, profile: SiteProfile
) -> None:
    run(sampling_world(), tmp_path, profile)
    row = figures(tmp_path, "M3", LAST_WEEK)
    assert (row["completed"], row["on_time"], row["pct"]) == (10, 8, Decimal("80.0"))
    rows = [r for r in contributing(tmp_path) if r["metric_id"] == "M3" and r["week_start"] == LAST_WEEK]
    assert len(rows) == 10  # exactly the contributing rows
    assert sum(r["on_time"] for r in rows) == 8
    assert {r["sla_days"] for r in rows} == {7}
    late = [r for r in rows if not r["on_time"]]
    assert sorted(r["duration_days"] for r in late) == [16, 18]
    assert set(rows[0]) == {
        "metric_id", "week_start", "row_key", "entry_date", "exit_date", "duration_days", "sla_days",
        "on_time", "run_id",
    }  # fmt: skip


@pytest.mark.usefixtures("demo_clock")
def test_f07_fr02_f20_53_weeks_per_pipeline_metric_with_empty_weeks_null(
    tmp_path: Path, profile: SiteProfile
) -> None:
    run(sampling_world(), tmp_path, profile)
    rows = weekly(tmp_path)
    assert {r["metric_id"] for r in rows} == {"M3", "M6", "M7"}  # pipeline-side metrics only
    m3 = sorted((r for r in rows if r["metric_id"] == "M3"), key=lambda r: r["week_start"])
    assert len(m3) == 53
    assert m3[0]["week_start"] == D(2025, 10, 13)  # 52 complete weeks before the current one (F20-FR-02)
    assert m3[-1]["week_start"] == MONDAY  # the current week to date
    assert all(r["week_start"].weekday() == 0 for r in m3)
    assert (m3[-1]["completed"], m3[-1]["on_time"], m3[-1]["pct"]) == (0, 0, None)
    assert figures(tmp_path, "M3", D(2026, 8, 3))["pct"] is None


@pytest.mark.usefixtures("demo_clock")
def test_f07_fr02_a_completion_after_the_snapshot_week_starts_counts_in_the_current_week(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = sampling_world()
    run(world, tmp_path, profile, day=D(2026, 10, 14))  # Wednesday
    assert figures(tmp_path, "M3", MONDAY)["completed"] == 0
    assert figures(tmp_path, "M3", LAST_WEEK)["completed"] == 10
    assert len(weekly(tmp_path)) == 3 * 53


@pytest.mark.usefixtures("demo_clock")
def test_f07_oq048_a_re_evaluation_lot_is_judged_against_its_own_sla(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 8, 1))
    world.lot_field("10000001", vcode="A", vdatum=D(2026, 8, 20))
    world.sample("10000001", D(2026, 8, 10), status="approved", approved_at=datetime(2026, 8, 19, tzinfo=UTC))
    world.reeval("B1", "10000002", D(2026, 10, 1))  # lot 09: sampling SLA 5 days (profile override)
    world.sample("10000002", D(2026, 10, 7), status="in_progress", charg="B1")  # 6 days: late for a 09 lot
    run(world, tmp_path, profile)
    [row] = [
        r for r in contributing(tmp_path) if r["metric_id"] == "M3" and r["row_key"].endswith("10000002")
    ]
    assert (row["duration_days"], row["sla_days"], row["on_time"]) == (6, 5, False)


@pytest.mark.usefixtures("demo_clock")
def test_f07_fr02_rows_where_the_stage_is_not_finished_are_not_counted(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 10, 1))
    world.check("10000001", "passed", D(2026, 10, 2))  # still in sampling: no collection date yet
    run(world, tmp_path, profile)
    assert contributing(tmp_path) == []
    assert all(r["completed"] == 0 for r in weekly(tmp_path))


def test_f07_fr02_the_week_list_is_iso_weeks_relative_to_the_snapshot_date() -> None:
    weeks = metric_weeks(D(2026, 10, 14))  # a Wednesday
    assert len(weeks) == 53
    assert weeks[-1] == (
        MONDAY,
        D(2026, 10, 15),
    )  # current week to date: up to and including the snapshot day
    assert weeks[-2] == (LAST_WEEK, MONDAY)
    assert weeks[0][0] == D(2025, 10, 13)


def test_f07_fr02_only_pipeline_side_metrics_are_computed(profile: SiteProfile) -> None:
    assert [(m.id, m.stage) for m in pipeline_metrics(profile)] == [
        ("M3", "sampling"), ("M6", "qc_testing"), ("M7", "qa_release"),
    ]  # fmt: skip


def test_f07_fr02_every_metrics_file_is_portable(profile: SiteProfile) -> None:
    """The metrics SQL follows the same portability rules as the transforms (F06-FR-08)."""
    from r2r_pipeline.metrics import metric_files
    from r2r_pipeline.portability import check_sql
    from r2r_pipeline.sql_shim import render_template

    files = metric_files()
    assert [p.name for p in files] == [
        "10_metric_rows.sql.j2",
        "20_weekly_metrics.sql.j2",
        "30_monthly_metrics.sql.j2",
    ]
    for path in files:
        rendered = render_template(path.read_text(encoding="utf-8"), metrics=pipeline_metrics(profile))
        assert check_sql(rendered, profile.site.timezone) == [], path.name
