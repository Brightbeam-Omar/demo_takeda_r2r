"""T4: the run history the Sync Status page reads (F21-FR-02, OQ-135)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from r2r_core.profile import load_profile
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import NOW, load_mirror

pytestmark = pytest.mark.integration

EARLIER = datetime(2026, 10, 12, 5, 0, tzinfo=UTC)


def run(run_id: str, seq: int, started: datetime, **values: Any) -> dict[str, Any]:
    return {
        "pipeline_run_id": run_id, "run_seq": seq, "started_at": started, "duration_ms": 1500, "files": 18,
        "inserted": 0, "total": 803, "skipped": 803, "status": "ok", "failed_step": None, "run_id": "run-3",
    } | values  # fmt: skip


def step(run_id: str, name: str, status: str = "success", **values: Any) -> dict[str, Any]:
    return {
        "pipeline_run_id": run_id, "step": name, "status": status, "started_at": NOW, "finished_at": NOW,
        "duration_ms": 120, "rows": 803, "error": None, "run_id": "run-3",
    } | values  # fmt: skip


def seed(factory: sessionmaker[Session]) -> None:
    load_mirror(
        factory,
        load_profile("site_a"),
        [],
        run_id="run-3",
        runs=[
            run("run-1", 100, EARLIER, inserted=803, skipped=0),
            run(
                "run-2",
                200,
                EARLIER,
                status="failed",
                failed_step="transform",
                inserted=None,
                total=None,
                skipped=None,
            ),
            run("run-3", 300, NOW),
        ],
        run_steps=[
            step("run-2", "setup"),
            step("run-2", "transform", "failed", error="RuntimeError: boom", rows=None),
            step("run-3", "publish"),
            step("run-3", "setup"),
        ],
    )


def test_f21_fr02_runs_come_newest_first_with_demo_clock_ages(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    seed(app_factory)
    body = client.get("/api/pipeline/runs").json()
    assert [r["pipeline_run_id"] for r in body] == ["run-3", "run-2", "run-1"]
    assert body[0]["age_seconds"] == 0  # NOW is the demo clock in the tests
    assert body[1]["age_seconds"] == 2 * 3600
    assert (body[0]["inserted"], body[0]["skipped"], body[0]["total"]) == (0, 803, 803)


def test_f21_fr02_a_failed_run_shows_its_step_and_no_figures(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    seed(app_factory)
    failed = next(r for r in client.get("/api/pipeline/runs").json() if r["pipeline_run_id"] == "run-2")
    assert (failed["status"], failed["failed_step"]) == ("failed", "transform")
    assert (failed["inserted"], failed["total"], failed["skipped"]) == (None, None, None)


def test_f21_fr02_the_steps_of_a_run_are_in_pipeline_order_with_errors(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    seed(app_factory)
    steps = client.get("/api/pipeline/runs/run-2/steps").json()["steps"]
    assert [(s["step"], s["status"]) for s in steps] == [("setup", "success"), ("transform", "failed")]
    assert steps[1]["error"] == "RuntimeError: boom"
    assert steps[0]["duration_ms"] == 120
    ordered = client.get("/api/pipeline/runs/run-3/steps").json()["steps"]
    assert [s["step"] for s in ordered] == ["setup", "publish"]  # not the order they were stored in


def test_f21_fr02_an_unknown_run_is_404_and_every_role_may_read(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    seed(app_factory)
    assert client.get("/api/pipeline/runs/nope/steps").status_code == 404
    for user in ("sam", "pat", "admin"):
        assert client.get("/api/pipeline/runs", headers={"X-Demo-User": user}).status_code == 200
    assert client.get("/api/pipeline/runs", headers={"X-Demo-User": "ghost"}).status_code == 401
