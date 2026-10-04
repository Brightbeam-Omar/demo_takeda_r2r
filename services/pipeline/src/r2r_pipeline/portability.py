"""The portability check for transform SQL (F06-FR-08, F06-AC-07).

A file passes when (1) it parses in both the DuckDB and the Spark dialect and (2) every function it calls is
in the allow-list: the SQL a data engineer can port to Databricks unchanged, plus the four shim macros.
"""

import sqlglot
from sqlglot import exp

from r2r_pipeline.sql_shim import DIALECTS, MACRO_NAMES, expand_macros

BASE_FUNCTIONS = ("CASE", "COALESCE", "CAST", "MIN", "MAX", "SUM", "COUNT", "ROW_NUMBER", "LAG", "LEAD")
ALLOWED_FUNCTIONS = (*BASE_FUNCTIONS, *(name.upper() for name in MACRO_NAMES))


def _is_syntax(node: exp.Func) -> bool:
    """sqlglot models AND / OR and the WHEN branches of a CASE as functions; they are plain syntax."""
    return isinstance(node, (exp.And, exp.Or)) or (
        isinstance(node, exp.If) and isinstance(node.parent, exp.Case)
    )


def _function_name(node: exp.Func) -> str:
    return node.name.upper() if isinstance(node, exp.Anonymous) else node.sql_name().upper()


def check_sql(sql: str, timezone: str) -> list[str]:
    """Problems found in a rendered SQL text, empty if it is portable."""
    problems: list[str] = []
    try:
        statements = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except sqlglot.errors.SqlglotError as error:
        return [f"does not parse: {error}"]
    for statement in statements:
        for node in statement.find_all(exp.Func):
            if _is_syntax(node):
                continue
            name = _function_name(node)
            if name not in ALLOWED_FUNCTIONS:
                problems.append(f"function {name} is not in the portable allow-list")
    for dialect in DIALECTS:
        expanded = expand_macros(sql, dialect, timezone)
        try:
            sqlglot.parse(expanded, read=dialect)
        except sqlglot.errors.SqlglotError as error:
            problems.append(f"does not parse as {dialect}: {error}")
    return sorted(set(problems))
