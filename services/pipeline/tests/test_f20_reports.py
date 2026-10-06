"""F20: 52-week and monthly metrics, the calendar, pipeline_daily and releases_weekly (F20-FR-02, F20-AC-04)."""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest
from fixture_world import World
from r2r_core.profile import SiteProfile
from r2r_pipeline.context import new_context
from r2r_pipeline.lake import read_delta
from r2r_pipeline.metrics import metric_months, metric_weeks, pipeline_metrics
from r2r_pipeline.reports import calendar_days, report_files
from r2r_pipeline.setup import setup
from r2r_pipeline.snapshot import snapshot_aggregate
from r2r_pipeline.transform import transform

D = date
MONDAY = D(2026, 10, 12)


def run(world: World, lake: Path, profile: SiteProfile, day: date = MONDAY) -> None:
    world.write(lake)
    ctx = new_context(profile, lake, run_id="run-1", snapshot_date=day)
    transform(ctx)
    snapshot_aggregate(ctx)


def table(lake: Path, name: str) -> list[dict[str, Any]]:
    return read_delta(lake, f"intelligence.{name}").to_pylist()


# --- calendar ----------------------------------------------------------------------------------


def test_f20_fr02_the_calendar_is_365_days_ending_on_the_snapshot_date() -> None:
    days = calendar_days(MONDAY)
    assert len(days) == 365
    assert (days[0], days[-1]) == (D(2025, 10, 13), MONDAY)
    assert all(b - a == timedelta(days=1) for a, b in pairwise(days))


@pytest.mark.usefixtures("demo_clock")
def test_f20_fr02_setup_writes_the_calendar_table(tmp_path: Path, profile: SiteProfile) -> None:
    ctx = setup(profile, tmp_path, run_id="run-1")
    rows = read_delta(tmp_path, "intelligence.calendar").to_pylist()
    assert [r["day"] for r in rows] == calendar_days(ctx.snapshot_date)


# --- 52 weeks and months -----------------------------------------------------------------------


def test_f20_fr02_the_week_list_is_52_complete_weeks_plus_the_current_one() -> None:
    weeks = metric_weeks(D(2026, 10, 14))
    assert len(weeks) == 53
    assert weeks[0][0] == D(2025, 10, 13)
    assert weeks[-2] == (D(2026, 10, 5), MONDAY)
    assert weeks[-1] == (MONDAY, D(2026, 10, 15))


def test_f20_fr02_the_month_list_is_12_complete_months_plus_the_current_to_date() -> None:
    months = metric_months(D(2026, 10, 14))
    assert len(months) == 13
    assert months[0] == (D(2025, 10, 1), D(2025, 11, 1))
    assert months[-2] == (D(2026, 9, 1), D(2026, 10, 1))
    assert months[-1] == (D(2026, 10, 1), D(2026, 10, 15))  # to date, end exclusive


def test_f20_fr02_the_month_list_crosses_a_year_boundary() -> None:
    months = metric_months(D(2026, 1, 5))
    assert months[0][0] == D(2025, 1, 1)
    assert months[-2] == (D(2025, 12, 1), D(2026, 1, 1))
    assert months[-1][0] == D(2026, 1, 1)


def _sampling_world() -> World:
    """Sampling completions: 3 in September (2 on time), 10 in October (8 on time)."""
    world = World()
    for i, collected in enumerate([D(2026, 9, 5), D(2026, 9, 6), D(2026, 9, 20)]):  # 4, 5 and 19 days
        lot, batch = f"2000{i:04d}", f"S{i}"
        world.receive(batch, lot, D(2026, 9, 1))
        world.check(lot, "passed", D(2026, 9, 1))
        world.sample(lot, collected=collected, matnr="RM1", charg=batch)
    for i in range(10):
        lot, batch = f"1000{i:04d}", f"B{i}"
        late = i >= 8
        world.receive(batch, lot, D(2026, 9, 18))
        world.check(lot, "passed", D(2026, 9, 20) if late else D(2026, 10, 1))
        world.sample(lot, collected=D(2026, 10, 6 + i % 3), matnr="RM1", charg=batch)
    return world


@pytest.mark.usefixtures("demo_clock")
def test_f20_fr02_monthly_metrics_pool_by_the_exit_months_calendar_month(
    tmp_path: Path, profile: SiteProfile
) -> None:
    """Hand-computed: M3 in October has 10 completions, 8 within the 7-day SLA; September has 3 and 2."""
    run(_sampling_world(), tmp_path, profile)
    monthly = {(r["metric_id"], r["month_start"]): r for r in table(tmp_path, "monthly_metrics")}
    october = monthly["M3", D(2026, 10, 1)]
    assert (october["completed"], october["on_time"], str(october["pct"])) == (10, 8, "80.0")
    september = monthly["M3", D(2026, 9, 1)]
    assert (september["completed"], september["on_time"]) == (3, 2)
    assert str(september["pct"]) == "66.7"


@pytest.mark.usefixtures("demo_clock")
def test_f20_fr02_monthly_metrics_emit_empty_months_for_every_pipeline_metric(
    tmp_path: Path, profile: SiteProfile
) -> None:
    run(_sampling_world(), tmp_path, profile)
    rows = table(tmp_path, "monthly_metrics")
    assert len(rows) == 3 * 13
    assert {r["metric_id"] for r in rows} == {m.id for m in pipeline_metrics(profile)}
    empty = next(r for r in rows if r["metric_id"] == "M3" and r["month_start"] == D(2026, 6, 1))
    assert (empty["completed"], empty["on_time"], empty["pct"]) == (0, 0, None)


@pytest.mark.usefixtures("demo_clock")
def test_f20_fr02_weekly_metrics_now_cover_53_weeks(tmp_path: Path, profile: SiteProfile) -> None:
    run(_sampling_world(), tmp_path, profile)
    m3 = [r for r in table(tmp_path, "weekly_metrics") if r["metric_id"] == "M3"]
    assert len(m3) == 53
    assert min(r["week_start"] for r in m3) == D(2025, 10, 13)


# --- pipeline_daily ----------------------------------------------------------------------------


def _flow_world() -> World:
    """B1 released on 20 Sep; B2 in sampling since 1 Oct; B3 still pending (receipt reversed)."""
    world = World()
    world.receive("B1", "10000001", D(2026, 9, 1))
    world.check("10000001", "passed", D(2026, 9, 3))
    world.sample(
        "10000001", D(2026, 9, 8), status="approved", approved_at=datetime(2026, 9, 15, 9, tzinfo=UTC)
    )
    world.lot_field("10000001", vcode="A", vdatum=D(2026, 9, 20))
    world.receive("B2", "10000002", D(2026, 10, 1))
    world.check("10000002", "passed", D(2026, 10, 1))
    world.receive("B3", "10000003", D(2026, 10, 9))
    world.move("102", "B3", "0100", D(2026, 10, 9))
    return world


def _daily(lake: Path) -> dict[tuple[date, str], int]:
    return {(r["day"], r["stage_key"]): r["open_count"] for r in table(lake, "pipeline_daily")}


@pytest.mark.usefixtures("demo_clock")
def test_f20_fr02_pipeline_daily_counts_a_lot_in_a_stage_from_entry_up_to_but_not_including_exit(
    tmp_path: Path, profile: SiteProfile
) -> None:
    ctx = setup(profile, tmp_path, run_id="run-1")
    world = _flow_world()
    world.write(tmp_path)
    transform(ctx)
    snapshot_aggregate(ctx)
    daily = _daily(tmp_path)
    assert daily[D(2026, 9, 2), "receipt"] == 1  # B1: receipt 1 Sep to 3 Sep
    assert daily[D(2026, 9, 3), "receipt"] == 0  # exit day: no longer in receipt
    assert daily[D(2026, 9, 3), "sampling"] == 1  # and in sampling from that day
    assert daily[D(2026, 9, 19), "qa_release"] == 1
    assert daily[D(2026, 9, 20), "qa_release"] == 0  # released on 20 Sep: not counted on its release day


@pytest.mark.usefixtures("demo_clock")
def test_f20_ac04_the_latest_day_equals_the_open_non_pending_rows(
    tmp_path: Path, profile: SiteProfile
) -> None:
    """F20-AC-04 (fixture): one open lot in sampling, one released, one pending: the last day totals 1."""
    ctx = setup(profile, tmp_path, run_id="run-1")
    _flow_world().write(tmp_path)
    transform(ctx)
    snapshot_aggregate(ctx)
    last = {k[1]: v for k, v in _daily(tmp_path).items() if k[0] == MONDAY}
    assert sum(last.values()) == 1
    assert last["sampling"] == 1


@pytest.mark.usefixtures("demo_clock")
def test_f20_oq125_a_lot_is_in_at_most_one_stage_per_day_and_the_latest_day_matches_its_stage(
    tmp_path: Path, profile: SiteProfile
) -> None:
    """The one-stage-per-day rule (OQ-125), checked on the contributing rows by brute force."""
    ctx = setup(profile, tmp_path, run_id="run-1")
    _sampling_world().write(tmp_path)
    transform(ctx)
    snapshot_aggregate(ctx)
    snapshot = read_delta(tmp_path, "intelligence.batch_snapshot").to_pylist()
    stages = [s.key for s in profile.stages if not s.terminal and s.sla_days > 0]
    expected: dict[tuple[date, str], int] = defaultdict(int)
    for day in calendar_days(MONDAY):
        for row in snapshot:
            hits = [
                s
                for s in stages
                if row[f"{s}_entry"] is not None
                and row[f"{s}_entry"] <= day
                and (row[f"{s}_exit"] is None or day < row[f"{s}_exit"])
            ]
            assert len(hits) <= 1, (row["row_key"], day, hits)
            for s in hits:
                expected[day, s] += 1
    daily = _daily(tmp_path)
    assert all(daily[key] == expected.get(key, 0) for key in daily)
    open_rows = [r for r in snapshot if r["stage_key"] not in ("pending", "released")]
    assert sum(v for (d, _), v in daily.items() if d == MONDAY) == len(open_rows)


@pytest.mark.usefixtures("demo_clock")
def test_f20_fr02_pipeline_daily_has_a_row_for_every_day_and_stage(
    tmp_path: Path, profile: SiteProfile
) -> None:
    ctx = setup(profile, tmp_path, run_id="run-1")
    _flow_world().write(tmp_path)
    transform(ctx)
    snapshot_aggregate(ctx)
    stages = {s.key for s in profile.stages if not s.terminal and s.sla_days > 0}
    rows = table(tmp_path, "pipeline_daily")
    assert len(rows) == 365 * len(stages)
    assert {r["stage_key"] for r in rows} == stages
    assert "pending" not in stages


# --- releases_weekly ---------------------------------------------------------------------------


@pytest.mark.usefixtures("demo_clock")
def test_f20_fr02_releases_weekly_counts_effective_usage_decisions_by_iso_week_of_the_ud_date(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    for i, (ud, vdate) in enumerate([("A", D(2026, 9, 21)), ("A4", D(2026, 9, 27)), ("A", D(2026, 9, 28)),
                                     ("R", D(2026, 9, 29))]):  # fmt: skip
        lot = f"3000{i:04d}"
        world.receive(f"R{i}", lot, D(2026, 8, 1))
        world.lot_field(lot, vcode=ud, vdatum=vdate)
    run(world, tmp_path, profile)
    weekly = {r["week_start"]: r["released_count"] for r in table(tmp_path, "releases_weekly")}
    assert weekly[D(2026, 9, 21)] == 2  # Monday 21 Sep to Sunday 27 Sep
    assert weekly[D(2026, 9, 28)] == 1  # the rejected lot is not a release
    assert weekly[D(2026, 10, 5)] == 0
    assert len(weekly) == 53 and min(weekly) == D(2025, 10, 13)


@pytest.mark.usefixtures("demo_clock")
def test_f20_fr02_the_report_sql_files_are_portable(profile: SiteProfile) -> None:
    from r2r_pipeline.portability import check_sql
    from r2r_pipeline.reports import render_report
    from r2r_pipeline.sql_shim import render_template

    files = report_files()
    assert [p.name for p in files] == ["10_pipeline_daily.sql.j2", "20_releases_weekly.sql.j2"]
    for path in files:
        assert check_sql(render_report(path, profile), profile.site.timezone) == [], path.name
    assert render_template  # shared renderer


def test_f20_fr02_monthly_metrics_sql_is_portable(profile: SiteProfile) -> None:
    from r2r_pipeline.metrics import metric_files
    from r2r_pipeline.portability import check_sql
    from r2r_pipeline.sql_shim import render_template

    names = [p.name for p in metric_files()]
    assert names == ["10_metric_rows.sql.j2", "20_weekly_metrics.sql.j2", "30_monthly_metrics.sql.j2"]
    path = next(p for p in metric_files() if p.name.startswith("30"))
    rendered = render_template(path.read_text(encoding="utf-8"), metrics=pipeline_metrics(profile))
    assert check_sql(rendered, profile.site.timezone) == []
