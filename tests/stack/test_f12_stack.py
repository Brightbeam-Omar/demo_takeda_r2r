"""F12 acceptance tests against the real containers: the harness, the validator and the roles on real data.

Run with `make stack-test` (an isolated stack and lakehouse) or against a running `make up`. Like the F08 and F21
stack tests it seeds the source databases first, so it resets the data of the stack it talks to; `make seed` puts
the demo back afterwards. The tests that need a model answer (a real run) use the committed recordings and are
skipped, with the reason, while `services/agents/recordings/air_gap/` is empty; everything else runs without a
model: it builds the ticket a perfect model would write from the real tool results and uses that.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest
from agents.air_gap.schema import AirGapTicket, EvidenceItem
from agents.air_gap.validator import ValidationContext, validate_ticket
from agents.settings import Settings
from agents.tools.http import ReadOnlyHttp
from agents.tools.sources import fetch_deviations, fetch_erp_lot, fetch_lims_sample, fetch_row
from r2r_core import clock
from r2r_core.clock import source_from_env
from r2r_core.profile import load_profile

pytestmark = pytest.mark.stack

REPO_ROOT = Path(__file__).resolve().parents[2]
RECORDINGS = REPO_ROOT / "services" / "agents" / "recordings" / "air_gap"
needs_recordings = pytest.mark.skipif(
    not list(RECORDINGS.glob("*.json")),
    reason="no recordings yet: run `make record-agents` (needs ANTHROPIC_API_KEY with credit)",
)


def _port(name: str, default: str) -> str:
    return os.environ.get(name, default)


SCENARIO = f"http://localhost:{_port('SCENARIO_HOST_PORT', '8100')}"
ERP = f"http://localhost:{_port('ERP_HOST_PORT', '8101')}"
LIMS = f"http://localhost:{_port('LIMS_HOST_PORT', '8102')}"
QMS = f"http://localhost:{_port('QMS_HOST_PORT', '8103')}"
APP_API = f"http://localhost:{_port('APP_API_HOST_PORT', '8000')}"
AGENTS = f"http://localhost:{_port('AGENTS_HOST_PORT', '8200')}"
ALEX = {"X-Demo-User": "alex"}
PAT = {"X-Demo-User": "pat"}
ADMIN = {"X-Demo-User": "admin"}


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
PG_HOST, PG_PORT = "localhost", _port("POSTGRES_HOST_PORT", "5432")


def _connect(user: str, password: str) -> psycopg.Connection[Any]:
    return psycopg.connect(
        host=PG_HOST, port=PG_PORT, dbname="app", user=user, password=password, autocommit=True
    )


def _owner() -> psycopg.Connection[Any]:
    return _connect(_env("POSTGRES_USER", "r2r"), _env("POSTGRES_PASSWORD", "r2r_dev_only"))


def _reset_agent_state() -> None:
    """What F13's demo reset will do to the agent tables (OQ-144): one TRUNCATE, ids and the trace sequence restart."""
    with _owner() as connection:
        connection.execute("TRUNCATE action_log, proposal, agent_trace RESTART IDENTITY")
        connection.execute("ALTER SEQUENCE agent_trace_seq RESTART")
        connection.execute(
            "DELETE FROM audit_event WHERE action IN ('agent_run','proposal_created','proposal_approved',"
            "'proposal_executed','proposal_rejected','proposal_rejected_by_validator','forbidden')"
        )


def _get(url: str, headers: dict[str, str] | None = None) -> Any:
    response = httpx.get(url, headers=headers or ADMIN, timeout=30)
    assert response.status_code == 200, f"{url}: {response.status_code} {response.text}"
    return response.json()


def _run_pipeline() -> str:
    response = httpx.post(f"{SCENARIO}/pipeline/run?wait=true", headers=TOKEN, timeout=330)
    assert response.status_code == 200, response.text
    run_id: str = response.json()["run_id"]
    return run_id


def _wait_for(condition: Callable[[], bool], timeout: float, what: str) -> None:
    began = time.perf_counter()
    while time.perf_counter() - began < timeout:
        if condition():
            return
        time.sleep(0.5)
    raise AssertionError(f"timed out after {timeout:.0f} s waiting for {what}")


def _synced(run_id: str) -> bool:
    marks = _get(f"{APP_API}/api/sync/status")["watermarks"]
    return any(m["object_name"] == "batch_pipeline_v" and m["run_id"] == run_id for m in marks) and (
        _get(f"{APP_API}/api/sync/health")["pending"] == 0
    )


def _pipeline_and_sync() -> None:
    run_id = _run_pipeline()
    _wait_for(lambda: _synced(run_id), 90, "the run to reach the app")


@pytest.fixture(scope="module")
def seeded() -> None:
    env = {
        **os.environ,
        "POSTGRES_HOST": PG_HOST,
        "POSTGRES_PORT": PG_PORT,
        "POSTGRES_USER": _env("POSTGRES_USER", "r2r"),
        "POSTGRES_PASSWORD": _env("POSTGRES_PASSWORD", "r2r_dev_only"),
    }
    with tempfile.TemporaryDirectory() as artifacts:
        result = subprocess.run(
            [sys.executable, "-m", "datagen", "generate", "--profile", "site_a", "--artifacts", artifacts],
            check=False, cwd=REPO_ROOT, env=env, capture_output=True, text=True,
        )  # fmt: skip
    assert result.returncode == 0, f"datagen failed:\n{result.stdout}\n{result.stderr}"
    _pipeline_and_sync()
    _reset_agent_state()


@pytest.fixture
def http() -> Iterator[ReadOnlyHttp]:
    env = {
        "CLOCK_SOURCE": "http",
        "SCENARIO_URL": SCENARIO,
        "POSTGRES_HOST": PG_HOST,
        "POSTGRES_PORT": PG_PORT,
        "POSTGRES_USER": _env("POSTGRES_USER", "r2r"),
        "POSTGRES_PASSWORD": _env("POSTGRES_PASSWORD", "r2r_dev_only"),
    }
    clock.set_clock_source(source_from_env(env))
    settings = Settings.from_env({"APP_API_URL": APP_API, "ERP_URL": ERP, "LIMS_URL": LIMS, "QMS_URL": QMS})
    yield ReadOnlyHttp.from_settings(settings)
    clock.set_clock_source(None)


def _context(http: ReadOnlyHttp) -> ValidationContext:
    profile = load_profile("site_a")
    return ValidationContext(
        http=http, demo_user="admin", threshold_hours=profile.air_gap.threshold_hours,
        high_priority_days=profile.agents.air_gap.high_priority_days, now=clock.now(), today=clock.today(),
    )  # fmt: skip


def _row_key(http: ReadOnlyHttp, batch_no: str) -> str:
    rows = http.get_json("app", "/api/overview/insights", demo_user="admin")["rows"]
    return str(next(r["row_key"] for r in rows if r["batch_no"] == batch_no))


def _perfect_ticket(http: ReadOnlyHttp, row_key: str, **changes: Any) -> AirGapTicket:
    """The ticket a perfect model would write for ``row_key``, built from the real sources."""
    row = fetch_row(http, row_key, "admin")
    sample = fetch_lims_sample(http, row["sample_id"])
    lot = fetch_erp_lot(http, row["inspection_lot_no"])
    open_deviations = [d for d in fetch_deviations(http, row["batch_no"]) if d["status"] == "open"]
    need_by = date.fromisoformat(row["operative_need_by"]) if row["operative_need_by"] else None
    window = load_profile("site_a").agents.air_gap.high_priority_days
    high = row["late"] or (need_by is not None and (need_by - clock.today()).days <= window)
    evidence = [
        EvidenceItem(
            system="LIMS", ref=sample["sample_id"], field="approved_at", value=sample["approved_at"]
        ),
        EvidenceItem(system="ERP", ref=lot["prueflos"], field="results_recorded_at", value="none"),
        EvidenceItem(system="ERP", ref=lot["prueflos"], field="ud_code", value="none"),
        *[
            EvidenceItem(system="QMS", ref=d["deviation_no"], field="status", value="open")
            for d in open_deviations
        ],
    ]
    data: dict[str, Any] = {
        "row_key": row_key,
        "title": f"Batch {row['batch_no']}: LIMS approved, no ERP usage decision",
        "summary": f"LIMS approved sample {sample['sample_id']} for batch {row['batch_no']}; the ERP has no "
        f"usage decision for lot {lot['prueflos']}.",
        "evidence": evidence,
        "hours_in_gap": row["air_gap_hours"],
        "open_deviations": [d["deviation_no"] for d in open_deviations],
        "recommended_action": "investigate_deviation_first" if open_deviations else "post_usage_decision",
        "priority": "high" if high else "normal",
        "recipient_role": "qa_release",
    }
    data.update(changes)
    return AirGapTicket.model_validate(data)


def _insert_proposal(http: ReadOnlyHttp, row_key: str) -> int:
    """A proposal as the agent would have stored it: the perfect ticket and the real validator's verdict."""
    ticket = _perfect_ticket(http, row_key)
    result = validate_ticket(ticket, _context(http))
    assert result.passed, result.headline
    with _owner() as connection:
        row = connection.execute(
            "INSERT INTO proposal (agent_key, row_key, kind, payload_json, evidence_json, validator_result_json, status, "
            "required_role, created_at) VALUES ('air_gap', %s, 'airgap_ticket', %s::jsonb, %s::jsonb, %s::jsonb, "
            "'pending_approval', 'qa_release', now()) RETURNING id",
            (
                row_key,
                ticket.model_dump_json(),
                json.dumps([e.model_dump() for e in ticket.evidence]),
                result.model_dump_json(),
            ),
        ).fetchone()
    assert row is not None
    return int(row[0])


# --- no model needed -------------------------------------------------------------------------------


def test_f12_ac07_the_agents_role_cannot_insert_into_override_value_on_the_real_database(
    seeded: None,
) -> None:
    password = _env("AGENTS_DB_PASSWORD", "agents_dev_only")
    with _connect("agents_rw", password) as connection:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                "INSERT INTO override_value (row_key, field, value_json, version, author_user_key, created_at, "
                "is_current) VALUES ('k', 'expedite', 'true', 1, 'pat', now(), true)"
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("SELECT * FROM status_log")
        connection.execute("INSERT INTO audit_event (at, action) VALUES (now(), 'forbidden')")  # allowed
    _reset_agent_state()


def test_f12_fr04_the_tools_read_the_real_sources_and_give_the_same_text_twice(
    seeded: None, http: ReadOnlyHttp
) -> None:
    from agents.tools.registry import read_only_tools

    registry = read_only_tools(http)
    key = _row_key(http, "B5003")
    first = registry.call("get_row", {"row_key": key}, "admin")
    assert not first.is_error and registry.call("get_row", {"row_key": key}, "admin").content == first.content
    row = fetch_row(http, key, "admin")
    assert row["air_gap"] is True and row["air_gap_hours"] == 30 and row["lims_status"] == "approved"
    assert fetch_lims_sample(http, row["sample_id"])["status"] == "approved"
    lot = fetch_erp_lot(http, row["inspection_lot_no"])
    assert lot["ud_code"] is None and lot["results_recorded_at"] is None
    assert registry.call("list_deviations", {"batch_no": "B5003"}, "admin").content == "[]"
    assert registry.call("get_erp_lot", {"prueflos": "99999999"}, "admin").is_error


def test_f12_fr07_a_correct_ticket_passes_v1_to_v6_on_real_data_and_a_wrong_one_fails_the_right_rule(
    seeded: None, http: ReadOnlyHttp
) -> None:
    for batch_no in (
        "B5003",
        "B1475",
        "B1363",
        "B1518",
    ):  # all four demo-start air gaps, with and without a deviation
        key = _row_key(http, batch_no)
        result = validate_ticket(_perfect_ticket(http, key), _context(http))
        assert result.passed, f"{batch_no}: {result.headline}"
        assert all(e.verified for e in result.evidence)
    key = _row_key(http, "B5003")
    bad_hours = validate_ticket(_perfect_ticket(http, key, hours_in_gap=33), _context(http))
    assert [r.id for r in bad_hours.rules if not r.passed] == ["V3"]
    bad_text = validate_ticket(
        _perfect_ticket(http, key, summary="Batch B5003 and batch B9999."), _context(http)
    )
    assert [r.id for r in bad_text.rules if not r.passed] == ["V6"]


def test_f12_fr12_the_agent_card_and_reads_through_the_proxy_and_role_checks(seeded: None) -> None:
    card = _get(f"{AGENTS}/agents", ALEX)[0]
    assert (card["key"], card["prompt_version"], card["provider"], card["can_run"]) == (
        "air_gap",
        "v1",
        "replay",
        True,
    )
    assert _get(f"{AGENTS}/agents", PAT)[0]["can_run"] is False
    run = httpx.post(f"{AGENTS}/agents/air_gap/run", headers=PAT, json={}, timeout=30)
    assert run.status_code == 403
    assert httpx.get(f"{AGENTS}/proposals", headers={"X-Demo-User": "nobody"}, timeout=10).status_code == 401
    with _owner() as connection:
        row = connection.execute(
            "SELECT actor_user_key FROM audit_event WHERE action = 'forbidden' ORDER BY id DESC"
        ).fetchone()
    assert row is not None and row[0] == "pat"
    _reset_agent_state()


def test_f12_ac02_pat_cannot_approve_alex_can_and_the_ticket_email_and_audit_are_written(
    seeded: None, http: ReadOnlyHttp
) -> None:
    _reset_agent_state()
    pid = _insert_proposal(http, _row_key(http, "B1363"))
    assert httpx.post(f"{AGENTS}/proposals/{pid}/approve", headers=PAT, timeout=30).status_code == 403
    response = httpx.post(f"{AGENTS}/proposals/{pid}/approve", headers=ALEX, timeout=60)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "executed" and body["decided_by"] == "alex"
    assert [a["action_type"] for a in body["actions"]] == ["ticket_created", "email_queued"]
    assert body["actions"][1]["rendered"]["delivery"] == "Sent to outbox (demo)"
    assert "B1363" in body["actions"][1]["rendered"]["subject"]
    audit = _get(f"{APP_API}/api/audit?action=proposal_executed")["items"]
    assert audit[0]["actor_user_key"] == "alex" and audit[0]["row_key"] == body["row_key"]
    again = httpx.post(f"{AGENTS}/proposals/{pid}/approve", headers=ADMIN, timeout=30)
    assert again.status_code == 200 and again.json()["decided_by"] == "alex"  # idempotent
    _reset_agent_state()


def test_f12_ac04_a_usage_decision_before_approval_makes_approve_fail_v1_with_air_gap_resolved(
    seeded: None, http: ReadOnlyHttp
) -> None:
    _reset_agent_state()
    key = _row_key(http, "B1475")
    pid = _insert_proposal(http, key)
    lot = fetch_row(http, key, "admin")["inspection_lot_no"]
    posted = httpx.post(
        f"{ERP}/events/usage-decision", json={"prueflos": lot, "vcode": "A"}, headers=TOKEN, timeout=30
    )
    assert posted.status_code in (200, 201), posted.text
    _pipeline_and_sync()
    response = httpx.post(f"{AGENTS}/proposals/{pid}/approve", headers=ALEX, timeout=60)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "rejected_by_validator" and body["validator"]["headline"] == "Air gap resolved"
    assert body["actions"] == []
    assert httpx.post(f"{AGENTS}/proposals/{pid}/approve", headers=ALEX, timeout=30).status_code == 409
    _reset_agent_state()


def test_f12_ac09_a_replay_miss_is_a_409_with_the_hint_not_a_crash(seeded: None, http: ReadOnlyHttp) -> None:
    """A changed fact (a new open deviation) makes the situation differ from every recording."""
    _reset_agent_state()
    key = _row_key(http, "B1518")
    row = fetch_row(http, key, "admin")
    opened = httpx.post(
        f"{QMS}/events/deviation-opened",
        json={"title": "Stack test excursion", "severity": "minor",
              "links": [{"material_no": row["material_no"], "batch_no": row["batch_no"]}]},
        headers=TOKEN, timeout=30,
    )  # fmt: skip
    assert opened.status_code in (200, 201), opened.text
    _pipeline_and_sync()
    response = httpx.post(f"{AGENTS}/agents/air_gap/run", headers=ALEX, json={"row_key": key}, timeout=60)
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"] == "replay_miss" and "make record-agents" in detail["message"]
    assert detail["replay_miss"]["key"] in detail["message"] and "demo-start" in detail["replay_miss"]["hint"]
    trace = _get(f"{AGENTS}/traces/{detail['errors'][0]['trace_id']}", ALEX)
    assert trace["steps"][-1]["payload"]["outcome"] == "replay_miss"
    assert _get(f"{AGENTS}/proposals", ALEX)["rows"] == []
    _reset_agent_state()


def test_f12_fr14_pause_and_resume_need_the_token_and_report_state(seeded: None) -> None:
    assert httpx.post(f"{AGENTS}/agents/autorun/pause", timeout=10).status_code == 401
    paused = httpx.post(f"{AGENTS}/agents/autorun/pause", headers=TOKEN, timeout=10).json()
    assert paused["paused"] is True
    resumed = httpx.post(f"{AGENTS}/agents/autorun/resume", headers=TOKEN, timeout=10).json()
    assert resumed["paused"] is False and resumed["cursor"]


# --- needs the recordings --------------------------------------------------------------------------


@needs_recordings
def test_f12_ac01_run_creates_a_pending_proposal_for_b5003_that_passes_v1_to_v6_from_the_recordings(
    seeded: None, http: ReadOnlyHttp
) -> None:
    _reset_agent_state()
    response = httpx.post(f"{AGENTS}/agents/air_gap/run", headers=ALEX, json={}, timeout=120)
    assert response.status_code == 200, response.text
    created = {c["row_key"]: c for c in response.json()["created"]}
    assert len(created) == 4 and all(c["status"] == "pending_approval" for c in created.values())
    b5003 = created[_row_key(http, "B5003")]
    detail = _get(f"{AGENTS}/proposals/{b5003['proposal_id']}", ALEX)
    assert detail["validator"]["passed"] is True and detail["batch_no"] == "B5003"
    trace = _get(f"{AGENTS}/traces/{b5003['trace_id']}", ALEX)
    kinds = [s["step_type"] for s in trace["steps"]]
    assert kinds[0] == "input" and kinds[-3:] == ["validation", "decision", "action"]
    calls = [s for s in trace["steps"] if s["step_type"] == "tool_call"]
    assert len(calls) >= 3 and len({s["payload"]["system"] for s in calls}) >= 2  # F12-AC-05
    assert trace["replayed"] is True
    again = httpx.post(f"{AGENTS}/agents/air_gap/run", headers=ALEX, json={}, timeout=60).json()  # F12-AC-06
    assert again["created"] == [] and len(again["skipped"]) == 4
    assert _get(f"{AGENTS}/proposals", ALEX)["counts"]["pending_approval"] == 4
    _reset_agent_state()
