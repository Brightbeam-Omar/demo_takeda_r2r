"""T1: SQL macro shim and templating (F06-FR-08)."""

from datetime import date

import duckdb
import pytest
import sqlglot
from r2r_pipeline.sql_shim import expand_macros, render_template, split_arguments, sql_literal

TZ = "Europe/Dublin"


def test_f06_fr08_split_arguments_respects_parentheses_and_quotes() -> None:
    assert split_arguments("a, f(b, c), 'x,y'") == ["a", "f(b, c)", "'x,y'"]
    assert split_arguments("single") == ["single"]


@pytest.mark.parametrize(
    ("macro", "duckdb_sql", "spark_sql"),
    [
        ("date_add_days(d, 5)", "(d + 5)", "date_add(d, 5)"),
        ("date_diff_days(a, b)", "date_diff('day', b, a)", "datediff(a, b)"),
        (
            "site_date(ts)",
            "CAST(timezone('Europe/Dublin', ts) AS DATE)",
            "CAST(from_utc_timestamp(ts, 'Europe/Dublin') AS DATE)",
        ),
        ("concat_key(x, y, z)", "CONCAT_WS('|', x, y, z)", "CONCAT_WS('|', x, y, z)"),
        (
            "row_hash(x, y)",
            "md5(CONCAT_WS('|', COALESCE(CAST(x AS STRING), '~'), COALESCE(CAST(y AS STRING), '~')))",
            "md5(CONCAT_WS('|', COALESCE(CAST(x AS STRING), '~'), COALESCE(CAST(y AS STRING), '~')))",
        ),
    ],
)
def test_f06_fr08_each_macro_expands_per_dialect(macro: str, duckdb_sql: str, spark_sql: str) -> None:
    assert expand_macros(f"SELECT {macro} AS v", "duckdb", TZ) == f"SELECT {duckdb_sql} AS v"
    assert expand_macros(f"SELECT {macro} AS v", "spark", TZ) == f"SELECT {spark_sql} AS v"


@pytest.mark.parametrize("dialect", ["duckdb", "spark"])
def test_f06_fr08_expanded_sql_parses_in_its_dialect(dialect: str) -> None:
    sql = (
        "SELECT concat_key(a, b, c) AS k, row_hash(a, b, c) AS h, site_date(ts) AS d, date_diff_days(date_add_days(x, 3), y) AS n "
        "FROM t"
    )
    expanded = expand_macros(sql, dialect, TZ)
    sqlglot.parse_one(expanded, read=dialect)
    assert not any(
        name in expanded
        for name in ("date_add_days", "date_diff_days", "site_date", "concat_key", "row_hash")
    )


def test_f06_fr08_the_duckdb_forms_compute_what_the_macros_promise() -> None:
    sql = (
        "SELECT date_add_days(DATE '2026-10-12', 5) AS added, "
        "date_diff_days(DATE '2026-10-12', DATE '2026-10-01') AS diff, "
        "site_date(TIMESTAMPTZ '2026-10-11 23:30:00+00') AS local_day, "
        "concat_key('RM1', 'B1', '1000') AS key"
    )
    row = duckdb.connect().execute(expand_macros(sql, "duckdb", TZ)).fetchone()
    assert row == (date(2026, 10, 17), 11, date(2026, 10, 12), "RM1|B1|1000")  # 23:30Z is 00:30 in Dublin


def test_f21_fr01_row_hash_is_stable_and_tells_null_from_text() -> None:
    sql = "SELECT row_hash('a', 1, NULL) AS h1, row_hash('a', 1, NULL) AS h2, row_hash('a', 1, 'x') AS h3, "
    sql += "row_hash('a', 1, '~') AS h4, row_hash(DATE '2026-10-12', TRUE) AS h5"
    h1, h2, h3, h4, h5 = duckdb.connect().execute(expand_macros(sql, "duckdb", TZ)).fetchone() or ()
    assert h1 == h2 and len(h1) == 32
    assert len({h1, h3, h5}) == 3
    assert h1 == h4  # a NULL and the text "~" are the same hash: documented, the null token is "~"


def test_f06_fr08_macro_errors_are_clear() -> None:
    with pytest.raises(ValueError, match="takes 2 argument"):
        expand_macros("SELECT date_add_days(d)", "duckdb", TZ)
    with pytest.raises(ValueError, match="unbalanced"):
        expand_macros("SELECT site_date(ts", "duckdb", TZ)
    with pytest.raises(ValueError, match="at least two"):
        expand_macros("SELECT concat_key(a)", "duckdb", TZ)
    with pytest.raises(ValueError, match="unknown dialect"):
        expand_macros("SELECT 1", "oracle", TZ)


def test_f06_sql_literals_and_templates() -> None:
    assert sql_literal("A") == "'A'"
    assert sql_literal("it's") == "'it''s'"
    assert sql_literal(["A", "A4"]) == "('A', 'A4')"
    assert sql_literal([]) == "(NULL)"
    assert sql_literal(date(2026, 10, 12)) == "DATE '2026-10-12'"
    assert render_template("x IN {{ codes | sql }}", codes=["A", "A4"]) == "x IN ('A', 'A4')"
    with pytest.raises(Exception, match="missing"):
        render_template("{{ missing }}")
