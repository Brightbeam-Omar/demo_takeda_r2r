"""``pipeline_runs_v`` and ``pipeline_run_steps_v``: the run history behind the Sync Status page (F21-FR-01).

Both are built from ``intelligence.pipeline_run_log``. A run that failed publishes nothing, so its row first
appears in the next successful run's history; it shows "no figures" (NULL inserted, total and skipped,
OQ-129). The current run is still inside ``publish`` when this is built, so its steps stop at ``publish``
(a synthetic row stands in for it) and its duration is what has elapsed so far.
"""

import json
from datetime import datetime
from typing import Any

import pyarrow as pa

from r2r_pipeline.context import RunContext
from r2r_pipeline.lake import delta_exists, read_delta
from r2r_pipeline.runlog import RUN_LOG, STATUS_FAILED, STATUS_SUCCESS, STEPS

HISTORY_LIMIT = 100
STAMP = pa.timestamp("us", tz="UTC")

PIPELINE_RUNS_SCHEMA = pa.schema(
    [
        ("pipeline_run_id", pa.string()),
        ("run_seq", pa.int64()),
        ("started_at", STAMP),
        ("duration_ms", pa.int64()),
        ("files", pa.int64()),
        ("inserted", pa.int64()),
        ("total", pa.int64()),
        ("skipped", pa.int64()),
        ("status", pa.string()),
        ("failed_step", pa.string()),
        ("run_id", pa.string()),
    ]
)
PIPELINE_RUN_STEPS_SCHEMA = pa.schema(
    [
        ("pipeline_run_id", pa.string()),
        ("step", pa.string()),
        ("status", pa.string()),
        ("started_at", STAMP),
        ("finished_at", STAMP),
        ("rows", pa.int64()),
        ("error", pa.string()),
        ("run_id", pa.string()),
    ]
)


def _detail(row: dict[str, Any]) -> dict[str, Any]:
    detail: dict[str, Any] = json.loads(row["detail_json"] or "{}")
    return detail


def _step_order(row: dict[str, Any]) -> int:
    return STEPS.index(row["step"]) if row["step"] in STEPS else len(STEPS)


def build_runs(
    ctx: RunContext, publish_started: datetime, rows_published: int, publish_elapsed_ms: int
) -> tuple[pa.Table, pa.Table]:
    """The history (newest runs, at most ``HISTORY_LIMIT``) and the steps of those runs."""
    logged = read_delta(ctx.lake_root, RUN_LOG).to_pylist() if delta_exists(ctx.lake_root, RUN_LOG) else []
    by_run: dict[str, list[dict[str, Any]]] = {}
    for row in logged:
        by_run.setdefault(row["run_id"], []).append(row)

    runs: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    for run_id, rows in by_run.items():
        rows.sort(key=_step_order)
        failed = next((r for r in rows if r["status"] == STATUS_FAILED), None)
        current = run_id == ctx.run_id
        published = any(r["step"] == "publish" and r["status"] == STATUS_SUCCESS for r in rows)
        if failed is None and not (current or published):
            continue  # started and never finished (killed); nothing to show
        by_step = {r["step"]: r for r in rows if r["status"] == STATUS_SUCCESS}
        setup = by_step.get("setup", rows[0])
        duration = sum(int(_detail(r).get("duration_ms", 0)) for r in rows)
        extract = _detail(by_step["extract"]) if "extract" in by_step else {}
        files = extract.get("files")
        snapshot = _detail(by_step["snapshot_aggregate"]) if "snapshot_aggregate" in by_step else {}
        ok = failed is None
        inserted = snapshot.get("inserted") if ok else None
        total = snapshot.get("total") if ok else None
        runs.append(
            {
                "pipeline_run_id": run_id,
                "run_seq": int(_detail(setup).get("wall_us", 0)),
                "started_at": setup["started_at"],
                "duration_ms": duration + (publish_elapsed_ms if current else 0),
                "files": files,
                "inserted": inserted,
                "total": total,
                "skipped": None if inserted is None or total is None else total - inserted,
                "status": "ok" if ok else "failed",
                "failed_step": None if failed is None else failed["step"],
                "run_id": ctx.run_id,
            }
        )
        for row in rows:
            steps.append(_step_row(ctx, run_id, row))
        if current:
            steps.append(
                {
                    "pipeline_run_id": run_id,
                    "step": "publish",
                    "status": STATUS_SUCCESS,
                    "started_at": publish_started,
                    "finished_at": publish_started,
                    "rows": rows_published,
                    "error": None,
                    "run_id": ctx.run_id,
                }
            )
    runs.sort(key=lambda r: (r["run_seq"], r["pipeline_run_id"]), reverse=True)
    kept = runs[:HISTORY_LIMIT]
    wanted = {r["pipeline_run_id"] for r in kept}
    steps = [s for s in steps if s["pipeline_run_id"] in wanted]
    steps.sort(key=lambda s: (s["pipeline_run_id"], STEPS.index(s["step"]) if s["step"] in STEPS else 99))
    return (
        pa.Table.from_pylist(kept, schema=PIPELINE_RUNS_SCHEMA),
        pa.Table.from_pylist(steps, schema=PIPELINE_RUN_STEPS_SCHEMA),
    )


def _step_row(ctx: RunContext, run_id: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "pipeline_run_id": run_id,
        "step": row["step"],
        "status": row["status"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "rows": row["rows"],
        "error": row["error"],
        "run_id": ctx.run_id,
    }
