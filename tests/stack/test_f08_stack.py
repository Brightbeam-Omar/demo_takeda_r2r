"""F08 acceptance tests against the real containers: pipeline -> webhook -> queue -> worker -> mirror.

Run with `make stack-test` (an isolated stack and lakehouse) or against a running `make up`. Like the F07 stack
test, it seeds the source databases with the generator first, so it resets the data of the stack it talks to.
"""

import hashlib
import hmac
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest
from deltalake import DeltaTable

pytestmark = pytest.mark.stack

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO = f"http://localhost:{os.environ.get('SCENARIO_HOST_PORT', '8100')}"
APP_API = f"http://localhost:{os.environ.get('APP_API_HOST_PORT', '8000')}"
LAKE = Path(os.environ.get("LAKEHOUSE_HOST_DIR", REPO_ROOT / "lakehouse"))
OBJECTS = {
    "batch_pipeline_v": "mirror_batch_pipeline",
    "weekly_metrics_v": "mirror_weekly_metrics",
    "weekly_metric_rows_v": "mirror_weekly_metric_rows",
    "stage_reference_v": "mirror_stage_reference",
    "metric_reference_v": "mirror_metric_reference",
    "reason_codes_v": "mirror_reason_codes",
    "deviations_v": "mirror_deviations",
    "pipeline_status_v": "mirror_pipeline_status",
}


def _env(name: str, default: str) -> str:
    if name in os.environ:
        return os.environ[name]
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return default


DRAIN_SECONDS = float(_env("DRAIN_INTERVAL_SECONDS", "20"))
SECRET = _env("WEBHOOK_SECRET", "dev-only-change-me")


def _pg(database: str) -> psycopg.Connection[Any]:
    return psycopg.connect(
        host="localhost",
        port=int(os.environ.get("POSTGRES_HOST_PORT", "5432")),
        user=_env("POSTGRES_USER", "r2r"),
        password=_env("POSTGRES_PASSWORD", "r2r_dev_only"),
        dbname=database,
        autocommit=True,
    )


def _app(query: str, *params: Any) -> list[tuple[Any, ...]]:
    with _pg("app") as connection:
        return connection.execute(query, params).fetchall()  # type: ignore[arg-type]


def _published(name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = DeltaTable(str(LAKE / "published" / name)).to_pyarrow_table().to_pylist()
    return rows


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def _webhook(run_id: str) -> httpx.Response:
    body = json.dumps(
        {"run_id": run_id, "published_at": "2026-10-12T07:00:00+00:00"}, separators=(",", ":")
    ).encode()
    return httpx.post(
        f"{APP_API}/api/sync/webhook",
        content=body,
        headers={"X-Signature": _sign(body), "Content-Type": "application/json"},
    )


def _wait_for(condition: Any, timeout: float, what: str) -> float:
    began = time.perf_counter()
    while time.perf_counter() - began < timeout:
        if condition():
            return time.perf_counter() - began
        time.sleep(0.5)
    raise AssertionError(f"timed out after {timeout:.0f} s waiting for {what}")


def _event(event_id: int) -> tuple[Any, ...]:
    [row] = _app(
        "SELECT status, rows_upserted, error, source, run_id FROM sync_event WHERE id = %s", event_id
    )
    return row


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
def synced(seeded: None) -> dict[str, Any]:
    """One pipeline run, then wait for the worker to mirror it. ``seconds`` runs from the end of the run."""
    token = {"X-Scenario-Token": _env("SCENARIO_TOKEN", "dev-only-change-me")}
    response = httpx.post(f"{SCENARIO}/pipeline/run?wait=true", headers=token, timeout=330)
    assert response.status_code == 200, response.text
    run_id: str = response.json()["run_id"]

    def mirrored() -> bool:
        rows = _app("SELECT run_id FROM watermark")
        done = _app("SELECT 1 FROM sync_event WHERE status = 'done' AND run_id = %s", run_id)
        return len(rows) == len(OBJECTS) and {r[0] for r in rows} == {run_id} and bool(done)

    seconds = _wait_for(mirrored, DRAIN_SECONDS + 40, "the mirror to reach the new run")
    print(
        f"\nF08 timing: pipeline run finished -> mirror done in {seconds:.1f} s (drain interval {DRAIN_SECONDS:.0f} s)"
    )
    return {"run_id": run_id, "seconds": seconds}


def test_f08_ac01_the_mirror_holds_every_published_row_and_the_watermark_the_new_run(
    synced: dict[str, Any],
) -> None:
    for name, table in OBJECTS.items():
        [(mirrored,)] = _app(f"SELECT count(*) FROM {table}")
        assert mirrored == len(_published(name)), name
        print(f"F08 mirror rows: {table} = {mirrored}")
    assert {r[0]: r[1] for r in _app("SELECT object_name, run_id FROM watermark")} == dict.fromkeys(
        OBJECTS, synced["run_id"]
    )
    [(runs,)] = _app("SELECT count(DISTINCT contract_run_id) FROM mirror_batch_pipeline")
    assert runs == 1


def test_f08_ac01_the_mirror_follows_the_pipeline_within_the_drain_interval_plus_ten_seconds(
    synced: dict[str, Any],
) -> None:
    assert synced["seconds"] <= DRAIN_SECONDS + 10, f"took {synced['seconds']:.1f} s"


def test_f08_fr02_notify_now_reports_ok(synced: dict[str, Any]) -> None:
    rows = DeltaTable(str(LAKE / "intelligence" / "pipeline_run_log")).to_pyarrow_table().to_pylist()
    [notify] = [r for r in rows if r["run_id"] == synced["run_id"] and r["step"] == "notify"]
    assert (notify["status"], notify["notify_status"]) == ("success", "ok")


def test_f08_fr05_the_webhook_event_is_done_with_the_row_counts(synced: dict[str, Any]) -> None:
    [(status, rows_upserted, error, source)] = _app(
        "SELECT status, rows_upserted, error, source FROM sync_event WHERE run_id = %s AND source = 'webhook' ORDER BY id LIMIT 1",
        synced["run_id"],
    )
    assert (status, error, source) == ("done", None, "webhook")
    assert rows_upserted == sum(len(_published(name)) for name in OBJECTS)


def test_f08_fr07_status_endpoint_shows_events_watermarks_and_freshness(synced: dict[str, Any]) -> None:
    body = httpx.get(f"{APP_API}/api/sync/status", timeout=10).json()
    assert body["pipeline_status"]["last_run_id"] == synced["run_id"]
    assert {w["run_id"] for w in body["watermarks"]} == {synced["run_id"]}
    assert body["events"][0]["age_seconds"] >= 0
    assert isinstance(body["freshness_minutes"], int)


def test_f08_ac02_a_bad_signature_gets_401_no_event_and_one_audit_row(synced: dict[str, Any]) -> None:
    [(audits_before,)] = _app("SELECT count(*) FROM audit_event WHERE action = 'webhook_rejected'")
    response = httpx.post(
        f"{APP_API}/api/sync/webhook", content=b'{"run_id":"x"}', headers={"X-Signature": "sha256=00"}
    )
    assert response.status_code == 401
    assert _app("SELECT count(*) FROM sync_event WHERE run_id = 'x'") == [(0,)]  # no event for the bad call
    assert _app("SELECT count(*) FROM audit_event WHERE action = 'webhook_rejected'") == [
        (audits_before + 1,)
    ]


def test_f08_ac05_a_duplicate_webhook_for_the_same_run_completes_as_a_no_op(synced: dict[str, Any]) -> None:
    response = _webhook(synced["run_id"])
    assert response.status_code == 202
    event_id = response.json()["event_id"]
    _wait_for(lambda: _event(event_id)[0] in {"done", "failed"}, DRAIN_SECONDS + 40, "the duplicate event")
    status, rows_upserted, error, *_ = _event(event_id)
    assert (status, rows_upserted, error) == ("done", 0, None)


def test_f08_fr03_the_manual_trigger_is_admin_only_and_completes(synced: dict[str, Any]) -> None:
    assert httpx.post(f"{APP_API}/api/sync/trigger", headers={"X-Demo-User": "sam"}).status_code == 403
    response = httpx.post(f"{APP_API}/api/sync/trigger", headers={"X-Demo-User": "admin"})
    assert response.status_code == 202
    event_id = response.json()["event_id"]
    _wait_for(lambda: _event(event_id)[0] in {"done", "failed"}, DRAIN_SECONDS + 40, "the manual event")
    assert _event(event_id)[:3] == ("done", 0, None)
    assert _event(event_id)[3] == "manual"


def test_f08_fr06_the_worker_cannot_write_to_the_lakehouse() -> None:
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "app-worker", "sh", "-c", "touch /lakehouse/should-not-exist"],
        check=False, cwd=REPO_ROOT, capture_output=True, text=True,
    )  # fmt: skip
    assert result.returncode != 0
    assert "read-only" in (result.stdout + result.stderr).lower()
