"""T6: failure semantics: a failed run publishes nothing (F07-FR-07, F07-AC-07)."""

from datetime import date
from pathlib import Path

import pytest
from fixture_world import World
from r2r_core.profile import SiteProfile
from r2r_pipeline import pipeline as pipeline_module
from r2r_pipeline.context import RunContext, new_context
from r2r_pipeline.lake import read_delta
from r2r_pipeline.pipeline import STEP_FUNCTIONS, StepFunction, run_pipeline
from r2r_pipeline.runlog import STEPS, StepResult, read_log


def world(batches: int) -> World:
    w = World()
    for i in range(batches):
        w.receive(f"B{i}", f"1000000{i}", date(2026, 10, 1))
    return w


def functions(w: World, lake: Path, **override: StepFunction) -> dict[str, StepFunction]:
    """Real steps, except that extract stages the hand-built world instead of reading Postgres."""

    def stage_world(ctx: RunContext) -> StepResult:
        w.write(lake)
        return StepResult(detail={"freshness": {}})

    return {
        **STEP_FUNCTIONS,
        "extract": stage_world,
        "notify": lambda ctx: StepResult(notify_status="skipped"),
        **override,
    }


def published(lake: Path, name: str) -> list[dict[str, object]]:
    return read_delta(lake, f"published.{name}").to_pylist()


@pytest.mark.usefixtures("demo_clock")
def test_f07_fr06_a_good_run_logs_all_six_steps_in_order(tmp_path: Path, profile: SiteProfile) -> None:
    ctx = run_pipeline(profile, tmp_path, run_id="run-1", functions=functions(world(2), tmp_path))
    log = read_log(ctx)
    assert [r["step"] for r in log] == list(STEPS)
    assert {r["status"] for r in log} == {"success"}
    assert log[-1]["notify_status"] == "skipped"
    assert [r["rows"] for r in log if r["step"] in ("transform", "snapshot_aggregate", "publish")] == [
        2,
        2,
        2,
    ]


@pytest.mark.usefixtures("demo_clock")
def test_f07_ac07_a_failure_in_transform_leaves_published_unchanged_and_is_logged(
    tmp_path: Path, profile: SiteProfile
) -> None:
    run_pipeline(profile, tmp_path, run_id="run-1", functions=functions(world(2), tmp_path))
    before = {name: published(tmp_path, name) for name in ("batch_pipeline_v", "pipeline_status_v")}

    def broken(ctx: RunContext) -> StepResult:
        raise RuntimeError("forced failure in transform")

    with pytest.raises(RuntimeError, match="forced failure"):
        run_pipeline(
            profile, tmp_path, run_id="run-2", functions=functions(world(3), tmp_path, transform=broken)
        )

    assert {name: published(tmp_path, name) for name in before} == before  # the previous state is intact
    assert published(tmp_path, "pipeline_status_v")[0]["last_run_id"] == "run-1"
    failed = read_log(_ctx(profile, tmp_path, "run-2"))
    assert [(r["step"], r["status"]) for r in failed] == [
        ("setup", "success"), ("extract", "success"), ("transform", "failed"),
    ]  # fmt: skip
    assert failed[-1]["error"] == "RuntimeError: forced failure in transform"
    assert "snapshot_aggregate" not in [r["step"] for r in failed]  # nothing after the failure ran


@pytest.mark.usefixtures("demo_clock")
def test_f07_fr07_a_failure_in_snapshot_also_blocks_publish(tmp_path: Path, profile: SiteProfile) -> None:
    run_pipeline(profile, tmp_path, run_id="run-1", functions=functions(world(2), tmp_path))

    def broken(ctx: RunContext) -> StepResult:
        raise ValueError("snapshot failed")

    with pytest.raises(ValueError, match="snapshot failed"):
        run_pipeline(
            profile,
            tmp_path,
            run_id="run-2",
            functions=functions(world(3), tmp_path, snapshot_aggregate=broken),
        )
    assert published(tmp_path, "pipeline_status_v")[0]["last_run_id"] == "run-1"
    assert len(published(tmp_path, "batch_pipeline_v")) == 2


@pytest.mark.usefixtures("demo_clock")
def test_f07_fr04_a_notify_exception_does_not_fail_the_run(
    tmp_path: Path, profile: SiteProfile, monkeypatch: pytest.MonkeyPatch
) -> None:
    def exploding(ctx: RunContext) -> StepResult:
        raise OSError("socket closed")

    monkeypatch.setattr(pipeline_module, "notify", exploding)
    funcs = {**functions(world(1), tmp_path), "notify": pipeline_module._notify}
    ctx = run_pipeline(profile, tmp_path, run_id="run-1", functions=funcs)
    last = read_log(ctx)[-1]
    assert (last["step"], last["status"], last["notify_status"]) == ("notify", "success", "failed")


def _ctx(profile: SiteProfile, lake: Path, run_id: str) -> RunContext:
    return new_context(profile, lake, run_id=run_id)
