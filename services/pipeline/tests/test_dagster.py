"""T7: the Dagster job, its stopped schedule and the reset job (F07-FR-06, F07-AC-08)."""

from datetime import date
from itertools import pairwise
from pathlib import Path

import pytest
import yaml
from dagster import DagsterInstance, DefaultScheduleStatus
from fixture_world import World
from r2r_pipeline import pipeline as pipeline_module
from r2r_pipeline.context import RunContext
from r2r_pipeline.dagster_defs import defs, r2r_pipeline, r2r_reset_lakehouse
from r2r_pipeline.lake import LAYERS, delta_exists, reset_lakehouse, write_delta
from r2r_pipeline.runlog import STEPS, StepResult, read_log

HOME = Path(__file__).resolve().parents[1] / "dagster_home"


def test_f07_fr06_the_job_has_the_six_ops_in_order() -> None:
    graph = r2r_pipeline.graph
    assert {node.name for node in graph.nodes} == set(STEPS)
    order = ["setup", "extract", "transform", "snapshot_aggregate", "publish", "notify"]
    assert order == list(STEPS)
    # each op depends on the one before it
    for earlier, later in pairwise(order):
        deps = graph.dependency_structure.input_to_upstream_outputs_for_node(later)
        assert {out.node_name for outs in deps.values() for out in outs} == {earlier}


def test_f07_fr06_the_four_hourly_schedule_is_defined_but_stopped() -> None:
    [schedule] = defs.schedules or []
    assert schedule.cron_schedule == "0 */4 * * *"
    assert schedule.default_status == DefaultScheduleStatus.STOPPED
    assert {j.name for j in defs.jobs or []} == {"r2r_pipeline", "r2r_reset_lakehouse"}


def test_f07_fr06_the_instance_uses_postgres_storage_and_the_workspace_points_at_the_defs() -> None:
    instance = yaml.safe_load((HOME / "dagster.yaml").read_text())
    assert instance["storage"]["postgres"]["postgres_db"]["db_name"] == "dagster"
    workspace = yaml.safe_load((HOME / "workspace.yaml").read_text())
    assert workspace["load_from"] == [{"python_module": "r2r_pipeline.dagster_defs"}]


@pytest.mark.usefixtures("demo_clock")
def test_f07_ac08_all_six_ops_run_and_the_pipeline_run_id_is_the_dagster_run_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = World()
    world.receive("B1", "10000001", date(2026, 10, 1))

    def stage_world(ctx: RunContext) -> StepResult:
        world.write(tmp_path)
        return StepResult(detail={"freshness": {}})

    monkeypatch.setitem(pipeline_module.STEP_FUNCTIONS, "extract", stage_world)
    monkeypatch.setenv("LAKEHOUSE_PATH", str(tmp_path))
    monkeypatch.delenv("WEBHOOK_URL", raising=False)

    result = r2r_pipeline.execute_in_process(instance=DagsterInstance.ephemeral())
    assert result.success
    assert {event.step_key for event in result.get_step_success_events()} == set(STEPS)

    from r2r_core.profile import load_profile
    from r2r_pipeline.context import new_context
    from r2r_pipeline.lake import read_delta

    ctx = new_context(load_profile("site_a"), tmp_path, run_id=result.run_id)
    assert [r["step"] for r in read_log(ctx)] == list(STEPS)
    [status] = read_delta(tmp_path, "published.pipeline_status_v").to_pylist()
    assert status["last_run_id"] == result.run_id
    assert read_log(ctx)[-1]["notify_status"] == "skipped"  # no WEBHOOK_URL in the test


def test_f07_fr06_the_reset_removes_the_tables_and_keeps_the_three_folders(tmp_path: Path) -> None:
    import pyarrow as pa

    for layer in LAYERS:
        write_delta(tmp_path, f"{layer}.t1", pa.table({"a": [1]}))
        write_delta(tmp_path, f"{layer}.t2", pa.table({"a": [1]}))
    removed = reset_lakehouse(tmp_path)
    assert sorted(removed) == sorted(f"{layer}.{t}" for layer in LAYERS for t in ("t1", "t2"))
    assert all((tmp_path / layer).is_dir() and not list((tmp_path / layer).iterdir()) for layer in LAYERS)
    assert not delta_exists(tmp_path, "published.t1")
    assert reset_lakehouse(tmp_path) == []  # idempotent, also on an empty lake


def test_f07_fr06_the_reset_creates_missing_folders(tmp_path: Path) -> None:
    reset_lakehouse(tmp_path / "lake")
    assert all((tmp_path / "lake" / layer).is_dir() for layer in LAYERS)


@pytest.mark.usefixtures("demo_clock")
def test_f07_fr06_the_reset_job_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import pyarrow as pa

    write_delta(tmp_path, "published.pipeline_status_v", pa.table({"a": [1]}))
    monkeypatch.setenv("LAKEHOUSE_PATH", str(tmp_path))
    assert r2r_reset_lakehouse.execute_in_process(instance=DagsterInstance.ephemeral()).success
    assert not delta_exists(tmp_path, "published.pipeline_status_v")
