"""F21 acceptance tests against the real containers: the run history, the queue health and the admin actions.

Run with `make stack-test` (an isolated stack and lakehouse) or against a running `make up`. Like the F08 stack
test it seeds the source databases first, so it resets the data of the stack it talks to. AC-03 stops and
restarts `app-worker`, so it needs the docker CLI and touches only that container.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from deltalake import DeltaTable
from r2r_pipeline.schemas import STAGING_SCHEMAS

pytestmark = pytest.mark.stack

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO = f"http://localhost:{os.environ.get('SCENARIO_HOST_PORT', '8100')}"
ERP = f"http://localhost:{os.environ.get('ERP_HOST_PORT', '8101')}"
APP_API = f"http://localhost:{os.environ.get('APP_API_HOST_PORT', '8000')}"
LAKE = Path(os.environ.get("LAKEHOUSE_HOST_DIR", REPO_ROOT / "lakehouse"))
ADMIN = {"X-Demo-User": "admin"}
SAM = {"X-Demo-User": "sam"}


def _env(name: str, default: str) -> str:
    if name in os.environ:
        return os.environ[name]
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return default


TOKEN = {"X-Scenario-Token": _env("SCENARIO_TOKEN", "dev-only-change-me")}


def _get(path: str, headers: dict[str, str] | None = None) -> Any:
    response = httpx.get(f"{APP_API}{path}", headers=headers or ADMIN, timeout=30)
    assert response.status_code == 200, f"{path}: {response.status_code} {response.text}"
    return response.json()


def _run_pipeline() -> str:
    response = httpx.post(f"{SCENARIO}/pipeline/run?wait=true", headers=TOKEN, timeout=330)
    assert response.status_code == 200, response.text
    run_id: str = response.json()["run_id"]
    return run_id


def _wait_for(condition: Any, timeout: float, what: str) -> float:
    began = time.perf_counter()
    while time.perf_counter() - began < timeout:
        if condition():
            return time.perf_counter() - began
        time.sleep(0.5)
    raise AssertionError(f"timed out after {timeout:.0f} s waiting for {what}")


def _runs() -> dict[str, dict[str, Any]]:
    return {r["pipeline_run_id"]: r for r in _get("/api/pipeline/runs")}


def _mirrored(run_id: str) -> bool:
    return run_id in _runs() and _get("/api/sync/health")["pending"] == 0


def _published_runs() -> dict[str, dict[str, Any]]:
    rows = DeltaTable(str(LAKE / "published" / "pipeline_runs_v")).to_pyarrow_table().to_pylist()
    return {r["pipeline_run_id"]: r for r in rows}


@pytest.fixture(scope="module")
def seeded() -> None:
    env = {
        **os.environ,
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": os.environ.get("POSTGRES_HOST_PORT", "5432"),
        "POSTGRES_USER": _env("POSTGRES_USER", "r2r"),
        "POSTGRES_PASSWORD": _env("POSTGRES_PASSWORD", "r2r_dev_only"),
    }
    with tempfile.TemporaryDirectory() as artifacts:
        result = subprocess.run(
            [sys.executable, "-m", "datagen", "generate", "--profile", "site_a", "--artifacts", artifacts],
            check=False, cwd=REPO_ROOT, env=env, capture_output=True, text=True,
        )  # fmt: skip
    assert result.returncode == 0, f"datagen failed:\n{result.stdout}\n{result.stderr}"


@pytest.fixture(scope="module")
def two_runs(seeded: None) -> dict[str, str]:
    """Two pipeline runs on unchanged data (F21-AC-01), then wait for the second to reach the app."""
    first, second = _run_pipeline(), _run_pipeline()
    _wait_for(lambda: _mirrored(second), 90, "the second run to reach the app")
    return {"first": first, "second": second}


def test_f21_ac01_the_second_run_on_unchanged_data_inserts_nothing(two_runs: dict[str, str]) -> None:
    runs = _published_runs()
    second = runs[two_runs["second"]]
    assert second["inserted"] == 0 and second["skipped"] == second["total"] > 600
    assert second["status"] == "ok" and second["failed_step"] is None
    assert second["files"] == len(STAGING_SCHEMAS) and second["duration_ms"] > 0


def test_f21_ac01_a_changed_lot_is_inserted_by_the_next_run(two_runs: dict[str, str]) -> None:
    lots = DeltaTable(str(LAKE / "published" / "batch_pipeline_v")).to_pyarrow_table().to_pylist()
    lot = next(r for r in lots if r["batch_status_code"] != "H" and r["stage_key"] != "released")
    body = {"matnr": lot["material_no"], "charg": lot["batch_no"], "hold": True}
    assert httpx.post(f"{ERP}/events/hold", json=body, headers=TOKEN, timeout=10).status_code in (200, 201)
    try:
        run_id = _run_pipeline()
        assert _published_runs()[run_id]["inserted"] >= 1
    finally:
        httpx.post(f"{ERP}/events/hold", json=body | {"hold": False}, headers=TOKEN, timeout=10)


def test_f21_fr02_the_app_serves_the_history_newest_first_with_per_step_detail(
    two_runs: dict[str, str],
) -> None:
    runs = _get("/api/pipeline/runs")
    ids = [r["pipeline_run_id"] for r in runs]
    assert ids.index(two_runs["second"]) < ids.index(two_runs["first"])
    steps = _get(f"/api/pipeline/runs/{two_runs['second']}/steps")["steps"]
    assert [s["step"] for s in steps][:5] == [
        "setup",
        "extract",
        "transform",
        "snapshot_aggregate",
        "publish",
    ]
    assert {s["status"] for s in steps} == {"success"}


def test_f21_ac03_cards_at_rest_then_a_stopped_worker_lets_pending_rise_and_last_drain_age(
    two_runs: dict[str, str],
) -> None:
    # At rest means the queue has caught up with the runs the earlier tests started.
    _wait_for(lambda: _get("/api/sync/health")["pending"] == 0, 30, "the queue to be idle")
    health = _get("/api/sync/health")
    assert (health["pending"], health["error"], health["abandoned"]) == (0, 0, 0)
    assert health["last_drain_age_seconds"] is not None and health["last_drain_age_seconds"] < 30
    if shutil.which("docker") is None:
        pytest.skip("the docker CLI is needed to stop app-worker")
    project = os.environ.get("COMPOSE_PROJECT_NAME")
    compose = ["docker", "compose", *(["-p", project] if project else [])]

    def worker(action: str) -> None:
        subprocess.run([*compose, action, "app-worker"], cwd=REPO_ROOT, check=True, capture_output=True)

    worker("stop")
    try:
        run_id = _run_pipeline()
        _wait_for(
            lambda: _get("/api/sync/health")["pending"] == 1, 30, "the webhook event to wait as pending"
        )
        time.sleep(6)
        assert (
            _get("/api/sync/health")["last_drain_age_seconds"] >= 6
        )  # the heartbeat stopped with the worker
        assert run_id not in _runs()  # nothing was mirrored
    finally:
        worker("start")
    _wait_for(lambda: _get("/api/sync/health")["pending"] == 0, 60, "the restarted worker to drain the queue")
    _wait_for(lambda: _get("/api/sync/health")["last_drain_age_seconds"] < 30, 30, "the heartbeat to resume")
    assert _get("/api/sync/health")["abandoned"] == 0


def test_f21_ac04_trigger_sync_now_flows_pipeline_webhook_done_and_sam_is_refused(
    two_runs: dict[str, str],
) -> None:
    assert httpx.post(f"{APP_API}/api/sync/run-pipeline", headers=SAM, timeout=10).status_code == 403
    before = set(_runs())
    response = httpx.post(f"{APP_API}/api/sync/run-pipeline", headers=ADMIN, timeout=30)
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]
    _wait_for(lambda: run_id in _runs(), 240, "the triggered run to appear in the history")
    assert run_id not in before
    _wait_for(lambda: _mirrored(run_id), 90, "the webhook event to finish")
    events = _get("/api/sync/status")["events"]
    assert events[0]["status"] == "done" and events[0]["source"] == "webhook"
    audit = _get("/api/audit?action=pipeline_triggered")["items"]
    assert audit[0]["actor_user_key"] == "admin" and audit[0]["details"]["pipeline_run_id"] == run_id


def test_f21_ac05_the_late_counts_of_the_teams_sum_to_the_overview_late_count(
    two_runs: dict[str, str],
) -> None:
    teams = _get("/api/teams")
    overview = _get("/api/overview")
    late = next(a for a in overview["alerts"] if a["kind"] == "late")["count"]
    assert sum(t["late"] for t in teams["teams"]) == late == teams["totals"]["late"]
    print(f"\nF21 late lots: {late}")


def test_f21_ac06_the_schema_reference_lists_every_published_object(two_runs: dict[str, str]) -> None:
    published = sorted(p.name for p in (LAKE / "published").iterdir() if p.is_dir())
    assert sorted(o["name"] for o in _get("/api/schema")["objects"]) == published
