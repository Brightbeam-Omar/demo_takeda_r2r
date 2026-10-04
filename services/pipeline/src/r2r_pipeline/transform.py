"""The ``transform`` step: SQL files over the staging tables build ``batch_flat`` and ``batch_stage``."""

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
from r2r_core.profile import SiteProfile

from r2r_pipeline.context import RunContext
from r2r_pipeline.lake import register, write_delta
from r2r_pipeline.schemas import STAGING_SCHEMAS
from r2r_pipeline.sql_shim import render_file

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
    """Build ``staging.batch_flat`` from the staging tables."""
    connection = duckdb.connect()
    load_staging(connection, ctx)
    run_files(connection, ctx, lambda path: path.name[:2] < "50")
    write_delta(
        ctx.lake_root,
        "staging.batch_flat",
        connection.execute("SELECT * FROM batch_flat").to_arrow_table(),
    )
