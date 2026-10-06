"""``intelligence.pipeline_run_log``: one row per step per run (F07-FR-05).

The steps are separate Dagster ops that share only the lakehouse, so anything a later step needs from an
earlier one (the run's start time, the source freshness) is read back from this log (OQ-046).
"""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pyarrow as pa
from r2r_core import clock

from r2r_pipeline.context import RunContext
from r2r_pipeline.lake import delta_exists, read_delta, write_delta

RUN_LOG = "intelligence.pipeline_run_log"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STEPS = ("setup", "extract", "transform", "snapshot_aggregate", "publish", "notify")

RUN_LOG_SCHEMA = pa.schema(
    [
        ("run_id", pa.string()),
        ("step", pa.string()),
        ("status", pa.string()),
        ("started_at", pa.timestamp("us", tz="UTC")),
        ("finished_at", pa.timestamp("us", tz="UTC")),
        ("rows", pa.int64()),
        ("error", pa.string()),
        ("notify_status", pa.string()),
        ("detail_json", pa.string()),
    ]
)


@dataclass
class StepResult:
    """What a step reports about itself; the runner turns it into the log row."""

    rows: int | None = None
    notify_status: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


def append_log(ctx: RunContext, row: dict[str, Any]) -> None:
    write_delta(ctx.lake_root, RUN_LOG, pa.Table.from_pylist([row], schema=RUN_LOG_SCHEMA), mode="append")


def run_step(ctx: RunContext, step: str, action: Callable[[], StepResult | None]) -> StepResult:
    """Run ``action`` and append its log row. A failure is logged with its error text and re-raised."""
    started_at = clock.now()
    began = time.perf_counter()  # duration is infrastructure timing, not business time (OQ-003)
    try:
        result = action() or StepResult()
    except Exception as error:
        append_log(
            ctx,
            _row(ctx, step, STATUS_FAILED, started_at, None, f"{type(error).__name__}: {error}", {}, began),
        )
        raise
    append_log(
        ctx,
        _row(ctx, step, STATUS_SUCCESS, started_at, result, None, result.detail, began),
    )
    return result


def _row(
    ctx: RunContext,
    step: str,
    status: str,
    started_at: datetime,
    result: StepResult | None,
    error: str | None,
    detail: dict[str, Any],
    began: float,
) -> dict[str, Any]:
    detail = {
        **detail,
        "duration_ms": round((time.perf_counter() - began) * 1000),
        "wall_us": time.time_ns() // 1000,  # orders the runs: the demo clock does not tick (F21-FR-01)
    }
    return {
        "run_id": ctx.run_id,
        "step": step,
        "status": status,
        "started_at": started_at,
        "finished_at": clock.now(),
        "rows": result.rows if result else None,
        "error": error,
        "notify_status": result.notify_status if result else None,
        "detail_json": json.dumps(detail, separators=(",", ":"), sort_keys=True),
    }


def read_log(ctx: RunContext, run_id: str | None = None) -> list[dict[str, Any]]:
    """The log rows of one run (default: this run), in step order (Delta does not keep append order)."""
    if not delta_exists(ctx.lake_root, RUN_LOG):
        return []
    wanted = run_id or ctx.run_id
    rows = [r for r in read_delta(ctx.lake_root, RUN_LOG).to_pylist() if r["run_id"] == wanted]
    return sorted(rows, key=lambda r: STEPS.index(r["step"]) if r["step"] in STEPS else len(STEPS))


def step_row(ctx: RunContext, step: str) -> dict[str, Any]:
    """This run's successful row for ``step``; later steps use it to read what an earlier one recorded."""
    for row in read_log(ctx):
        if row["step"] == step and row["status"] == STATUS_SUCCESS:
            return row
    raise LookupError(f"run {ctx.run_id} has no successful {step!r} step in the run log")


def step_detail(ctx: RunContext, step: str) -> dict[str, Any]:
    detail: dict[str, Any] = json.loads(step_row(ctx, step)["detail_json"] or "{}")
    return detail
