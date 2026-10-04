"""T6: QMS schema [F04-FR-01, F04-FR-02]. Needs Postgres (integration)."""

from collections.abc import Callable

import pytest
from qms_sim.db import migrate
from sqlalchemy import create_engine, inspect

pytestmark = pytest.mark.integration


def test_f04_fr01_qms_tables_keys_and_indexes_follow_the_contract(
    make_test_database: Callable[[str], str],
) -> None:
    dsn = make_test_database("qms_schema")
    migrate(dsn)
    inspector = inspect(create_engine(dsn))
    assert {"deviation", "deviation_link", "counter"} <= set(inspector.get_table_names())
    assert inspector.get_pk_constraint("deviation")["constrained_columns"] == ["deviation_no"]
    assert inspector.get_pk_constraint("deviation_link")["constrained_columns"] == [
        "deviation_no", "material_no", "batch_no",
    ]  # fmt: skip
    assert ["material_no", "batch_no"] in [
        ix["column_names"] for ix in inspector.get_indexes("deviation_link")
    ]
    assert [fk["referred_table"] for fk in inspector.get_foreign_keys("deviation_link")] == ["deviation"]
    for table in ("deviation", "deviation_link", "counter"):
        column = next(c for c in inspector.get_columns(table) if c["name"] == "updated_at")
        assert column["nullable"] is False
        assert ["updated_at"] in [ix["column_names"] for ix in inspector.get_indexes(table)]
