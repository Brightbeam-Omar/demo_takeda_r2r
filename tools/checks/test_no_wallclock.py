"""Repo guard: no wall-clock calls in service or package ``src/`` code [F01-FR-08].

Rule (decision OQ-003)
----------------------
All business time must come from the demo clock, ``r2r_core.clock.now()`` / ``today()``.
This guard walks every ``src/`` Python file with ``ast`` and fails on calls to:

* ``datetime.now``, ``datetime.utcnow``, ``date.today``, ``time.time``

Allowed:

* ``time.monotonic`` and ``time.perf_counter`` for latency and duration measurement
* infrastructure timing done in SQL (for example the sync worker's stale-claim check using
  Postgres ``now()``): it is not Python, so this guard never sees it
* ``packages/r2r_core/src/r2r_core/clock.py``, the only module allowed to read the real clock

Limits: only call sites that spell the module or class in the call (``datetime.now()``,
``datetime.datetime.now()``) are detected; aliased imports are not. Only ``src/`` is scanned.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWED = Path("packages/r2r_core/src/r2r_core/clock.py")
BANNED_SUFFIXES = ("datetime.now", "datetime.utcnow", "date.today", "time.time")
SKIP_DIRS = {".venv", "node_modules", ".git", "lakehouse", "artifacts"}


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    call: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.call}() is banned, use r2r_core.clock"


def _dotted_name(node: ast.expr) -> str:
    """Return ``a.b.c`` for a chain of attribute lookups on a name, else ``""``."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def find_violations(root: Path) -> list[Violation]:
    """Scan every ``.py`` file that sits under a ``src`` directory below ``root``."""
    found: list[Violation] = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if SKIP_DIRS & set(rel.parts) or "src" not in rel.parts or rel == ALLOWED:
            continue
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            if isinstance(node, ast.Call):
                name = _dotted_name(node.func)
                if name.endswith(BANNED_SUFFIXES):
                    found.append(Violation(rel, node.lineno, name))
    return found


def _write(root: Path, rel: str, body: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body)


def test_f01_ac03_flags_datetime_now_with_file_and_line(tmp_path: Path) -> None:
    """F01-AC-03: a ``datetime.now()`` in services/app_api/src is reported with file and line."""
    _write(
        tmp_path,
        "services/app_api/src/app_api/bad.py",
        "from datetime import datetime\n\nx = datetime.now()\n",
    )
    [violation] = find_violations(tmp_path)
    assert str(violation).startswith("services/app_api/src/app_api/bad.py:3:")


def test_f01_fr08_flags_every_banned_call(tmp_path: Path) -> None:
    """F01-FR-08: all four banned calls are caught, including ``datetime.datetime.now``."""
    body = (
        "import datetime\nimport time\n"
        "a = datetime.datetime.now()\n"
        "b = datetime.datetime.utcnow()\n"
        "c = datetime.date.today()\n"
        "d = time.time()\n"
    )
    _write(tmp_path, "services/pipeline/src/pipeline/bad.py", body)
    assert [v.line for v in find_violations(tmp_path)] == [3, 4, 5, 6]


def test_f01_fr08_allows_duration_timers(tmp_path: Path) -> None:
    """OQ-003: ``time.monotonic`` and ``time.perf_counter`` are allowed."""
    body = "import time\n\nt0 = time.perf_counter()\nt1 = time.monotonic()\n"
    _write(tmp_path, "services/agents/src/agents/ok.py", body)
    assert find_violations(tmp_path) == []


def test_f01_fr08_allows_clock_module(tmp_path: Path) -> None:
    """F01-FR-08: ``r2r_core/clock.py`` is the single allow-listed module."""
    _write(tmp_path, str(ALLOWED), "from datetime import datetime\n\nx = datetime.now()\n")
    assert find_violations(tmp_path) == []


def test_f01_fr08_ignores_code_outside_src(tmp_path: Path) -> None:
    """Only ``src/`` is scanned, so tests may build timestamps freely."""
    _write(
        tmp_path, "services/app_api/tests/test_x.py", "from datetime import datetime\n\nx = datetime.now()\n"
    )
    assert find_violations(tmp_path) == []


def test_f01_fr08_repo_has_no_wallclock_calls() -> None:
    """F01-FR-08: the real repository is clean. This is what makes `make check` fail on a violation."""
    violations = find_violations(REPO_ROOT)
    assert not violations, "\n" + "\n".join(str(v) for v in violations)
