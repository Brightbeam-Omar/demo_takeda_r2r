"""T1: the run log and the setup step (F07-FR-05)."""

import json
from datetime import date
from pathlib import Path

import pytest
from r2r_core.profile import SiteProfile
from r2r_pipeline.lake import read_delta
from r2r_pipeline.runlog import RUN_LOG_SCHEMA, StepResult, read_log, run_step, step_detail, step_row
from r2r_pipeline.setup import setup

pytestmark = pytest.mark.usefixtures("demo_clock")


def test_f07_fr05_setup_records_the_run_start_with_demo_time(tmp_path: Path, profile: SiteProfile) -> None:
    ctx = setup(profile, tmp_path, run_id="run-1")
    [row] = read_log(ctx)
    assert (row["run_id"], row["step"], row["status"]) == ("run-1", "setup", "success")
    assert row["started_at"].isoformat() == "2026-10-12T07:00:00+00:00"  # the demo clock, not wall time
    assert row["finished_at"] is not None
    assert ctx.snapshot_date == date(2026, 10, 12)
    assert step_detail(ctx, "setup")["snapshot_date"] == "2026-10-12"


def test_f07_fr05_the_log_has_the_contract_columns(tmp_path: Path, profile: SiteProfile) -> None:
    setup(profile, tmp_path, run_id="run-1")
    table = read_delta(tmp_path, "intelligence.pipeline_run_log")
    assert table.schema.names == [
        "run_id", "step", "status", "started_at", "finished_at", "rows", "error", "notify_status", "detail_json",
    ]  # fmt: skip
    assert table.schema == RUN_LOG_SCHEMA


def test_f07_fr05_every_step_appends_one_row_and_runs_stay_apart(
    tmp_path: Path, profile: SiteProfile
) -> None:
    first = setup(profile, tmp_path, run_id="run-1")
    run_step(first, "extract", lambda: StepResult(rows=12, detail={"freshness": {"erp": {}}}))
    second = setup(profile, tmp_path, run_id="run-2")
    assert [r["step"] for r in read_log(first)] == ["setup", "extract"]
    assert [r["step"] for r in read_log(second)] == ["setup"]
    assert step_row(first, "extract")["rows"] == 12
    assert step_detail(first, "extract")["freshness"] == {"erp": {}}


def test_f07_fr05_a_failing_step_is_logged_with_its_error_and_re_raised(
    tmp_path: Path, profile: SiteProfile
) -> None:
    ctx = setup(profile, tmp_path, run_id="run-1")

    def boom() -> StepResult:
        raise RuntimeError("source down")

    with pytest.raises(RuntimeError, match="source down"):
        run_step(ctx, "extract", boom)
    failed = read_log(ctx)[-1]
    assert (failed["step"], failed["status"]) == ("extract", "failed")
    assert failed["error"] == "RuntimeError: source down"
    with pytest.raises(LookupError):
        step_row(ctx, "extract")  # only successful rows count for later steps


def test_f07_fr05_the_detail_is_compact_json_with_a_duration(tmp_path: Path, profile: SiteProfile) -> None:
    ctx = setup(profile, tmp_path, run_id="run-1")
    detail = json.loads(step_row(ctx, "setup")["detail_json"])
    assert "duration_ms" in detail
