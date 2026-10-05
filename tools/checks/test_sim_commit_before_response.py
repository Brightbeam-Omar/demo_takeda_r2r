"""Repo guard: a source simulator commits its session before the HTTP response is sent [F04-FR-05].

FastAPI runs the code after ``yield`` in a dependency *after* the response is sent unless the dependency has
``scope="function"``. The simulators commit there, so a client could get its 200 and read the old data on its
next call (the flaky ``test_f04_fr05_qms_opens_and_closes_a_deviation_for_a_batch``). This checks that each
simulator's ``SessionDep`` is declared with that scope.
"""

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SIMS = ("erp_sim", "lims_sim", "qms_sim")


@pytest.mark.parametrize("sim", SIMS)
def test_session_dependency_commits_before_the_response(sim: str) -> None:
    source = (REPO_ROOT / "services/sources" / sim / "src" / sim / "app.py").read_text()
    depends = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Depends"
    ]
    session_deps = [
        call for call in depends if call.args and getattr(call.args[0], "id", "") == "get_session"
    ]
    assert session_deps, f"{sim}: no Depends(get_session) found"
    for call in session_deps:
        scope = {kw.arg: getattr(kw.value, "value", None) for kw in call.keywords}.get("scope")
        assert scope == "function", f"{sim}: Depends(get_session) must use scope='function'"
