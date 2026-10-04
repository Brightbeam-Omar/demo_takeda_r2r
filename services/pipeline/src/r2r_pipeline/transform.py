"""The ``transform`` step: SQL files over the staging tables build ``batch_flat`` and ``batch_stage``."""

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
from r2r_core.profile import SiteProfile

from r2r_pipeline.applicable_sla import build_applicable_sla
from r2r_pipeline.context import RunContext
from r2r_pipeline.lake import register, write_delta
from r2r_pipeline.schemas import STAGING_SCHEMAS
from r2r_pipeline.source_refs import build_source_refs
from r2r_pipeline.sql_shim import render_file
from r2r_pipeline.stage_engine import engine_variables

_PACKAGE_SQL = Path(__file__).parent / "sql"
SQL_DIR = (
    _PACKAGE_SQL if _PACKAGE_SQL.is_dir() else Path(__file__).resolve().parents[2] / "sql"
) / "transform"


def transform_files() -> list[Path]:
    """The transform SQL files in lexical order (``.sql`` and ``.sql.j2``)."""
    return sorted(p for p in SQL_DIR.iterdir() if p.name.endswith((".sql", ".sql.j2")))


def template_variables(profile: SiteProfile, snapshot_date: date) -> dict[str, Any]:
    """What the SQL templates may use: the snapshot date and everything that comes from the profile."""
    return {
        **engine_variables(profile),
        "snapshot_date": snapshot_date,
        "accept_codes": list(profile.ud_codes.accept),
        "reject_codes": list(profile.ud_codes.reject),
        "cancel_codes": list(profile.ud_codes.cancel),
        "timezone": profile.site.timezone,
        "full_spec_pairs": [(p.material, p.supplier) for p in profile.full_spec_pairs],
    }


def load_staging(connection: duckdb.DuckDBPyConnection, ctx: RunContext) -> None:
    """Make every ``staging.stg_*`` Delta table queryable by the SQL files."""
    for name in STAGING_SCHEMAS:
        register(connection, ctx.lake_root, f"staging.{name}")


def run_files(
    connection: duckdb.DuckDBPyConnection, ctx: RunContext, wanted: Callable[[Path], bool] = lambda path: True
) -> None:
    """Render and run the transform files that satisfy ``wanted``, in lexical order, in the DuckDB dialect."""
    variables = template_variables(ctx.profile, ctx.snapshot_date)
    for path in transform_files():
        if wanted(path):
            connection.execute(render_file(path, "duckdb", ctx.profile.site.timezone, **variables))


def transform(ctx: RunContext) -> None:
    """Build ``staging.batch_flat`` (input of the stage engine) and ``staging.batch_stage`` (its output)."""
    connection = duckdb.connect()
    load_staging(connection, ctx)
    run_files(connection, ctx)
    flat = connection.execute("SELECT * FROM batch_flat ORDER BY row_key").to_arrow_table()
    write_delta(ctx.lake_root, "staging.batch_flat", flat)
    stage = connection.execute("SELECT * FROM batch_stage_sql ORDER BY row_key").to_arrow_table()
    refs = build_source_refs(
        flat,
        connection.execute("SELECT * FROM stg_mseg").to_arrow_table(),
        connection.execute("SELECT * FROM stg_deviation_link").to_arrow_table(),
    )
    keys = stage["row_key"].to_pylist()
    slas = build_applicable_sla(flat, stage, ctx.profile)
    position = stage.column_names.index("on_hold")
    stage = stage.add_column(position, "applicable_sla_json", pa.array([slas[key] for key in keys]))
    stage = stage.append_column("source_refs_json", pa.array([refs[key] for key in keys]))
    write_delta(ctx.lake_root, "staging.batch_stage", stage)
