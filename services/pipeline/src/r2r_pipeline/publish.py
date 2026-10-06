"""The ``publish`` step: overwrite every ``published.*_v`` object of 04-data-contracts section 4 (F07-FR-03).

Each object is written straight to its final Delta table (an overwrite is atomic per table) in the order of
the contract, and ``pipeline_status_v`` goes **last**: when it shows a run id, every other object of that run
is already there. A crash inside this step can leave a mix of runs; the objects that carry a ``run_id`` let a
reader detect it (OQ-047). Nothing is published unless this run's snapshot and metrics were built.
"""

import json
from datetime import datetime

import pyarrow as pa
import pyarrow.compute as pc
from r2r_core import clock
from r2r_core.profile import SiteProfile

from r2r_pipeline.context import RunContext
from r2r_pipeline.lake import read_delta, write_delta
from r2r_pipeline.runlog import StepResult, step_detail, step_row
from r2r_pipeline.snapshot import BATCH_SNAPSHOT, WEEKLY_METRIC_ROWS, WEEKLY_METRICS

STAMP = pa.timestamp("us", tz="UTC")

# Columns of batch_pipeline_v after the batch_flat business columns (04 section 4.1), in contract order.
STAGE_COLUMNS = (
    "stage_key", "stage_rule_id", "cycle_start_date", "ud_effective", "stage_sort",
    "current_stage_entry_date", "lims_rejected",
    "receipt_entry", "receipt_exit", "call_off_entry", "call_off_exit", "sampling_entry", "sampling_exit",
    "qc_ship_entry", "qc_ship_exit", "qc_testing_entry", "qc_testing_exit", "qa_release_entry",
    "qa_release_exit", "applicable_sla_json", "source_refs_json", "system_need_by_locked", "on_hold",
    "erp_blocked", "re_eval", "offsite", "full_spec", "ud_rejected", "deviation_light", "inbound_light",
)  # fmt: skip

PUBLISH_ORDER = (
    "batch_pipeline_v",
    "weekly_metrics_v",
    "weekly_metric_rows_v",
    "stage_reference_v",
    "metric_reference_v",
    "reason_codes_v",
    "deviations_v",
    "expected_deliveries_v",
    "pipeline_status_v",
)
OBJECTS_WITH_RUN_ID = (
    "batch_pipeline_v",
    "weekly_metrics_v",
    "weekly_metric_rows_v",
    "expected_deliveries_v",
    "pipeline_status_v",
)


def published_name(name: str) -> str:
    return f"published.{name}"


def build_batch_pipeline(ctx: RunContext, published_at: datetime) -> pa.Table:
    snapshot = read_delta(ctx.lake_root, BATCH_SNAPSHOT)
    snapshot = snapshot.filter(pc.equal(snapshot["snapshot_date"], pa.scalar(ctx.snapshot_date, pa.date32())))
    if snapshot.num_rows and set(snapshot["run_id"].to_pylist()) != {ctx.run_id}:
        raise RuntimeError(f"batch_snapshot for {ctx.snapshot_date} was not built by run {ctx.run_id}")
    flat = read_delta(ctx.lake_root, "staging.batch_flat")
    columns = [*flat.schema.names, *STAGE_COLUMNS, "snapshot_date", "run_id"]
    table = snapshot.select(columns)
    stamp = pa.array([published_at] * table.num_rows, STAMP)
    return table.append_column("published_at", stamp)


def build_metrics(ctx: RunContext, table: str) -> pa.Table:
    result = read_delta(ctx.lake_root, table)
    if result.num_rows and set(result["run_id"].to_pylist()) != {ctx.run_id}:
        raise RuntimeError(f"{table} was not built by run {ctx.run_id}")
    return result


def build_stage_reference(profile: SiteProfile) -> pa.Table:
    return pa.Table.from_pylist(
        [
            {
                "stage_key": stage.key,
                "label": stage.label,
                "sort": number,
                "sla_days": stage.sla_days,
                "reeval_sla_days": profile.reeval_sla_overrides.get(stage.key),
                "team": stage.team,
                "action": stage.action,
                "terminal": stage.terminal,
                "show_card": stage.show_card,
            }
            for number, stage in enumerate(profile.stages, start=1)
        ],
        schema=pa.schema(
            [
                ("stage_key", pa.string()),
                ("label", pa.string()),
                ("sort", pa.int64()),
                ("sla_days", pa.int64()),
                ("reeval_sla_days", pa.int64()),
                ("team", pa.string()),
                ("action", pa.string()),
                ("terminal", pa.bool_()),
                ("show_card", pa.bool_()),
            ]
        ),
    )


def build_metric_reference(profile: SiteProfile) -> pa.Table:
    """Every metric of the profile; the app-side ones are ``awaiting_signal`` with the profile's reason."""
    rows = []
    for metric in profile.metrics:
        sla = metric.sla_days if metric.stage is None else profile.stage(metric.stage).sla_days
        active = metric.computed_in == "pipeline"
        rows.append(
            {
                "metric_id": metric.id,
                "label": metric.label,
                "stage_key": metric.stage,
                "sla_days": sla,
                "computed_in": metric.computed_in,
                "status": "active" if active else "awaiting_signal",
                "null_reason": None if active else metric.null_reason,
            }
        )
    schema = pa.schema(
        [
            ("metric_id", pa.string()),
            ("label", pa.string()),
            ("stage_key", pa.string()),
            ("sla_days", pa.int64()),
            ("computed_in", pa.string()),
            ("status", pa.string()),
            ("null_reason", pa.string()),
        ]
    )
    return pa.Table.from_pylist(rows, schema=schema)


def reason_label(code: str) -> str:
    return code.replace("_", " ").capitalize()


def build_reason_codes(profile: SiteProfile) -> pa.Table:
    return pa.table(
        {
            "code": pa.array(profile.reason_codes, pa.string()),
            "label": pa.array([reason_label(c) for c in profile.reason_codes], pa.string()),
        }
    )


def build_deviations(ctx: RunContext) -> pa.Table:
    """One row per deviation-to-batch link, from the staged QMS tables."""
    deviations = read_delta(ctx.lake_root, "staging.stg_deviation")
    links = read_delta(ctx.lake_root, "staging.stg_deviation_link")
    joined = links.select(["deviation_no", "material_no", "batch_no"]).join(
        deviations.select(
            [
                "deviation_no",
                "title",
                "severity",
                "status",
                "opened_on",
                "closed_on",
                "root_cause_category",
                "owner",
            ]
        ),
        keys="deviation_no",
        join_type="inner",
    )
    columns = [
        "deviation_no", "material_no", "batch_no", "title", "severity", "status", "opened_on", "closed_on",
        "root_cause_category", "owner",
    ]  # fmt: skip
    return joined.select(columns).sort_by(
        [("deviation_no", "ascending"), ("material_no", "ascending"), ("batch_no", "ascending")]
    )


def build_expected_deliveries(ctx: RunContext) -> pa.Table:
    """The open PO lines of this run's transform, stamped with the run id (F17-FR-03)."""
    lines = read_delta(ctx.lake_root, "staging.expected_deliveries")
    return lines.append_column("run_id", pa.array([ctx.run_id] * lines.num_rows, pa.string()))


def build_status(ctx: RunContext, published_at: datetime, row_count: int) -> pa.Table:
    """The one-row status: written last, so its run id means every other object is complete."""
    freshness = step_detail(ctx, "extract").get("freshness", {})
    row = {
        "last_run_id": ctx.run_id,
        "started_at": step_row(ctx, "setup")["started_at"],
        "last_success_at": published_at,
        "row_count": row_count,
        "source_freshness_json": json.dumps(freshness, separators=(",", ":"), sort_keys=True),
    }
    schema = pa.schema(
        [
            ("last_run_id", pa.string()),
            ("started_at", STAMP),
            ("last_success_at", STAMP),
            ("row_count", pa.int64()),
            ("source_freshness_json", pa.string()),
        ]
    )
    return pa.Table.from_pylist([row], schema=schema)


def publish(ctx: RunContext) -> StepResult:
    """Overwrite the nine published objects, ``pipeline_status_v`` last."""
    for step in ("transform", "snapshot_aggregate"):
        step_row(ctx, step)  # raises LookupError unless this run completed it
    published_at = clock.now()
    batch = build_batch_pipeline(ctx, published_at)
    # Everything is built before anything is written, so a build error leaves published/ untouched.
    tables = {
        "batch_pipeline_v": batch,
        "weekly_metrics_v": build_metrics(ctx, WEEKLY_METRICS),
        "weekly_metric_rows_v": build_metrics(ctx, WEEKLY_METRIC_ROWS),
        "stage_reference_v": build_stage_reference(ctx.profile),
        "metric_reference_v": build_metric_reference(ctx.profile),
        "reason_codes_v": build_reason_codes(ctx.profile),
        "deviations_v": build_deviations(ctx),
        "expected_deliveries_v": build_expected_deliveries(ctx),
        "pipeline_status_v": build_status(ctx, published_at, batch.num_rows),
    }
    for name in PUBLISH_ORDER:
        write_delta(ctx.lake_root, published_name(name), tables[name])
    counts = {name: tables[name].num_rows for name in PUBLISH_ORDER}
    return StepResult(
        rows=batch.num_rows, detail={"published_at": published_at.isoformat(), "objects": counts}
    )
