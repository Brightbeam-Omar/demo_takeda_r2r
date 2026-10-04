"""T5: LIMS schema [F04-FR-01, F04-FR-02]. Needs Postgres (integration)."""

from collections.abc import Callable

import pytest
from lims_sim.db import migrate
from sqlalchemy import create_engine, inspect

pytestmark = pytest.mark.integration


def test_f04_fr01_lims_tables_keys_and_indexes_follow_the_contract(
    make_test_database: Callable[[str], str],
) -> None:
    dsn = make_test_database("lims_schema")
    migrate(dsn)
    inspector = inspect(create_engine(dsn))
    assert {"sample", "test_result", "counter"} <= set(inspector.get_table_names())
    assert inspector.get_pk_constraint("sample")["constrained_columns"] == ["sample_id"]
    assert inspector.get_pk_constraint("test_result")["constrained_columns"] == ["id"]
    sample_indexes = [ix["column_names"] for ix in inspector.get_indexes("sample")]
    assert ["material_no", "batch_no"] in sample_indexes
    assert [fk["referred_table"] for fk in inspector.get_foreign_keys("test_result")] == ["sample"]
    for table in ("sample", "test_result", "counter"):
        column = next(c for c in inspector.get_columns(table) if c["name"] == "updated_at")
        assert column["nullable"] is False
        assert ["updated_at"] in [ix["column_names"] for ix in inspector.get_indexes(table)]
