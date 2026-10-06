"""Row content hashes: what changed between two successful snapshots (F21-FR-01).

``row_hash`` covers every column of the snapshot except the ones listed in ``HASH_EXCLUDED``, so it moves
only when a business or fact value of the lot moves. ``intelligence.row_hash_last`` holds the hashes of the
previous **successful** run. ``snapshot_aggregate`` compares against it and ``publish`` rewrites it once
everything is published, so a failed run never moves it and a same-day re-run compares correctly (OQ-129).
"""

from pathlib import Path

import duckdb
import pyarrow as pa

from r2r_pipeline.context import RunContext
from r2r_pipeline.lake import delta_exists, read_delta, write_delta
from r2r_pipeline.sql_shim import expand_macros

ROW_HASH_LAST = "intelligence.row_hash_last"
# Not part of the content: the key itself, the run's own stamps and the hash.
HASH_EXCLUDED = ("row_key", "snapshot_date", "run_id", "published_at", "row_hash")

ROW_HASH_LAST_SCHEMA = pa.schema(
    [("row_key", pa.string()), ("row_hash", pa.string()), ("pipeline_run_id", pa.string())]
)


def hashed_columns(table: pa.Table) -> list[str]:
    return sorted(name for name in table.schema.names if name not in HASH_EXCLUDED)


def add_row_hash(ctx: RunContext, snapshot: pa.Table) -> pa.Table:
    """The snapshot plus a ``row_hash`` column, computed with the ``row_hash()`` macro in DuckDB."""
    columns = ", ".join(f'"{name}"' for name in hashed_columns(snapshot))
    sql = expand_macros(
        f"SELECT row_key, row_hash({columns}) AS row_hash FROM snapshot", "duckdb", ctx.profile.site.timezone
    )
    connection = duckdb.connect()
    try:
        connection.register("snapshot", snapshot)
        hashes = connection.execute(sql).to_arrow_table()
    finally:
        connection.close()
    by_key = dict(zip(hashes["row_key"].to_pylist(), hashes["row_hash"].to_pylist(), strict=True))
    return snapshot.append_column(
        "row_hash", pa.array([by_key[key] for key in snapshot["row_key"].to_pylist()], pa.string())
    )


def count_inserted(lake_root: Path, snapshot: pa.Table) -> int:
    """Rows that are new or whose hash differs from the previous successful run's."""
    if not delta_exists(lake_root, ROW_HASH_LAST):
        return int(snapshot.num_rows)
    last = read_delta(lake_root, ROW_HASH_LAST)
    known = dict(zip(last["row_key"].to_pylist(), last["row_hash"].to_pylist(), strict=True))
    pairs = zip(snapshot["row_key"].to_pylist(), snapshot["row_hash"].to_pylist(), strict=True)
    return int(sum(1 for key, value in pairs if known.get(key) != value))


def write_last(ctx: RunContext, snapshot: pa.Table) -> None:
    """Replace ``row_hash_last`` with this run's hashes. Called by ``publish`` after the last object."""
    count = snapshot.num_rows
    table = pa.table(
        {
            "row_key": snapshot["row_key"],
            "row_hash": snapshot["row_hash"],
            "pipeline_run_id": pa.array([ctx.run_id] * count, pa.string()),
        },
        schema=ROW_HASH_LAST_SCHEMA,
    )
    write_delta(ctx.lake_root, ROW_HASH_LAST, table)
