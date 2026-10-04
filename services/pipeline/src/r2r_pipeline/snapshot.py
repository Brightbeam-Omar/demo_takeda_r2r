"""The ``snapshot_aggregate`` step: ``intelligence.batch_snapshot`` and the need-by history (F07-FR-01).

``batch_snapshot`` is ``batch_flat`` joined to ``batch_stage`` for one snapshot date. A run replaces only
its own date's partition, so running twice on the same demo day gives the same rows. ``need_by_history``
remembers the first non-null ``system_need_by_date`` of every row and never changes it;
``system_need_by_locked`` is that value (OQ-045).
"""

import pyarrow as pa
import pyarrow.compute as pc

from r2r_pipeline.context import RunContext
from r2r_pipeline.lake import delta_exists, read_delta, replace_partition, write_delta
from r2r_pipeline.runlog import StepResult

BATCH_SNAPSHOT = "intelligence.batch_snapshot"
NEED_BY_HISTORY = "intelligence.need_by_history"

NEED_BY_HISTORY_SCHEMA = pa.schema(
    [
        ("row_key", pa.string()),
        ("system_need_by_date", pa.date32()),
        ("first_seen_date", pa.date32()),
        ("run_id", pa.string()),
    ]
)


def read_history(ctx: RunContext) -> pa.Table:
    if delta_exists(ctx.lake_root, NEED_BY_HISTORY):
        return read_delta(ctx.lake_root, NEED_BY_HISTORY)
    return NEED_BY_HISTORY_SCHEMA.empty_table()


def lock_need_by(ctx: RunContext, flat: pa.Table) -> tuple[pa.Table, int]:
    """Lock the first non-null need-by of new rows; return the whole history and the number of new rows."""
    history = read_history(ctx)
    known = history["row_key"]
    candidates = flat.filter(
        pc.and_(
            pc.is_valid(flat["system_need_by_date"]),
            pc.invert(pc.is_in(flat["row_key"], value_set=known)),
        )
    )
    new = pa.table(
        {
            "row_key": candidates["row_key"],
            "system_need_by_date": candidates["system_need_by_date"],
            "first_seen_date": pa.array([ctx.snapshot_date] * candidates.num_rows, pa.date32()),
            "run_id": pa.array([ctx.run_id] * candidates.num_rows, pa.string()),
        },
        schema=NEED_BY_HISTORY_SCHEMA,
    )
    if new.num_rows or not delta_exists(ctx.lake_root, NEED_BY_HISTORY):
        write_delta(ctx.lake_root, NEED_BY_HISTORY, new, mode="append")
    return pa.concat_tables([history, new]), new.num_rows


def build_snapshot(ctx: RunContext, flat: pa.Table, stage: pa.Table, history: pa.Table) -> pa.Table:
    """Flat and stage joined on ``row_key``, plus ``snapshot_date``, ``run_id`` and the locked need-by."""
    joined = flat.join(stage, keys="row_key", join_type="inner").sort_by("row_key")
    locked = dict(
        zip(history["row_key"].to_pylist(), history["system_need_by_date"].to_pylist(), strict=True)
    )
    count = joined.num_rows
    joined = joined.append_column("snapshot_date", pa.array([ctx.snapshot_date] * count, pa.date32()))
    joined = joined.append_column("run_id", pa.array([ctx.run_id] * count, pa.string()))
    return joined.append_column(
        "system_need_by_locked",
        pa.array([locked.get(key) for key in joined["row_key"].to_pylist()], pa.date32()),
    )


def snapshot_aggregate(ctx: RunContext) -> StepResult:
    flat = read_delta(ctx.lake_root, "staging.batch_flat")
    stage = read_delta(ctx.lake_root, "staging.batch_stage")
    history, inserted = lock_need_by(ctx, flat)
    snapshot = build_snapshot(ctx, flat, stage, history)
    replace_partition(ctx.lake_root, BATCH_SNAPSHOT, snapshot, "snapshot_date", ctx.snapshot_date)
    return StepResult(rows=snapshot.num_rows, detail={"need_by_locked_new": inserted})
