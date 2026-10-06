"""The six steps as plain functions, and a runner that executes them in order (F07-FR-06, F07-FR-07).

Dagster wraps the same ``execute_step`` in one op per step; this module is also what the tests and a plain
Python run use. A step that raises is logged as failed by ``run_step`` and the exception stops the run, so
``publish`` never runs and the previous ``published/`` state stays as it was.
"""

import logging
import os
from collections.abc import Callable, Mapping
from pathlib import Path

from r2r_core.profile import SiteProfile, load_profile

from r2r_pipeline.context import RunContext, SourceDsns, new_context
from r2r_pipeline.extract import extract
from r2r_pipeline.lake import read_delta
from r2r_pipeline.notify import notify
from r2r_pipeline.publish import publish
from r2r_pipeline.runlog import STEPS, StepResult, run_step
from r2r_pipeline.schemas import STAGING_SCHEMAS
from r2r_pipeline.setup import setup
from r2r_pipeline.snapshot import snapshot_aggregate
from r2r_pipeline.transform import transform

log = logging.getLogger(__name__)

StepFunction = Callable[[RunContext], StepResult | None]


def _extract(ctx: RunContext) -> StepResult:
    extract(ctx)
    rows = sum(read_delta(ctx.lake_root, f"staging.{name}").num_rows for name in STAGING_SCHEMAS)
    return StepResult(rows=rows, detail={"freshness": ctx.freshness, "files": len(STAGING_SCHEMAS)})


def _transform(ctx: RunContext) -> StepResult:
    transform(ctx)
    return StepResult(rows=read_delta(ctx.lake_root, "staging.batch_stage").num_rows)


def _notify(ctx: RunContext) -> StepResult:
    """The webhook never fails the run (F07-FR-04): whatever goes wrong becomes ``notify_status = failed``."""
    try:
        return notify(ctx)
    except Exception as error:  # by contract no webhook problem may fail a published run
        log.warning("notify raised %s: %s", type(error).__name__, error)
        return StepResult(notify_status="failed", detail={"error": f"{type(error).__name__}: {error}"})


STEP_FUNCTIONS: dict[str, StepFunction] = {
    "extract": _extract,
    "transform": _transform,
    "snapshot_aggregate": snapshot_aggregate,
    "publish": publish,
    "notify": _notify,
}


def execute_step(
    ctx: RunContext, step: str, functions: Mapping[str, StepFunction] | None = None
) -> StepResult:
    """Run one step after ``setup`` and append its log row."""
    function = (functions or STEP_FUNCTIONS)[step]
    return run_step(ctx, step, lambda: function(ctx))


def context_from_env(run_id: str, snapshot_date_iso: str) -> RunContext:
    """What a Dagster op rebuilds from the two values it is handed (OQ-046)."""
    from datetime import date

    profile = load_profile(os.environ.get("SITE_PROFILE", "site_a"))
    lake = Path(os.environ.get("LAKEHOUSE_PATH", "./lakehouse"))
    return new_context(profile, lake, run_id=run_id, snapshot_date=date.fromisoformat(snapshot_date_iso))


def run_pipeline(
    profile: SiteProfile,
    lake_root: Path,
    *,
    run_id: str | None = None,
    dsns: SourceDsns | None = None,
    functions: Mapping[str, StepFunction] | None = None,
) -> RunContext:
    """Run setup and the five steps in order; the first failure is logged and re-raised."""
    ctx = setup(profile, lake_root, run_id=run_id, dsns=dsns)
    for step in STEPS[1:]:
        execute_step(ctx, step, functions)
    return ctx
