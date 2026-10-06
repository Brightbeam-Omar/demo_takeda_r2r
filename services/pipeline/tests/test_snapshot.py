"""T2 [TDD]: snapshot_aggregate and need-by history locking (F07-FR-01, F07-AC-02, F07-AC-03)."""

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fixture_world import World
from r2r_core.profile import SiteProfile
from r2r_pipeline.context import RunContext, new_context
from r2r_pipeline.lake import read_delta
from r2r_pipeline.snapshot import snapshot_aggregate
from r2r_pipeline.transform import transform

D = date
DAY1, DAY2, DAY3 = D(2026, 10, 12), D(2026, 10, 13), D(2026, 10, 14)


def run_day(world: World, lake: Path, profile: SiteProfile, day: date, run_id: str) -> RunContext:
    """Stage the world, run transform and snapshot_aggregate for ``day`` (a fresh run id each call)."""
    world.write(lake)
    ctx = new_context(profile, lake, run_id=run_id, snapshot_date=day)
    transform(ctx)
    snapshot_aggregate(ctx)
    return ctx


def snapshot_rows(lake: Path, day: date | None = None) -> list[dict[str, Any]]:
    rows = read_delta(lake, "intelligence.batch_snapshot").to_pylist()
    return [r for r in rows if day is None or r["snapshot_date"] == day]


def by_lot(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r["inspection_lot_no"]: r for r in rows}


@pytest.fixture
def world() -> World:
    w = World()
    w.receive("B1", "10000001", D(2026, 10, 1))
    w.receive("B2", "10000002", D(2026, 10, 2))
    w.demand(1, D(2026, 11, 20), "CMP-ALPHA")
    return w


@pytest.mark.usefixtures("demo_clock")
def test_f07_fr01_the_snapshot_joins_flat_and_stage_with_run_columns(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    run_day(world, tmp_path, profile, DAY1, "run-1")
    flat = read_delta(tmp_path, "staging.batch_flat")
    stage = read_delta(tmp_path, "staging.batch_stage")
    table = read_delta(tmp_path, "intelligence.batch_snapshot")
    assert table.num_rows == flat.num_rows == stage.num_rows == 2
    expected = [*flat.schema.names, *[n for n in stage.schema.names if n != "row_key"]]
    assert table.schema.names == [*expected, "snapshot_date", "run_id", "system_need_by_locked", "row_hash"]
    row = by_lot(table.to_pylist())["10000001"]
    assert (row["snapshot_date"], row["run_id"], row["stage_key"]) == (DAY1, "run-1", "receipt")


@pytest.mark.usefixtures("demo_clock")
def test_f07_ac02_running_twice_on_the_same_day_gives_the_same_row_count(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    run_day(world, tmp_path, profile, DAY1, "run-1")
    first = len(snapshot_rows(tmp_path, DAY1))
    run_day(world, tmp_path, profile, DAY1, "run-2")
    assert len(snapshot_rows(tmp_path, DAY1)) == first == 2
    assert {r["run_id"] for r in snapshot_rows(tmp_path, DAY1)} == {"run-2"}  # the date's rows were replaced


@pytest.mark.usefixtures("demo_clock")
def test_f07_fr01_a_run_replaces_only_its_own_date(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    run_day(world, tmp_path, profile, DAY1, "run-1")
    run_day(world, tmp_path, profile, DAY2, "run-2")
    run_day(world, tmp_path, profile, DAY2, "run-3")
    assert len(snapshot_rows(tmp_path, DAY1)) == 2
    assert len(snapshot_rows(tmp_path, DAY2)) == 2
    assert {r["run_id"] for r in snapshot_rows(tmp_path, DAY1)} == {"run-1"}


@pytest.mark.usefixtures("demo_clock")
def test_f07_ac03_the_locked_need_by_stays_at_the_first_seen_value(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    run_day(world, tmp_path, profile, DAY1, "run-1")
    first = by_lot(snapshot_rows(tmp_path, DAY1))["10000001"]
    assert (first["system_need_by_date"], first["system_need_by_locked"]) == (
        D(2026, 11, 20),
        D(2026, 11, 20),
    )

    world.rows["stg_mdez"][0]["bdter"] = D(2026, 12, 15)  # demand moves later
    run_day(world, tmp_path, profile, DAY2, "run-2")
    second = by_lot(snapshot_rows(tmp_path, DAY2))["10000001"]
    assert second["system_need_by_date"] == D(2026, 12, 15)
    assert second["system_need_by_locked"] == D(2026, 11, 20)


@pytest.mark.usefixtures("demo_clock")
def test_f07_oq045_history_holds_one_row_per_row_key_and_is_never_updated(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    run_day(world, tmp_path, profile, DAY1, "run-1")
    world.rows["stg_mdez"][0]["bdter"] = D(2026, 12, 15)
    run_day(world, tmp_path, profile, DAY2, "run-2")
    run_day(world, tmp_path, profile, DAY2, "run-3")
    history = read_delta(tmp_path, "intelligence.need_by_history")
    assert history.schema.names == ["row_key", "system_need_by_date", "first_seen_date", "run_id"]
    rows = history.to_pylist()
    assert sorted(r["row_key"] for r in rows) == ["RM1|B1|10000001", "RM1|B2|10000002"]
    assert {(r["system_need_by_date"], r["first_seen_date"], r["run_id"]) for r in rows} == {
        (D(2026, 11, 20), DAY1, "run-1")
    }


@pytest.mark.usefixtures("demo_clock")
def test_f07_oq045_the_first_non_null_value_is_locked(tmp_path: Path, profile: SiteProfile) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 10, 1))
    run_day(world, tmp_path, profile, DAY1, "run-1")
    assert by_lot(snapshot_rows(tmp_path, DAY1))["10000001"]["system_need_by_locked"] is None
    assert read_delta(tmp_path, "intelligence.need_by_history").num_rows == 0

    world.demand(1, D(2026, 12, 1))  # demand appears on day 2
    run_day(world, tmp_path, profile, DAY2, "run-2")
    assert by_lot(snapshot_rows(tmp_path, DAY2))["10000001"]["system_need_by_locked"] == D(2026, 12, 1)
    world.rows["stg_mdez"][0]["bdter"] = D(2026, 12, 20)
    run_day(world, tmp_path, profile, DAY3, "run-3")
    assert by_lot(snapshot_rows(tmp_path, DAY3))["10000001"]["system_need_by_locked"] == D(2026, 12, 1)


@pytest.mark.usefixtures("demo_clock")
def test_f07_oq045_a_row_released_before_it_had_demand_stays_null(
    tmp_path: Path, profile: SiteProfile
) -> None:
    world = World()
    world.receive("B1", "10000001", D(2026, 9, 1))
    world.lot_field("10000001", vcode="A", vdatum=D(2026, 10, 9))  # released
    world.demand(1, D(2026, 12, 1))
    run_day(world, tmp_path, profile, DAY1, "run-1")
    row = by_lot(snapshot_rows(tmp_path, DAY1))["10000001"]
    assert (row["stage_key"], row["system_need_by_date"], row["system_need_by_locked"]) == (
        "released",
        None,
        None,
    )


@pytest.mark.usefixtures("demo_clock")
def test_f07_oq045_a_locked_value_survives_the_release(
    world: World, tmp_path: Path, profile: SiteProfile
) -> None:
    run_day(world, tmp_path, profile, DAY1, "run-1")
    world.lot_field("10000001", vcode="A", vdatum=D(2026, 10, 13))
    run_day(world, tmp_path, profile, DAY2, "run-2")
    row = by_lot(snapshot_rows(tmp_path, DAY2))["10000001"]
    assert (row["stage_key"], row["system_need_by_date"]) == ("released", None)
    assert row["system_need_by_locked"] == D(2026, 11, 20)
