"""Dagster definitions: the ``r2r_pipeline`` job, its stopped schedule and the reset job (F07-FR-06).

One op per step: ``setup -> extract -> transform -> snapshot_aggregate -> publish -> notify``. The ops hand
each other only the run id and the snapshot date (OQ-046); every step reads the rest from the lakehouse and
the run log. ``setup`` uses the Dagster run id as the pipeline ``run_id``, so
``pipeline_status_v.last_run_id`` is the id shown in the Dagster UI.
"""

import os
from pathlib import Path
from typing import Any

from dagster import (
    DefaultScheduleStatus,
    Definitions,
    OpExecutionContext,
    ScheduleDefinition,
    job,
    op,
)
from r2r_core.profile import load_profile

from r2r_pipeline.lake import reset_lakehouse
from r2r_pipeline.pipeline import context_from_env, execute_step
from r2r_pipeline.setup import setup

RunInfo = dict[str, str]  # {"run_id": ..., "snapshot_date": ...}: all the ops pass on


def _lake_root() -> Path:
    return Path(os.environ.get("LAKEHOUSE_PATH", "./lakehouse"))


@op(name="setup")
def setup_op(context: OpExecutionContext) -> RunInfo:
    profile = load_profile(os.environ.get("SITE_PROFILE", "site_a"))
    ctx = setup(profile, _lake_root(), run_id=context.run_id)
    return {"run_id": ctx.run_id, "snapshot_date": ctx.snapshot_date.isoformat()}


def _step_op(step: str) -> Any:
    @op(name=step)
    def run_step_op(context: OpExecutionContext, run: RunInfo) -> RunInfo:
        ctx = context_from_env(run["run_id"], run["snapshot_date"])
        result = execute_step(ctx, step)
        context.log.info("%s finished: rows=%s notify_status=%s", step, result.rows, result.notify_status)
        return run

    return run_step_op


extract_op = _step_op("extract")
transform_op = _step_op("transform")
snapshot_aggregate_op = _step_op("snapshot_aggregate")
publish_op = _step_op("publish")
notify_op = _step_op("notify")


@job(name="r2r_pipeline", description="Source tables to the published contract, then the signed webhook")
def r2r_pipeline() -> None:
    notify_op(publish_op(snapshot_aggregate_op(transform_op(extract_op(setup_op())))))


@op(name="reset_lakehouse")
def reset_lakehouse_op(context: OpExecutionContext) -> None:
    removed = reset_lakehouse(_lake_root())
    context.log.info("removed %d table(s): %s", len(removed), ", ".join(removed))


@job(name="r2r_reset_lakehouse", description="Remove every Delta table from the lakehouse (demo reset)")
def r2r_reset_lakehouse() -> None:
    reset_lakehouse_op()


# Every 4 hours, defined but STOPPED: the demo clock does not tick, so runs are triggered explicitly.
every_four_hours = ScheduleDefinition(
    name="r2r_pipeline_every_4_hours",
    job=r2r_pipeline,
    cron_schedule="0 */4 * * *",
    default_status=DefaultScheduleStatus.STOPPED,
)

defs = Definitions(jobs=[r2r_pipeline, r2r_reset_lakehouse], schedules=[every_four_hours])
