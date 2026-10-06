"""Pipeline facts for the Reports & Metrics page (F20-FR-02): the calendar, ``pipeline_daily`` and
``releases_weekly``.

As for the metrics, the arithmetic is SQL (``sql/reports/*.sql.j2``, same portability rules). Python writes
the calendar (so no date-spine SQL is needed) and hands the SQL its small inputs.
"""

from datetime import date, timedelta
from pathlib import Path

import duckdb
import pyarrow as pa
from r2r_core.profile import SiteProfile

from r2r_pipeline.context import RunContext
from r2r_pipeline.lake import delta_exists, read_delta, write_delta
from r2r_pipeline.metrics import metric_weeks
from r2r_pipeline.sql_shim import render_file

_PACKAGE_SQL = Path(__file__).parent / "sql"
SQL_DIR = (_PACKAGE_SQL if _PACKAGE_SQL.is_dir() else Path(__file__).resolve().parents[2] / "sql") / "reports"

CALENDAR = "intelligence.calendar"
CALENDAR_DAYS = 365

PIPELINE_DAILY_SCHEMA = pa.schema(
    [
        ("day", pa.date32()),
        ("stage_key", pa.string()),
        ("open_count", pa.int64()),
        ("run_id", pa.string()),
    ]
)
RELEASES_WEEKLY_SCHEMA = pa.schema(
    [("week_start", pa.date32()), ("released_count", pa.int64()), ("run_id", pa.string())]
)


def calendar_days(snapshot_date: date) -> list[date]:
    """The last 365 days, ending on the snapshot date."""
    return [snapshot_date - timedelta(days=n) for n in range(CALENDAR_DAYS - 1, -1, -1)]


def write_calendar(ctx: RunContext) -> int:
    days = calendar_days(ctx.snapshot_date)
    write_delta(ctx.lake_root, CALENDAR, pa.table({"day": pa.array(days, pa.date32())}))
    return len(days)


def read_calendar(ctx: RunContext) -> pa.Table:
    """The calendar ``setup`` wrote for this snapshot date; written here if a caller skipped ``setup``."""
    if (
        not delta_exists(ctx.lake_root, CALENDAR)
        or read_delta(ctx.lake_root, CALENDAR)["day"][-1].as_py() != ctx.snapshot_date
    ):
        write_calendar(ctx)
    return read_delta(ctx.lake_root, CALENDAR)


def report_files() -> list[Path]:
    return sorted(p for p in SQL_DIR.iterdir() if p.name.endswith((".sql", ".sql.j2")))


def report_stages(profile: SiteProfile) -> list[str]:
    """The stages that carry entry and exit dates: every non-terminal stage with an SLA."""
    return [s.key for s in profile.stages if not s.terminal and s.sla_days > 0]


def render_report(path: Path, profile: SiteProfile) -> str:
    return render_file(path, "duckdb", profile.site.timezone, stages=report_stages(profile))


def compute_reports(ctx: RunContext, snapshot: pa.Table, calendar: pa.Table) -> tuple[pa.Table, pa.Table]:
    """``(pipeline_daily, releases_weekly)`` for the snapshot, each with the run id."""
    weeks = metric_weeks(ctx.snapshot_date)
    connection = duckdb.connect()
    connection.register("snapshot", snapshot)
    connection.register("calendar", calendar)
    connection.register(
        "metric_weeks",
        pa.table(
            {
                "week_start": pa.array([w[0] for w in weeks], pa.date32()),
                "week_end": pa.array([w[1] for w in weeks], pa.date32()),
            }
        ),
    )
    for path in report_files():
        connection.execute(render_report(path, ctx.profile))
    daily = connection.execute("SELECT * FROM pipeline_daily ORDER BY day, stage_key").to_arrow_table()
    releases = connection.execute("SELECT * FROM releases_weekly ORDER BY week_start").to_arrow_table()
    return _stamp(daily, ctx, PIPELINE_DAILY_SCHEMA), _stamp(releases, ctx, RELEASES_WEEKLY_SCHEMA)


def _stamp(table: pa.Table, ctx: RunContext, schema: pa.Schema) -> pa.Table:
    table = table.append_column("run_id", pa.array([ctx.run_id] * table.num_rows, pa.string()))
    return table.select(schema.names).cast(schema)
