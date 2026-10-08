"""F13 acceptance tests against the real containers: the demo reset and the scenario steps.

Run with `make stack-test` (an isolated stack and lakehouse) or against a running `make up`. Every test starts from
a demo reset (about a minute), so this file is the slow one. It leaves the stack in the demo-start state. The tests
that run the air-gap agent use the committed recordings and are skipped, with the reason, when there are none.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest
from deltalake import DeltaTable

pytestmark = pytest.mark.stack

REPO_ROOT = Path(__file__).resolve().parents[2]
RECORDINGS = REPO_ROOT / "services" / "agents" / "recordings" / "air_gap"
needs_recordings = pytest.mark.skipif(
    not list(RECORDINGS.glob("*.json")),
    reason="no recordings yet: run `make record-agents` (needs ANTHROPIC_API_KEY with credit)",
)


def _env(name: str, default: str) -> str:
    if name in os.environ:
        return os.environ[name]
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return default


def _url(port_var: str, default: str) -> str:
    return f"http://localhost:{os.environ.get(port_var, default)}"


SCENARIO = _url("SCENARIO_HOST_PORT", "8100")
APP_API = _url("APP_API_HOST_PORT", "8000")
AGENTS = _url("AGENTS_HOST_PORT", "8200")
LAKE = Path(os.environ.get("LAKEHOUSE_HOST_DIR", REPO_ROOT / "lakehouse"))
PG_PORT = os.environ.get("POSTGRES_HOST_PORT", "5432")
TOKEN = {"X-Scenario-Token": _env("SCENARIO_TOKEN", "dev-only-change-me"), "X-Actor-User": "admin"}
ADMIN = {"X-Demo-User": "admin"}
PAT = {"X-Demo-User": "pat"}
ALEX = {"X-Demo-User": "alex"}
OPENING = "2026-10-12T07:00:00Z"
RESET_BUDGET_SECONDS = 180  # F13-AC-01


def _pg(database: str) -> psycopg.Connection[Any]:
    return psycopg.connect(
        host="localhost", port=PG_PORT, dbname=database, user=_env("POSTGRES_USER", "r2r"),
        password=_env("POSTGRES_PASSWORD", "r2r_dev_only"), autocommit=True,
    )  # fmt: skip


def _scalar(database: str, sql: str) -> Any:
    with _pg(database) as connection:
        row = connection.execute(sql).fetchone()
    assert row is not None
    return row[0]


def _get(url: str, headers: dict[str, str] | None = None) -> Any:
    response = httpx.get(url, headers=headers or ADMIN, timeout=60)
    assert response.status_code == 200, f"{url}: {response.status_code} {response.text}"
    return response.json()


def _follow(run_id: str) -> list[dict[str, Any]]:
    """Every progress event of a run, read from the SSE stream until it ends."""
    events: list[dict[str, Any]] = []
    with httpx.stream(
        "GET", f"{SCENARIO}/scenario/runs/{run_id}/events", headers=TOKEN, timeout=600
    ) as stream:
        assert stream.status_code == 200
        for line in stream.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: ") :]))
    return events


def _run(path: str) -> tuple[int, dict[str, Any], list[dict[str, Any]]]:
    """Start a step or the reset. Returns the HTTP status, the body and the progress events (none when refused)."""
    response = httpx.post(f"{SCENARIO}{path}", headers=TOKEN, timeout=60)
    body = response.json()
    return response.status_code, body, _follow(body["run_id"]) if response.status_code == 202 else []


def _step(step_id: str) -> list[dict[str, Any]]:
    status, body, events = _run(f"/scenario/steps/{step_id}/run")
    assert status == 202, body
    assert events[-1]["kind"] == "done", events[-1]
    return events


def _reset() -> float:
    began = time.perf_counter()
    status, body, events = _run("/scenario/reset")
    elapsed = time.perf_counter() - began
    assert status == 202, body
    assert events[-1]["kind"] == "done", [e["message"] for e in events][-3:]
    return elapsed


def _row(batch: str) -> dict[str, Any]:
    rows = [r for r in _get(f"{APP_API}/api/overview?q={batch}")["rows"] if r["batch_no"] == batch]
    assert rows, f"the app shows no row for {batch}"
    row: dict[str, Any] = sorted(rows, key=lambda r: r["lot_type"])[0]
    return row


def _maybe_row(batch: str) -> dict[str, Any] | None:
    """The in-flight row of a batch; None once its lot is released (a usage decision takes it out of the list)."""
    rows = [r for r in _get(f"{APP_API}/api/overview?q={batch}")["rows"] if r["batch_no"] == batch]
    return rows[0] if rows else None


def _air_gap_batches() -> set[str]:
    return {r["batch_no"] for r in _get(f"{APP_API}/api/overview/insights")["rows"]}


def _checksums() -> dict[str, str]:
    """F13-AC-05 / OQ-149: the published batch rows without run id and publish time, and every source table."""
    published = DeltaTable(str(LAKE / "published" / "batch_pipeline_v")).to_pyarrow_table().to_pylist()
    kept = sorted(
        ({k: v for k, v in row.items() if k not in ("run_id", "published_at")} for row in published),
        key=lambda row: str(row["row_key"]),
    )
    sums = {
        "batch_pipeline_v": hashlib.sha256(json.dumps(kept, sort_keys=True, default=str).encode()).hexdigest()
    }
    for database in ("erp_sim", "lims_sim", "qms_sim"):
        with _pg(database) as connection:
            tables = [
                r[0]
                for r in connection.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1"
                )
            ]
            for table in tables:
                if table in ("alembic_version",):
                    continue
                sums[f"{database}.{table}"] = str(
                    connection.execute(
                        f"SELECT md5(coalesce(string_agg(to_jsonb(t)::text, '|' ORDER BY to_jsonb(t)::text), '')) FROM \"{table}\" t"
                    ).fetchone()[0]  # type: ignore[index]
                )
    return sums


def _dirty_the_demo() -> None:
    """User input in every table the reset clears, an advanced clock, and (with recordings) agent proposals."""
    b2077 = _row("B2077")["row_key"]
    assert httpx.post(f"{APP_API}/api/bookmarks/{b2077}", headers=PAT, timeout=30).status_code == 201
    need_by = {"adjusted_date": "2026-11-26", "reason_code": "CAMPAIGN_PULLED_FORWARD", "expedite": False}
    assert (
        httpx.put(f"{APP_API}/api/rows/{b2077}/need-by", json=need_by, headers=PAT, timeout=30).status_code
        == 200
    )
    log = {"status": "at_risk", "comment": "Lab backlog this week"}
    assert (
        httpx.post(
            f"{APP_API}/api/rows/{b2077}/status-log", json=log, headers={"X-Demo-User": "quinn"}, timeout=30
        ).status_code
        == 201
    )
    assert (
        httpx.post(f"{SCENARIO}/clock/advance", json={"days": 3}, headers=TOKEN, timeout=30).status_code
        == 200
    )
    # A proposal row, inserted the way the agent writes it (a real run needs the recordings, which assume the opening clock).
    with _pg("app") as connection:
        connection.execute(
            "INSERT INTO proposal (agent_key, row_key, kind, payload_json, evidence_json, validator_result_json, status, "
            "required_role, created_at, trace_id) VALUES ('air_gap', %s, 'airgap_ticket', '{}', '[]', '[]', "
            "'pending_approval', 'qa_release', now(), 'TR-0007')",
            (b2077,),
        )


def test_f13_ac01_reset_from_a_dirty_state_is_fast_and_leaves_the_demo_start_state() -> None:
    _dirty_the_demo()
    assert _scalar("app", "SELECT count(*) FROM proposal") == 1
    clock = _get(f"{SCENARIO}/clock")
    assert clock["now_utc"] != OPENING

    elapsed = _reset()
    assert elapsed < RESET_BUDGET_SECONDS, f"the reset took {elapsed:.0f} s"

    assert _get(f"{SCENARIO}/clock")["now_utc"] == OPENING
    for table in (
        "proposal",
        "action_log",
        "agent_trace",
        "bookmark",
        "override_value",
        "status_log",
        "comment",
    ):
        assert _scalar("app", f"SELECT count(*) FROM {table}") == 0, table
    assert _scalar("app", "SELECT count(*) FROM app_user") == 5
    assert _get(f"{AGENTS}/proposals")["rows"] == []
    # The five story batches are in their set-up states (F05-FR-06).
    assert _row("B1042")["stage_key"] == "qc_testing"
    b2077 = _row("B2077")
    assert b2077["stage_key"] == "sampling" and b2077["adjusted_need_by_date"] is None
    b3150 = _row("B3150")
    assert b3150["stage_key"] == "qa_release" and b3150["deviation_light"] == "red"
    b4410 = _row("B4410")
    assert b4410["stage_key"] == "sampling" and b4410["lot_type"] == "09"
    b5003 = _row("B5003")
    assert b5003["air_gap"] is True and b5003["air_gap_hours"] == 30
    assert "B5003" in _air_gap_batches() and len(_air_gap_batches()) == 4
    # Published and mirrored: every watermark is at the run the reset published.
    marks = _get(f"{APP_API}/api/sync/status")["watermarks"]
    assert len(marks) == 17 and len({m["run_id"] for m in marks}) == 1


def test_f13_ac02_approving_b1042_moves_it_to_qa_release_and_a_second_run_is_refused() -> None:
    began = time.perf_counter()
    events = _step("lims-approve-B1042")
    assert time.perf_counter() - began < 90
    assert _row("B1042")["stage_key"] == "qa_release"
    assert any("[1/4] LIMS: approve the sample" in e["message"] for e in events)

    status, body, _ = _run("/scenario/steps/lims-approve-B1042/run")
    assert status == 409
    assert body["detail"]["error"] == "precondition_failed"
    assert "already been approved in LIMS" in body["detail"]["message"]
    outcomes = _scalar(
        "app",
        "SELECT string_agg(details_json->>'outcome', ',' ORDER BY id) FROM audit_event WHERE action = 'scenario_step'",
    )
    assert outcomes == "succeeded,precondition_failed"  # F13-FR-07


@pytest.mark.parametrize("step", ["ud-post-B5003", "interface-sync-B5003"])
def test_f13_ac03_both_b5003_steps_remove_it_from_the_air_gap_alerts(step: str) -> None:
    _reset()
    assert "B5003" in _air_gap_batches()
    _step(step)
    assert "B5003" not in _air_gap_batches()
    row = _maybe_row("B5003")
    if step == "interface-sync-B5003":
        assert row is not None and row["air_gap"] is False
        assert (
            row["ud_code"] is None and row["ud_date"] is None
        )  # the gap cleared with no usage decision posted
    else:
        assert (
            row is None or row["air_gap"] is False
        )  # released with the usage decision: out of the in-flight list
    status, body, _ = _run(f"/scenario/steps/{step}/run")  # the gap is gone: the step is not available twice
    assert status == 409 and "no longer an air gap" in body["detail"]["message"]


def test_f13_ac03_the_other_steps_do_what_their_titles_say() -> None:
    _reset()
    day = _get(f"{SCENARIO}/clock")["now_utc"]
    _step("advance-day")
    assert _get(f"{SCENARIO}/clock")["now_utc"] != day
    _reset()
    _step("open-deviation-B1042")
    assert _row("B1042")["deviation_light"] != "green"
    _step("close-deviation-B3150")
    assert _row("B3150")["deviation_light"] != "red"
    _step("run-pipeline")
    _step("pull-forward-B2077")
    assert _row("B2077")["adjusted_need_by_date"] == "2026-11-26"
    status, _, _ = _run("/scenario/steps/pull-forward-B2077/run")
    assert status == 409


def test_f13_ac05_reset_step_reset_returns_to_an_identical_state() -> None:
    _reset()
    before = _checksums()
    assert len(before) > 10
    _step("lims-approve-B1042")
    during = _checksums()
    assert during != before  # the step really changed something
    _reset()
    after = _checksums()
    assert after == before, sorted(k for k in before if before[k] != after.get(k))


@needs_recordings
def test_f13_ac05_the_agent_step_after_a_reset_gives_the_four_recorded_proposals() -> None:
    _reset()
    events = _step("airgap-agent")
    assert any("4 proposal(s) created" in e["message"] for e in events)
    proposals = _get(f"{AGENTS}/proposals")["rows"]
    assert len(proposals) == 4 and {p["status"] for p in proposals} == {
        "pending_approval"
    }  # replay: no misses
    assert sorted(p["id"] for p in proposals) == [1, 2, 3, 4]  # OQ-144: the same ids after every reset
    assert _scalar("app", "SELECT min(trace_id) FROM agent_trace") == "TR-0001"
    _reset()
    assert _get(f"{AGENTS}/proposals")["rows"] == []


def test_f13_fr06_the_admin_api_lists_the_steps_and_hides_the_token() -> None:
    steps = _get(f"{APP_API}/api/demo/steps")
    assert {s["id"] for s in steps} >= {"lims-approve-B1042", "airgap-agent", "pull-forward-B2077"}
    assert all(s["preconditions"] in ("met", "unmet") for s in steps)
    assert httpx.get(f"{APP_API}/api/demo/steps", headers=PAT, timeout=30).status_code == 403
    assert _get(f"{APP_API}/api/demo/steps").__str__().count(TOKEN["X-Scenario-Token"]) == 0
