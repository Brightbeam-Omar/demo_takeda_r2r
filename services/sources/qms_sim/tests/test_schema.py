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
    assert {"deviation", "deviation_link", "change_control", "change_control_link", "counter"} <= set(
        inspector.get_table_names()
    )
    assert inspector.get_pk_constraint("deviation")["constrained_columns"] == ["deviation_no"]
    assert inspector.get_pk_constraint("deviation_link")["constrained_columns"] == [
        "deviation_no", "material_no", "batch_no",
    ]  # fmt: skip
    assert ["material_no", "batch_no"] in [
        ix["column_names"] for ix in inspector.get_indexes("deviation_link")
    ]
    assert [fk["referred_table"] for fk in inspector.get_foreign_keys("deviation_link")] == ["deviation"]
    for table in ("deviation", "deviation_link", "change_control", "change_control_link", "counter"):
        column = next(c for c in inspector.get_columns(table) if c["name"] == "updated_at")
        assert column["nullable"] is False
        assert ["updated_at"] in [ix["column_names"] for ix in inspector.get_indexes(table)]


def test_f19_fr03_change_control_tables_deviation_fields_and_severity_vocabulary(
    make_test_database: Callable[[str], str],
) -> None:
    dsn = make_test_database("qms_schema_f19")
    migrate(dsn)
    inspector = inspect(create_engine(dsn))
    assert inspector.get_pk_constraint("change_control")["constrained_columns"] == ["cc_no"]
    assert inspector.get_pk_constraint("change_control_link")["constrained_columns"] == [
        "cc_no", "material_no", "batch_no",
    ]  # fmt: skip
    assert ["material_no", "batch_no"] in [
        ix["column_names"] for ix in inspector.get_indexes("change_control_link")
    ]
    columns = {c["name"]: c for c in inspector.get_columns("deviation")}
    assert columns["causal_factor"]["nullable"] is True
    assert columns["investigation_summary"]["nullable"] is True
    checks = {c["name"]: c["sqltext"] for c in inspector.get_check_constraints("deviation")}
    assert "moderate" in checks["ck_deviation_severity"] and "critical" not in checks["ck_deviation_severity"]
    cc = {c["name"] for c in inspector.get_columns("change_control")}
    assert cc >= {"cc_no", "title", "status", "current_state", "proposed_state", "opened_on", "effective_on"}
