"""Delta tables on the lakehouse volume: ``<root>/<layer>/<table>``, addressed as ``layer.table``."""

import shutil
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
    """Write ``table``.

    An overwrite also replaces the schema (staging, published and wholesale-rebuilt tables), and an append
    merges it (``deltalake`` ``schema_mode``), so a column added to a contract needs no lakehouse reset.
    """
    path = table_path(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "overwrite":
        write_deltalake(str(path), table, mode="overwrite", schema_mode="overwrite")
    else:
        write_deltalake(str(path), table, mode="append", schema_mode="merge")


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
    """Replace the rows where ``column = value`` and leave every other row alone (idempotent per date).

    The schema is merged: a column added since earlier runs is NULL in the rows of the other dates.
    """
    path = table_path(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_deltalake(
        str(path),
        table,
        mode="overwrite",
        partition_by=[column],
        predicate=f"{column} = '{value.isoformat()}'",
        schema_mode="merge",
    )


LAYERS = ("staging", "intelligence", "published")


def reset_lakehouse(root: Path) -> list[str]:
    """Remove every table directory under the three layers and keep the layer folders (F07-FR-06).

    Returns the names (``layer.table``) of the tables removed. A missing published table is what a reader
    treats as "no data yet".
    """
    removed: list[str] = []
    for layer in LAYERS:
        folder = root / layer
        folder.mkdir(parents=True, exist_ok=True)
        for table in sorted(p for p in folder.iterdir() if p.is_dir()):
            shutil.rmtree(table)
            removed.append(f"{layer}.{table.name}")
    return removed
