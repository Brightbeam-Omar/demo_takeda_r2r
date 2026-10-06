"""T2: row hashes, ``pipeline_runs_v`` and ``pipeline_run_steps_v`` (F21-FR-01, F21-AC-01, F21-AC-02)."""

from datetime import date
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest
from fixture_world import World
from r2r_core.profile import SiteProfile
from r2r_pipeline import runs as runs_module
from r2r_pipeline.context import RunContext
from r2r_pipeline.lake import read_delta
from r2r_pipeline.pipeline import STEP_FUNCTIONS, StepFunction, run_pipeline
from r2r_pipeline.rowhash import HASH_EXCLUDED, ROW_HASH_LAST
from r2r_pipeline.runlog import StepResult


def world(batches: int = 3) -> World:
    w = World()
    for i in range(batches):
        w.receive(f"B{i}", f"1000000{i}", date(2026, 10, 1))
    return w


def functions(w: World, lake: Path, **override: StepFunction) -> dict[str, StepFunction]:
    def stage_world(ctx: RunContext) -> StepResult:
        w.write(lake)
        return StepResult(detail={"freshness": {}, "files": 18})

    return {
        **STEP_FUNCTIONS,
        "extract": stage_world,
        "notify": lambda ctx: StepResult(notify_status="skipped"),
        **override,
    }


def run(w: World, lake: Path, profile: SiteProfile, run_id: str, **override: StepFunction) -> RunContext:
    return run_pipeline(profile, lake, run_id=run_id, functions=functions(w, lake, **override))


def published(lake: Path, name: str) -> list[dict[str, Any]]:
    return read_delta(lake, f"published.{name}").to_pylist()


def runs_by_id(lake: Path) -> dict[str, dict[str, Any]]:
    return {r["pipeline_run_id"]: r for r in published(lake, "pipeline_runs_v")}


def broken(ctx: RunContext) -> StepResult:
    raise RuntimeError("forced failure")


@pytest.mark.usefixtures("demo_clock")
def test_f21_fr01_the_first_run_inserts_every_row(tmp_path: Path, profile: SiteProfile) -> None:
    run(world(), tmp_path, profile, "run-1")
    (first,) = published(tmp_path, "pipeline_runs_v")
    assert (first["status"], first["failed_step"], first["files"]) == ("ok", None, 18)
    assert (first["inserted"], first["total"], first["skipped"]) == (3, 3, 0)
    assert first["pipeline_run_id"] == first["run_id"] == "run-1"
    assert first["duration_ms"] >= 0


@pytest.mark.usefixtures("demo_clock")
def test_f21_ac01_a_second_run_on_unchanged_data_inserts_nothing(
    tmp_path: Path, profile: SiteProfile
) -> None:
    w = world()
    run(w, tmp_path, profile, "run-1")
    run(w, tmp_path, profile, "run-2")
    runs = runs_by_id(tmp_path)
    assert (runs["run-2"]["inserted"], runs["run-2"]["skipped"], runs["run-2"]["total"]) == (0, 3, 3)
    assert runs["run-1"]["inserted"] == 3  # the history keeps the earlier figures


@pytest.mark.usefixtures("demo_clock")
def test_f21_ac01_a_changed_lot_is_inserted_by_the_next_run(tmp_path: Path, profile: SiteProfile) -> None:
    w = world()
    run(w, tmp_path, profile, "run-1")
    w.check("10000001", "passed", date(2026, 10, 3))  # one lot moves on
    run(w, tmp_path, profile, "run-2")
    assert (runs_by_id(tmp_path)["run-2"]["inserted"], runs_by_id(tmp_path)["run-2"]["skipped"]) == (1, 2)


@pytest.mark.usefixtures("demo_clock")
def test_f21_fr01_a_new_lot_counts_as_inserted(tmp_path: Path, profile: SiteProfile) -> None:
    w = world(2)
    run(w, tmp_path, profile, "run-1")
    w.receive("B9", "10000009", date(2026, 10, 2))
    run(w, tmp_path, profile, "run-2")
    assert runs_by_id(tmp_path)["run-2"]["inserted"] == 1


@pytest.mark.usefixtures("demo_clock")
def test_f21_fr01_the_hash_ignores_the_run_stamps_and_the_snapshot_date(
    tmp_path: Path, profile: SiteProfile
) -> None:
    assert set(HASH_EXCLUDED) == {"row_key", "snapshot_date", "run_id", "published_at", "row_hash"}
    w = world(2)
    run(w, tmp_path, profile, "run-1")
    first = {r["row_key"]: r["row_hash"] for r in read_delta(tmp_path, ROW_HASH_LAST).to_pylist()}
    run(w, tmp_path, profile, "run-2")  # new run id and published_at, same content
    second = {r["row_key"]: r["row_hash"] for r in read_delta(tmp_path, ROW_HASH_LAST).to_pylist()}
    assert first == second
    assert {r["pipeline_run_id"] for r in read_delta(tmp_path, ROW_HASH_LAST).to_pylist()} == {"run-2"}


@pytest.mark.usefixtures("demo_clock")
def test_f21_ac02_a_failed_run_appears_after_the_next_successful_one(
    tmp_path: Path, profile: SiteProfile
) -> None:
    w = world()
    run(w, tmp_path, profile, "run-1")
    with pytest.raises(RuntimeError):
        run(w, tmp_path, profile, "run-2", transform=broken)
    assert "run-2" not in runs_by_id(tmp_path)  # a failed run publishes nothing
    run(w, tmp_path, profile, "run-3")
    runs = runs_by_id(tmp_path)
    failed = runs["run-2"]
    assert (failed["status"], failed["failed_step"]) == ("failed", "transform")
    assert (failed["inserted"], failed["total"], failed["skipped"]) == (None, None, None)
    assert failed["files"] == 18 and failed["run_id"] == "run-3"
    assert [runs[r]["status"] for r in ("run-1", "run-2", "run-3")] == ["ok", "failed", "ok"]
    ordered = [
        r["pipeline_run_id"]
        for r in sorted(published(tmp_path, "pipeline_runs_v"), key=lambda r: -r["run_seq"])
    ]
    assert ordered == ["run-3", "run-2", "run-1"]  # newest first even though the demo clock stood still


@pytest.mark.usefixtures("demo_clock")
def test_f21_fr01_a_failure_after_the_snapshot_does_not_move_the_baseline(
    tmp_path: Path, profile: SiteProfile
) -> None:
    w = world()
    run(w, tmp_path, profile, "run-1")
    w.check("10000001", "passed", date(2026, 10, 3))
    with pytest.raises(RuntimeError):
        run(w, tmp_path, profile, "run-2", publish=broken)  # snapshot_aggregate ran, publish did not
    assert {r["pipeline_run_id"] for r in read_delta(tmp_path, ROW_HASH_LAST).to_pylist()} == {"run-1"}
    run(w, tmp_path, profile, "run-3")
    assert runs_by_id(tmp_path)["run-3"]["inserted"] == 1  # still compared against the published run-1
    failed = runs_by_id(tmp_path)["run-2"]
    assert (failed["status"], failed["failed_step"], failed["inserted"]) == ("failed", "publish", None)


@pytest.mark.usefixtures("demo_clock")
def test_f21_fr01_the_steps_view_lists_each_run_step_by_step(tmp_path: Path, profile: SiteProfile) -> None:
    w = world(2)
    run(w, tmp_path, profile, "run-1")
    with pytest.raises(RuntimeError):
        run(w, tmp_path, profile, "run-2", transform=broken)
    run(w, tmp_path, profile, "run-3")
    steps = published(tmp_path, "pipeline_run_steps_v")
    per_run: dict[str, list[tuple[str, str]]] = {}
    for step in steps:
        per_run.setdefault(step["pipeline_run_id"], []).append((step["step"], step["status"]))
    assert per_run["run-2"] == [("setup", "success"), ("extract", "success"), ("transform", "failed")]
    assert per_run["run-1"][-2:] == [("publish", "success"), ("notify", "success")]
    assert per_run["run-3"][-1] == ("publish", "success")  # the current run is still inside publish
    assert {s["run_id"] for s in steps} == {"run-3"}
    failed = next(s for s in steps if s["status"] == "failed")
    assert failed["error"] == "RuntimeError: forced failure"
    publish_row = next(s for s in steps if (s["pipeline_run_id"], s["step"]) == ("run-3", "publish"))
    assert publish_row["rows"] == 2
    assert all(s["duration_ms"] is not None and s["duration_ms"] >= 0 for s in steps)


@pytest.mark.usefixtures("demo_clock")
def test_f21_fr01_the_history_keeps_the_last_hundred_runs(
    tmp_path: Path, profile: SiteProfile, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert runs_module.HISTORY_LIMIT == 100
    monkeypatch.setattr(runs_module, "HISTORY_LIMIT", 3)  # a hundred real runs take minutes
    w = world(1)
    for number in range(5):
        run(w, tmp_path, profile, f"run-{number}")
    runs = published(tmp_path, "pipeline_runs_v")
    assert {r["pipeline_run_id"] for r in runs} == {"run-2", "run-3", "run-4"}
    assert {s["pipeline_run_id"] for s in published(tmp_path, "pipeline_run_steps_v")} == {
        r["pipeline_run_id"] for r in runs
    }


@pytest.mark.usefixtures("demo_clock")
def test_f21_ac06_the_declared_schemas_are_exactly_what_the_pipeline_publishes(
    tmp_path: Path, profile: SiteProfile
) -> None:
    from deltalake import DeltaTable
    from r2r_pipeline.contract_schemas import published_schemas
    from r2r_pipeline.publish import PUBLISH_ORDER

    w = world(2)
    w.deviation("DEV-000001", "open", [("RM1", "B0")])
    w.change_control("CC-000001", "open", [("RM1", "B0")])
    w.po_line("4500000001", date(2026, 10, 20))
    run(w, tmp_path, profile, "run-1")
    declared = published_schemas()
    assert list(declared) == list(PUBLISH_ORDER)
    for name, schema in declared.items():
        actual = pa.schema(DeltaTable(str(tmp_path / "published" / name)).schema().to_arrow())
        assert [(f.name, str(f.type)) for f in actual] == [(f.name, str(f.type)) for f in schema], name
