"""Delta tables on the lakehouse volume: ``<root>/<layer>/<table>``, addressed as ``layer.table``."""

from datetime import date
from pathlib import Path

import duckdb
import pyarrow as pa
from deltalake import DeltaTable, write_deltalake


def table_path(root: Path, name: str) -> Path:
    layer, _, table = name.partition(".")
    if not table:
        raise ValueError(f"table name must be 'layer.table' (got {name!r})")
    return root / layer / table


def write_delta(root: Path, name: str, table: pa.Table, mode: str = "overwrite") -> None:
    """Write ``table``; an overwrite also replaces the schema (staging tables are rebuilt every run)."""
    path = table_path(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "overwrite":
        write_deltalake(str(path), table, mode="overwrite", schema_mode="overwrite")
    else:
        write_deltalake(str(path), table, mode="append")


def read_delta(root: Path, name: str) -> pa.Table:
    path = table_path(root, name)
    if not path.exists():
        raise FileNotFoundError(f"no Delta table {name} under {root}")
    return DeltaTable(str(path)).to_pyarrow_table()


def delta_exists(root: Path, name: str) -> bool:
    return (table_path(root, name) / "_delta_log").is_dir()


def register(connection: duckdb.DuckDBPyConnection, root: Path, name: str, alias: str | None = None) -> None:
    """Make a Delta table queryable in DuckDB as ``alias`` (default: the table part of ``name``)."""
    connection.register(alias or name.partition(".")[2], read_delta(root, name))


def replace_partition(root: Path, name: str, table: pa.Table, column: str, value: date) -> None:
    """Replace the rows where ``column = value`` and leave every other row alone (idempotent per date)."""
    path = table_path(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_deltalake(
        str(path),
        table,
        mode="overwrite",
        partition_by=[column],
        predicate=f"{column} = '{value.isoformat()}'",
    )
