"""T2: ERP schema and migration [F04-FR-01, F04-FR-02]. Needs Postgres (integration)."""

from collections.abc import Callable, Iterator

import pytest
from erp_sim.db import migrate
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine.reflection import Inspector

pytestmark = pytest.mark.integration

TABLES = {"mara", "lfa1", "t001l", "mcha", "mchb", "mseg", "qals", "zinbchk", "mdez", "counter"}


@pytest.fixture(scope="module")
def inspector(make_test_database: Callable[[str], str]) -> Iterator[Inspector]:
    dsn = make_test_database("erp_sim")
    migrate(dsn)
    engine = create_engine(dsn)
    yield inspect(engine)
    engine.dispose()


def test_f04_fr01_migration_creates_the_erp_tables(inspector: Inspector) -> None:
    assert set(inspector.get_table_names()) >= TABLES


def test_f04_fr02_every_table_has_a_not_null_timestamptz_updated_at_with_an_index(
    inspector: Inspector,
) -> None:
    for table in TABLES:
        column = next(c for c in inspector.get_columns(table) if c["name"] == "updated_at")
        assert column["nullable"] is False, table
        assert getattr(column["type"], "timezone", False) is True, table
        indexed = [ix["column_names"] for ix in inspector.get_indexes(table)]
        assert ["updated_at"] in indexed, table


def test_f04_fr01_keys_match_the_data_contract(inspector: Inspector) -> None:
    keys = {t: inspector.get_pk_constraint(t)["constrained_columns"] for t in TABLES}
    assert keys["mara"] == ["matnr"]
    assert keys["lfa1"] == ["lifnr"]
    assert keys["t001l"] == ["lgort"]
    assert keys["mcha"] == ["matnr", "charg"]
    assert keys["mchb"] == ["matnr", "charg", "lgort"]
    assert keys["mseg"] == ["mblnr", "zeile"]
    assert keys["qals"] == ["prueflos"]
    assert keys["zinbchk"] == ["prueflos"]
    assert keys["mdez"] == ["id"]


def test_f04_fr01_mseg_has_a_quantity_column(inspector: Inspector) -> None:
    menge = next(c for c in inspector.get_columns("mseg") if c["name"] == "menge")
    assert menge["nullable"] is False
    assert (menge["type"].precision, menge["type"].scale) == (13, 3)


def test_f04_fr01_foreign_keys_follow_the_contract(inspector: Inspector) -> None:
    def targets(table: str) -> set[tuple[str, tuple[str, ...]]]:
        return {
            (fk["referred_table"], tuple(fk["constrained_columns"]))
            for fk in inspector.get_foreign_keys(table)
        }

    assert targets("mcha") == {("mara", ("matnr",)), ("lfa1", ("lifnr",))}
    assert targets("mchb") == {("mcha", ("matnr", "charg")), ("t001l", ("lgort",))}
    assert targets("mseg") == {("mcha", ("matnr", "charg")), ("t001l", ("lgort",)), ("t001l", ("umlgo",))}
    assert targets("qals") == {("mcha", ("matnr", "charg"))}
    assert targets("zinbchk") == {("qals", ("prueflos",))}
    assert targets("mdez") == {("mara", ("matnr",))}


def test_f04_fr01_batch_columns_are_indexed_where_present(inspector: Inspector) -> None:
    for table in ("mseg", "qals"):
        assert ["matnr", "charg"] in [ix["column_names"] for ix in inspector.get_indexes(table)], table
    # mchb and mcha lead with (matnr, charg) in their primary key.
    assert inspector.get_pk_constraint("mchb")["constrained_columns"][:2] == ["matnr", "charg"]


def test_f04_fr01_migration_is_repeatable(make_test_database: Callable[[str], str]) -> None:
    dsn = make_test_database("erp_sim_again")
    migrate(dsn)
    migrate(dsn)  # already at head: a no-op
