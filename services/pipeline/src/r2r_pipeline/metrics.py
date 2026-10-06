"""Weekly metrics for the pipeline-side metrics (F07-FR-02, 03-domain-model section 7).

The arithmetic is SQL (``sql/metrics/*.sql.j2``, same portability rules as the transforms). Python only
prepares the two small inputs the SQL joins to, so that no date truncation or JSON function is needed in SQL:

* ``metric_weeks``: the ISO weeks to publish, relative to the snapshot date;
* ``row_sla``: ``applicable_sla_json`` exploded to one row per row key and stage.
"""

import json
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pyarrow as pa
from r2r_core.profile import Metric, SiteProfile

from r2r_pipeline.context import RunContext
from r2r_pipeline.sql_shim import render_file

_PACKAGE_SQL = Path(__file__).parent / "sql"
SQL_DIR = (_PACKAGE_SQL if _PACKAGE_SQL.is_dir() else Path(__file__).resolve().parents[2] / "sql") / "metrics"

COMPLETE_WEEKS = 52  # F20-FR-02 (was 12)
COMPLETE_MONTHS = 12

WEEKLY_METRICS_SCHEMA = pa.schema(
    [
        ("metric_id", pa.string()),
        ("week_start", pa.date32()),
        ("completed", pa.int64()),
        ("on_time", pa.int64()),
        ("pct", pa.decimal128(5, 1)),
        ("run_id", pa.string()),
    ]
)
MONTHLY_METRICS_SCHEMA = pa.schema(
    [
        ("metric_id", pa.string()),
        ("month_start", pa.date32()),
        ("completed", pa.int64()),
        ("on_time", pa.int64()),
        ("pct", pa.decimal128(5, 1)),
        ("run_id", pa.string()),
    ]
)
WEEKLY_METRIC_ROWS_SCHEMA = pa.schema(
    [
        ("metric_id", pa.string()),
        ("week_start", pa.date32()),
        ("row_key", pa.string()),
        ("entry_date", pa.date32()),
        ("exit_date", pa.date32()),
        ("duration_days", pa.int64()),
        ("sla_days", pa.int64()),
        ("on_time", pa.bool_()),
        ("run_id", pa.string()),
    ]
)


def metric_files() -> list[Path]:
    return sorted(p for p in SQL_DIR.iterdir() if p.name.endswith((".sql", ".sql.j2")))


def pipeline_metrics(profile: SiteProfile) -> list[Metric]:
    """The metrics whose signal is in the pipeline and that are tied to a stage."""
    return [m for m in profile.metrics if m.computed_in == "pipeline" and m.stage is not None]


def metric_weeks(snapshot_date: date) -> list[tuple[date, date]]:
    """``(week_start, week_end)`` of the 52 complete ISO weeks before the snapshot's week, then that week to
    date. ``week_end`` is exclusive; for the current week it is the day after the snapshot date."""
    current = snapshot_date - timedelta(days=snapshot_date.weekday())
    weeks = [
        (current - timedelta(weeks=n), current - timedelta(weeks=n - 1)) for n in range(COMPLETE_WEEKS, 0, -1)
    ]
    return [*weeks, (current, snapshot_date + timedelta(days=1))]


def _add_months(first_of_month: date, months: int) -> date:
    index = first_of_month.year * 12 + first_of_month.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def metric_months(snapshot_date: date) -> list[tuple[date, date]]:
    """``(month_start, month_end)`` of the 12 complete calendar months before the snapshot's month, then that
    month to date. ``month_end`` is exclusive; for the current month it is the day after the snapshot date."""
    current = snapshot_date.replace(day=1)
    months = [(_add_months(current, -n), _add_months(current, -n + 1)) for n in range(COMPLETE_MONTHS, 0, -1)]
    return [*months, (current, snapshot_date + timedelta(days=1))]


def sla_rows(snapshot: pa.Table) -> pa.Table:
    """``applicable_sla_json`` as ``(row_key, stage_key, sla_days)`` rows."""
    out: list[dict[str, object]] = []
    for key, text in zip(
        snapshot["row_key"].to_pylist(), snapshot["applicable_sla_json"].to_pylist(), strict=True
    ):
        out.extend(
            {"row_key": key, "stage_key": item["stage_key"], "sla_days": item["sla_days"]}
            for item in json.loads(text)
        )
    schema = pa.schema([("row_key", pa.string()), ("stage_key", pa.string()), ("sla_days", pa.int64())])
    return pa.Table.from_pylist(out, schema=schema)


def compute_metrics(ctx: RunContext, snapshot: pa.Table) -> tuple[pa.Table, pa.Table, pa.Table]:
    """``(weekly_metrics, weekly_metric_rows, monthly_metrics)`` for the snapshot, each with the run id."""
    weeks = metric_weeks(ctx.snapshot_date)
    months = metric_months(ctx.snapshot_date)
    connection = duckdb.connect()
    connection.register("snapshot", snapshot)
    connection.register("row_sla", sla_rows(snapshot))
    connection.register(
        "metric_weeks",
        pa.table(
            {
                "week_start": pa.array([w[0] for w in weeks], pa.date32()),
                "week_end": pa.array([w[1] for w in weeks], pa.date32()),
            }
        ),
    )
    connection.register(
        "metric_months",
        pa.table(
            {
                "month_start": pa.array([m[0] for m in months], pa.date32()),
                "month_end": pa.array([m[1] for m in months], pa.date32()),
            }
        ),
    )
    for path in metric_files():
        connection.execute(
            render_file(path, "duckdb", ctx.profile.site.timezone, metrics=pipeline_metrics(ctx.profile))
        )
    weekly = connection.execute(
        "SELECT * FROM weekly_metrics ORDER BY metric_id, week_start"
    ).to_arrow_table()
    rows = connection.execute(
        "SELECT * FROM metric_rows ORDER BY metric_id, week_start, row_key"
    ).to_arrow_table()
    monthly = connection.execute(
        "SELECT * FROM monthly_metrics ORDER BY metric_id, month_start"
    ).to_arrow_table()
    return (
        _with_run_id(weekly, ctx, WEEKLY_METRICS_SCHEMA),
        _with_run_id(rows, ctx, WEEKLY_METRIC_ROWS_SCHEMA),
        _with_run_id(monthly, ctx, MONTHLY_METRICS_SCHEMA),
    )


def _with_run_id(table: pa.Table, ctx: RunContext, schema: pa.Schema) -> pa.Table:
    table = table.append_column("run_id", pa.array([ctx.run_id] * table.num_rows, pa.string()))
    return table.select(schema.names).cast(schema)
