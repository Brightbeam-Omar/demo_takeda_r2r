"""Repo guard: the application commits its session before the HTTP response is sent [F08].

FastAPI runs the code after ``yield`` in a dependency *after* the response is sent unless the dependency has
``scope="function"``. ``app_api.db.get_session`` commits there, so a client could get its 200 from a write
endpoint (need-by, status, comments, sync trigger, webhook, feedback) and read the old data on its next call.
This checks that every ``Depends(get_session)`` in ``app_api`` is declared with that scope, and that no write
endpoint defers work with ``BackgroundTasks``.
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_API_SRC = REPO_ROOT / "services/app_api/src/app_api"


def _sources() -> list[Path]:
    return sorted(p for p in APP_API_SRC.rglob("*.py") if "migrations" not in p.parts)


def test_every_session_dependency_commits_before_the_response() -> None:
    found = 0
    for path in _sources():
        for node in ast.walk(ast.parse(path.read_text())):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Depends"):
                continue
            if not (node.args and getattr(node.args[0], "id", "") == "get_session"):
                continue
            found += 1
            scope = {kw.arg: getattr(kw.value, "value", None) for kw in node.keywords}.get("scope")
            where = f"{path.relative_to(REPO_ROOT)}:{node.lineno}"
            assert scope == "function", f"{where}: Depends(get_session) must use scope='function'"
    assert found, "no Depends(get_session) found in app_api"


def test_write_endpoints_do_not_defer_work_to_background_tasks() -> None:
    for path in _sources():
        assert "BackgroundTasks" not in path.read_text(), f"{path.relative_to(REPO_ROOT)}: no deferred work"
