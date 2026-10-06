"""SQL macros and templating: one SQL text, two dialects (constitution P6).

Transform files use a Spark-SQL-compatible subset plus five macros, expanded here per dialect:

| macro | meaning |
|---|---|
| ``date_add_days(d, n)`` | the date ``n`` days after ``d`` |
| ``date_diff_days(a, b)`` | whole days from ``b`` to ``a`` (``a - b``) |
| ``site_date(ts)`` | the site-local calendar date of a UTC timestamp (time zone from the profile) |
| ``concat_key(a, b, ...)`` | the ``|``-joined key of its arguments |
| ``row_hash(a, b, ...)`` | a stable content hash (MD5 hex); NULL counts as ``~`` (F21-FR-01) |

Files are Jinja templates too: they receive the run's parameters (snapshot date, UD codes, ...) and never
carry hand-written literals for them.
"""

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import jinja2

DIALECTS = ("duckdb", "spark")
MACRO_NAMES = ("date_add_days", "date_diff_days", "site_date", "concat_key", "row_hash")

Expander = Callable[[list[str], str], str]


def _concat(args: list[str], tz: str) -> str:
    return "CONCAT_WS('|', " + ", ".join(args) + ")"


def _row_hash(args: list[str], tz: str) -> str:
    """MD5 over the arguments as text, separated by ``|``; the same text form in both dialects."""
    return "md5(CONCAT_WS('|', " + ", ".join(f"COALESCE(CAST({a} AS STRING), '~')" for a in args) + "))"


_EXPANDERS: dict[str, dict[str, Expander]] = {
    "duckdb": {
        "date_add_days": lambda a, tz: f"({a[0]} + {a[1]})",
        "date_diff_days": lambda a, tz: f"date_diff('day', {a[1]}, {a[0]})",
        "site_date": lambda a, tz: f"CAST(timezone('{tz}', {a[0]}) AS DATE)",
        "concat_key": _concat,
        "row_hash": _row_hash,
    },
    "spark": {
        "date_add_days": lambda a, tz: f"date_add({a[0]}, {a[1]})",
        "date_diff_days": lambda a, tz: f"datediff({a[0]}, {a[1]})",
        "site_date": lambda a, tz: f"CAST(from_utc_timestamp({a[0]}, '{tz}') AS DATE)",
        "concat_key": _concat,
        "row_hash": _row_hash,
    },
}
_ARITY = {"date_add_days": 2, "date_diff_days": 2, "site_date": 1}
_CALL = re.compile(r"\b(" + "|".join(MACRO_NAMES) + r")\s*\(", re.IGNORECASE)


def split_arguments(text: str) -> list[str]:
    """Split a macro's argument text at top-level commas (parentheses and quotes are respected)."""
    parts: list[str] = []
    depth, start, quote = 0, 0, False
    for index, char in enumerate(text):
        if char == "'":
            quote = not quote
        elif quote:
            continue
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
    parts.append(text[start:].strip())
    return parts


def expand_macros(sql: str, dialect: str, timezone: str) -> str:
    """Replace every macro call by its form in ``dialect``. Nested calls are expanded first."""
    if dialect not in _EXPANDERS:
        raise ValueError(f"unknown dialect {dialect!r}; expected one of {DIALECTS}")
    out: list[str] = []
    position = 0
    while True:
        match = _CALL.search(sql, position)
        if match is None:
            out.append(sql[position:])
            return "".join(out)
        depth, index, quote = 1, match.end(), False
        while depth:
            if index >= len(sql):
                raise ValueError(f"unbalanced parentheses in call to {match.group(1)}")
            char = sql[index]
            if char == "'":
                quote = not quote
            elif not quote:
                depth += (char == "(") - (char == ")")
            index += 1
        name = match.group(1).lower()
        args = [expand_macros(a, dialect, timezone) for a in split_arguments(sql[match.end() : index - 1])]
        if name in _ARITY and len(args) != _ARITY[name]:
            raise ValueError(f"{name} takes {_ARITY[name]} argument(s), got {len(args)}")
        if name == "concat_key" and len(args) < 2:
            raise ValueError("concat_key takes at least two arguments")
        if name == "row_hash" and not args[0]:
            raise ValueError("row_hash takes at least one argument")
        out.append(sql[position : match.start()])
        out.append(_EXPANDERS[dialect][name](args, timezone))
        position = index


def sql_literal(value: Any) -> str:
    """A SQL literal for a Jinja variable: quoted strings, ``DATE '...'`` dates, ``('a', 'b')`` lists."""
    from datetime import date

    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, date):
        return f"DATE '{value.isoformat()}'"
    if isinstance(value, (list, tuple)):
        return "(" + ", ".join(sql_literal(v) for v in value) + ")" if value else "(NULL)"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _environment() -> jinja2.Environment:
    env = jinja2.Environment(
        undefined=jinja2.StrictUndefined, keep_trailing_newline=True, trim_blocks=True, lstrip_blocks=True
    )
    env.filters["sql"] = sql_literal
    return env


def render_template(text: str, **variables: Any) -> str:
    """Render a SQL template with Jinja. Use ``{{ value | sql }}`` to put a value in as a literal."""
    return _environment().from_string(text).render(**variables)


def render_file(path: Path, dialect: str, tz_name: str, /, **variables: Any) -> str:
    return expand_macros(render_template(path.read_text(encoding="utf-8"), **variables), dialect, tz_name)
