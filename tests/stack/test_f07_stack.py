"""F07 acceptance tests against the real containers: Dagster, the scenario trigger and the lakehouse volume.

Run with `make stack-test` (an isolated stack and lakehouse) or against a running `make up`. The test seeds the
source databases with the generator first, so it resets the data of the stack it talks to.
"""

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from deltalake import DeltaTable

pytestmark = pytest.mark.stack

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO = f"http://localhost:{os.environ.get('SCENARIO_HOST_PORT', '8100')}"
DAGSTER = f"http://localhost:{os.environ.get('DAGSTER_HOST_PORT', '3001')}"
LAKE = Path(os.environ.get("LAKEHOUSE_HOST_DIR", REPO_ROOT / "lakehouse"))
STEPS = ["setup", "extract", "transform", "snapshot_aggregate", "publish", "notify"]
PUBLISHED = [
    "batch_pipeline_v", "weekly_metrics_v", "weekly_metric_rows_v", "stage_reference_v", "metric_reference_v",
    "reason_codes_v", "deviations_v", "pipeline_status_v",
]  # fmt: skip


def _env_file_value(name: str, default: str) -> str:
    if name in os.environ:
        return os.environ[name]
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return default


def _table(layer: str, name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = DeltaTable(str(LAKE / layer / name)).to_pyarrow_table().to_pylist()
    return rows


@pytest.fixture(scope="module")
def seeded() -> None:
    """Fill the three source databases with the seeded dataset, as the stack's Postgres sees them."""
    env = {
        **os.environ,
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": os.environ.get("POSTGRES_HOST_PORT", "5432"),
        "POSTGRES_USER": _env_file_value("POSTGRES_USER", "r2r"),
        "POSTGRES_PASSWORD": _env_file_value("POSTGRES_PASSWORD", "r2r_dev_only"),
    }
    result = subprocess.run(
        [sys.executable, "-m", "datagen", "generate", "--profile", "site_a"],
        check=False, cwd=REPO_ROOT, env=env, capture_output=True, text=True,
    )  # fmt: skip
    assert result.returncode == 0, f"datagen failed:\n{result.stdout}\n{result.stderr}"


@pytest.fixture(scope="module")
def run(seeded: None) -> dict[str, Any]:
    token = {"X-Scenario-Token": _env_file_value("SCENARIO_TOKEN", "dev-only-change-me")}
    began = time.perf_counter()
    response = httpx.post(f"{SCENARIO}/pipeline/run?wait=true", headers=token, timeout=330)
    elapsed = time.perf_counter() - began
    assert response.status_code == 200, response.text
    return {**response.json(), "seconds": elapsed}


def test_f07_ac01_all_eight_objects_exist_and_the_status_has_the_new_run_id(run: dict[str, Any]) -> None:
    for name in PUBLISHED:
        assert (LAKE / "published" / name / "_delta_log").is_dir(), name
    status = _table("published", "pipeline_status_v")
    assert [row["last_run_id"] for row in status] == [run["run_id"]]
    assert status[0]["row_count"] == len(_table("published", "batch_pipeline_v")) > 600


def test_f07_ac08_the_run_is_in_dagster_with_all_six_ops_green(run: dict[str, Any]) -> None:
    query = (
        "query($id: ID!) { runOrError(runId: $id) { ... on Run { status stepStats { stepKey status } } } }"
    )
    result = httpx.post(
        f"{DAGSTER}/graphql", json={"query": query, "variables": {"id": run["run_id"]}}, timeout=30
    ).json()["data"]["runOrError"]
    assert result["status"] == "SUCCESS"
    assert {s["stepKey"]: s["status"] for s in result["stepStats"]} == dict.fromkeys(STEPS, "SUCCESS")


def test_f07_fr08_a_full_run_on_the_seeded_dataset_takes_under_sixty_seconds(run: dict[str, Any]) -> None:
    """Wall time of `POST /pipeline/run?wait=true`, which includes Dagster's process start-up and notify."""
    assert run["seconds"] < 60, f"run took {run['seconds']:.1f} s"


def test_f07_fr05_the_run_log_has_one_row_per_step_for_the_run(run: dict[str, Any]) -> None:
    rows = [r for r in _table("intelligence", "pipeline_run_log") if r["run_id"] == run["run_id"]]
    assert sorted(r["step"] for r in rows) == sorted(STEPS)
    assert {r["status"] for r in rows} == {"success"}


def test_f07_fr04_a_webhook_that_cannot_be_delivered_does_not_fail_the_run(run: dict[str, Any]) -> None:
    """Until F08 exists nothing answers at WEBHOOK_URL, so notify reports failed and the run still succeeds."""
    [notify] = [
        r
        for r in _table("intelligence", "pipeline_run_log")
        if r["run_id"] == run["run_id"] and r["step"] == "notify"
    ]
    assert notify["status"] == "success"
    assert notify["notify_status"] in {"ok", "failed", "skipped"}
