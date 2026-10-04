"""T1: Delta helpers and run context."""

from datetime import date
from pathlib import Path

import duckdb
import pyarrow as pa
import pytest
from r2r_core.profile import load_profile
from r2r_pipeline.context import new_context
from r2r_pipeline.lake import delta_exists, read_delta, register, table_path, write_delta


def test_f06_fr01_write_read_overwrite_and_query_in_duckdb(tmp_path: Path) -> None:
    write_delta(tmp_path, "staging.stg_demo", pa.table({"a": [1, 2], "b": ["x", "y"]}))
    assert delta_exists(tmp_path, "staging.stg_demo")
    assert read_delta(tmp_path, "staging.stg_demo").num_rows == 2
    write_delta(tmp_path, "staging.stg_demo", pa.table({"a": [3], "c": [1.5]}))  # new schema replaces the old
    assert read_delta(tmp_path, "staging.stg_demo").column_names == ["a", "c"]
    connection = duckdb.connect()
    register(connection, tmp_path, "staging.stg_demo")
    assert connection.execute("SELECT a FROM stg_demo").fetchall() == [(3,)]


def test_f06_fr01_missing_tables_and_bad_names_are_clear(tmp_path: Path) -> None:
    assert not delta_exists(tmp_path, "staging.nothing")
    with pytest.raises(FileNotFoundError, match="staging\\.nothing"):
        read_delta(tmp_path, "staging.nothing")
    with pytest.raises(ValueError, match="layer\\.table"):
        table_path(tmp_path, "nodot")


def test_f06_fr09_context_defaults_to_the_demo_today_and_a_uuid_run_id(tmp_path: Path) -> None:
    profile = load_profile("site_a")
    context = new_context(profile, tmp_path, snapshot_date=date(2026, 10, 12))
    assert context.snapshot_date == date(2026, 10, 12)
    assert len(context.run_id) == 36
    other = new_context(profile, tmp_path, run_id="dagster-run-1", snapshot_date=date(2026, 10, 12))
    assert other.run_id == "dagster-run-1"
