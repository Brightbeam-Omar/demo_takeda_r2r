"""T2 [TDD]: the sqlglot portability harness (F06-FR-08, F06-AC-07)."""

import pytest
from r2r_core.profile import SiteProfile
from r2r_pipeline.portability import ALLOWED_FUNCTIONS, check_sql
from r2r_pipeline.transform import template_variables, transform_files

TZ = "Europe/Dublin"

GOOD = """
CREATE OR REPLACE TABLE t AS
WITH ranked AS (
  SELECT a.x, ROW_NUMBER() OVER (PARTITION BY a.k ORDER BY a.d DESC) AS rn,
         LAG(a.d) OVER (PARTITION BY a.k ORDER BY a.d) AS prev,
         LEAD(a.d) OVER (PARTITION BY a.k ORDER BY a.d) AS nxt
  FROM a
)
SELECT concat_key(r.x, 'b', 'c') AS key,
       CASE WHEN r.rn = 1 THEN CAST(r.x AS INTEGER) ELSE COALESCE(r.prev, 0) END AS v,
       MIN(r.x) AS lo, MAX(r.x) AS hi, SUM(r.rn) AS total, COUNT(*) AS n,
       date_diff_days(date_add_days(r.d, 3), r.d) AS gap, site_date(r.ts) AS local_day
FROM ranked r LEFT JOIN b ON b.k = r.x
WHERE r.x IN ('A', 'A4') AND r.d >= DATE '2026-10-12'
GROUP BY r.x
"""


def test_f06_ac07_the_allowed_function_set_is_the_spec_list_plus_the_macros() -> None:
    assert {
        "CASE", "COALESCE", "CAST", "MIN", "MAX", "SUM", "COUNT", "ROW_NUMBER", "LAG", "LEAD",
        "DATE_ADD_DAYS", "DATE_DIFF_DAYS", "SITE_DATE", "CONCAT_KEY",
    } == set(ALLOWED_FUNCTIONS)  # fmt: skip


def test_f06_ac07_portable_sql_with_macros_passes_in_both_dialects() -> None:
    assert check_sql(GOOD, TZ) == []


@pytest.mark.parametrize(
    ("sql", "function"),
    [
        ("SELECT CURRENT_DATE FROM t", "CURRENT_DATE"),
        ("SELECT IF(a > 1, 1, 0) FROM t", "IF"),
        ("SELECT regexp_replace(a, 'x', 'y') FROM t", "REGEXP_REPLACE"),
        ("SELECT strftime(d, '%Y') FROM t", "TIME_TO_STR"),
        ("SELECT LOWER(a) FROM t", "LOWER"),
        ("SELECT GREATEST(a, b) FROM t", "GREATEST"),
        ("SELECT to_json(a) FROM t", "TO_JSON"),
        ("SELECT TRY_CAST(a AS INTEGER) FROM t", "TRY_CAST"),
    ],
)
def test_f06_ac07_unknown_functions_are_reported_by_name(sql: str, function: str) -> None:
    problems = check_sql(sql, TZ)
    assert any(function in problem for problem in problems), problems


def test_f06_ac07_sql_that_does_not_parse_is_reported() -> None:
    assert check_sql("SELECT FROM WHERE (", TZ)


def test_f06_ac07_every_transform_file_is_portable(profile: SiteProfile) -> None:
    """Every SQL file of the pipeline, rendered with the real profile, passes in the DuckDB and Spark dialects."""
    from datetime import date

    files = transform_files()
    if not files:
        pytest.skip("no transform SQL files yet")
    from r2r_pipeline.sql_shim import render_template

    variables = template_variables(profile, date(2026, 10, 12))
    for path in files:
        rendered = render_template(path.read_text(encoding="utf-8"), **variables)
        assert check_sql(rendered, profile.site.timezone) == [], path.name
