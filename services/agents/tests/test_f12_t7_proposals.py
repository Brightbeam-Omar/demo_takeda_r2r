"""F12 T7: candidates, proposals, approve and reject with roles, idempotency [F12-FR-08, AC-01, AC-02, AC-04..06, AC-09]."""

from collections.abc import Callable
from typing import Any

import pytest
from agent_support import ROW_KEY, B5003Model, row_body, source_transport
from agents.gateway.replay import ReplayGateway
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

pytestmark = pytest.mark.integration

ALEX = {"X-Demo-User": "alex"}
PAT = {"X-Demo-User": "pat"}
Build = Callable[..., TestClient]


def _run(client: TestClient, headers: dict[str, str] = ALEX, **body: Any) -> Any:
    return client.post("/agents/air_gap/run", headers=headers, json=body)


def _audit(owner_engine: Engine) -> list[tuple[str | None, str]]:
    with owner_engine.connect() as connection:
        return [
            tuple(r)
            for r in connection.execute(text("SELECT actor_user_key, action FROM audit_event ORDER BY id"))
        ]


def test_f12_ac01_run_creates_a_proposal_for_b5003_that_passes_v1_to_v6(build_app: Build) -> None:
    client = build_app()
    response = _run(client)
    assert response.status_code == 200
    created = response.json()["created"]
    assert [(c["row_key"], c["status"]) for c in created] == [(ROW_KEY, "pending_approval")]
    detail = client.get(f"/proposals/{created[0]['proposal_id']}", headers=ALEX).json()
    assert detail["status"] == "pending_approval" and detail["required_role"] == "qa_release"
    assert detail["validator"]["passed"] is True
    assert [r["id"] for r in detail["validator"]["rules"]] == ["V1", "V2", "V3", "V4", "V5", "V6"]
    assert all(r["passed"] for r in detail["validator"]["rules"])
    assert all(e["verified"] for e in detail["validator"]["evidence"])
    assert detail["batch_no"] == "B5003" and detail["priority"] == "high" and detail["hours_in_gap"] == 30
    assert detail["trace_id"] == "TR-0001"


def test_f12_ac05_the_trace_runs_input_tools_model_validation_decision_action(build_app: Build) -> None:
    client = build_app()
    trace_id = _run(client).json()["created"][0]["trace_id"]
    trace = client.get(f"/traces/{trace_id}", headers=ALEX).json()
    kinds = [s["step_type"] for s in trace["steps"]]
    assert kinds[0] == "input" and kinds[-3:] == ["validation", "decision", "action"]
    assert [s["seq"] for s in trace["steps"]] == list(range(1, len(kinds) + 1))
    calls = [s for s in trace["steps"] if s["step_type"] == "tool_call"]
    systems = {s["payload"]["system"] for s in calls}
    assert len(calls) >= 3 and len(systems) >= 2
    assert kinds.index("model_request") < kinds.index("tool_call") < kinds.index("validation")
    assert kinds.count("model_request") == kinds.count("model_response") == 4
    assert trace["totals"]["model_calls"] == 4 and trace["totals"]["tokens_in"] == 10000
    assert trace["totals"]["cost_usd"] == pytest.approx(10 * 0.003 + 0.4 * 0.015)
    assert trace["provider"] == "scripted" and trace["proposal_id"] == 1


def test_f12_ac06_running_twice_creates_no_duplicate_open_proposal(
    build_app: Build, owner_engine: Engine
) -> None:
    client = build_app()
    assert len(_run(client).json()["created"]) == 1
    second = _run(client).json()
    assert second["created"] == [] and [s["row_key"] for s in second["skipped"]] == [ROW_KEY]
    again = _run(client, row_key=ROW_KEY).json()
    assert again["created"] == [] and again["skipped"][0]["message"] == "already has an open proposal"
    with owner_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM proposal")).scalar_one() == 1


def test_f12_ac02_pat_cannot_approve_alex_can_and_the_ticket_and_email_are_logged(
    build_app: Build, owner_engine: Engine
) -> None:
    client = build_app()
    pid = _run(client).json()["created"][0]["proposal_id"]
    assert client.post(f"/proposals/{pid}/approve", headers=PAT).status_code == 403
    assert client.get(f"/proposals/{pid}", headers=PAT).json()["status"] == "pending_approval"
    done = client.post(f"/proposals/{pid}/approve", headers=ALEX)
    assert done.status_code == 200
    body = done.json()
    assert body["status"] == "executed" and body["decided_by"] == "alex"
    assert [a["action_type"] for a in body["actions"]] == ["ticket_created", "email_queued"]
    email = body["actions"][1]["rendered"]
    assert email["delivery"] == "Sent to outbox (demo)" and "TKT-0001" in email["subject"]
    assert body["validator"]["passed"] is True
    audit = _audit(owner_engine)
    assert ("pat", "forbidden") in audit
    assert [a for a in audit if a[1] in ("proposal_approved", "proposal_executed")] == [
        ("alex", "proposal_approved"),
        ("alex", "proposal_executed"),
    ]
    assert ("agent:air_gap", "proposal_created") in audit and ("alex", "agent_run") in audit
    trace = client.get("/traces/TR-0001", headers=ALEX).json()
    kinds = [s["step_type"] for s in trace["steps"]]
    assert (
        kinds[-3:] == ["validation", "decision", "action"]
        and trace["steps"][-1]["payload"]["ticket_no"] == "TKT-0001"
    )


def test_f12_fr08_approve_is_idempotent(build_app: Build, owner_engine: Engine) -> None:
    client = build_app()
    pid = _run(client).json()["created"][0]["proposal_id"]
    first = client.post(f"/proposals/{pid}/approve", headers=ALEX).json()
    second = client.post(f"/proposals/{pid}/approve", headers={"X-Demo-User": "admin"})
    assert second.status_code == 200 and second.json()["decided_by"] == "alex"
    assert len(second.json()["actions"]) == len(first["actions"]) == 2
    with owner_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM action_log")).scalar_one() == 2


def test_f12_ac04_a_usage_decision_before_approval_fails_v1_with_air_gap_resolved(build_app: Build) -> None:
    client = build_app()
    pid = _run(client).json()["created"][0]["proposal_id"]
    resolved = source_transport(row=row_body(air_gap=False, air_gap_hours=0, ud_code="A"), ud_code="A")
    client.app.state.deps.http = type(client.app.state.deps.http).from_settings(  # type: ignore[attr-defined]
        client.app.state.deps.settings,
        transport=resolved,  # type: ignore[attr-defined]
    )
    response = client.post(f"/proposals/{pid}/approve", headers=ALEX)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected_by_validator" and body["actions"] == []
    assert body["validator"]["headline"] == "Air gap resolved"
    assert next(r for r in body["validator"]["rules"] if r["id"] == "V1")["passed"] is False
    assert client.post(f"/proposals/{pid}/approve", headers=ALEX).status_code == 409  # final
    trace = client.get("/traces/TR-0001", headers=ALEX).json()
    assert trace["steps"][-1]["payload"]["outcome"] == "rejected_by_validator"


def test_f12_fr08_reject_needs_the_role_and_a_reason(build_app: Build, owner_engine: Engine) -> None:
    client = build_app()
    pid = _run(client).json()["created"][0]["proposal_id"]
    assert (
        client.post(f"/proposals/{pid}/reject", headers=PAT, json={"reason": "not needed now"}).status_code
        == 403
    )
    assert client.post(f"/proposals/{pid}/reject", headers=ALEX, json={"reason": "no"}).status_code == 422
    done = client.post(f"/proposals/{pid}/reject", headers=ALEX, json={"reason": "Handled by phone already"})
    assert done.status_code == 200 and done.json()["status"] == "rejected"
    assert (
        done.json()["decision_reason"] == "Handled by phone already" and done.json()["decided_by"] == "alex"
    )
    assert client.post(f"/proposals/{pid}/approve", headers=ALEX).status_code == 409
    assert (
        client.post(f"/proposals/{pid}/reject", headers=ALEX, json={"reason": "again please"}).status_code
        == 409
    )
    assert ("alex", "proposal_rejected") in _audit(owner_engine)
    # a human rejection closes the proposal, so a manual run proposes again (OQ-137)
    assert len(_run(client, row_key=ROW_KEY).json()["created"]) == 1


def test_f12_fr08_running_needs_qa_release_or_admin(build_app: Build) -> None:
    client = build_app()
    for user in ("pat", "quinn", "sam"):
        assert _run(client, {"X-Demo-User": user}).status_code == 403
    assert _run(client, {"X-Demo-User": "admin"}).status_code == 200
    assert client.get("/proposals", headers={"X-Demo-User": "sam"}).status_code == 200  # reads are open
    assert client.get("/proposals", headers={"X-Demo-User": "nobody"}).status_code == 401


def test_f12_fr07_a_draft_that_fails_the_validator_is_stored_as_rejected_by_validator(
    build_app: Build,
) -> None:
    client = build_app(gateway=B5003Model(hours_in_gap=40))
    created = _run(client).json()["created"][0]
    assert created["status"] == "rejected_by_validator" and "40 h" in created["message"]
    detail = client.get(f"/proposals/{created['proposal_id']}", headers=ALEX).json()
    assert [r["id"] for r in detail["validator"]["rules"] if not r["passed"]] == ["V3"]
    assert client.post(f"/proposals/{created['proposal_id']}/approve", headers=ALEX).status_code == 409
    # the only way forward is to run again, which is allowed because the proposal is closed
    client.app.state.deps.gateway = B5003Model()  # type: ignore[attr-defined]
    assert _run(client).json()["created"][0]["status"] == "pending_approval"
    listing = client.get("/proposals", headers=ALEX).json()
    assert listing["counts"]["rejected_by_validator"] == 1 and listing["counts"]["pending_approval"] == 1
    assert [r["id"] for r in listing["rows"]] == [2, 1]
    only = client.get("/proposals?status=rejected_by_validator", headers=ALEX).json()
    assert [r["id"] for r in only["rows"]] == [1] and only["counts"]["pending_approval"] == 1


def test_f12_ac09_a_replay_miss_is_a_clear_409_with_the_hint_and_a_trace(
    build_app: Build, tmp_path: Any
) -> None:
    client = build_app(gateway=ReplayGateway(tmp_path))
    response = _run(client)
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"] == "replay_miss"
    assert "make record-agents" in detail["message"] and detail["replay_miss"]["key"] in detail["message"]
    assert "demo-start" in detail["replay_miss"]["hint"]
    trace = client.get("/traces/TR-0001", headers=ALEX).json()
    assert trace["steps"][-1]["payload"]["outcome"] == "replay_miss"
    assert client.get("/proposals", headers=ALEX).json()["rows"] == []  # nothing half-created


def test_f12_oq145_a_run_with_no_valid_ticket_is_a_visible_rejected_proposal(build_app: Build) -> None:
    # a model whose final submission never matches the schema (it only sends the row key), twice in a row
    from agents.gateway.base import ModelResult, ToolUseBlock

    class Garbage(B5003Model):
        def generate(self, **kwargs: Any) -> ModelResult:
            if kwargs["turn"] < 4:
                return super().generate(**kwargs)
            bad = ToolUseBlock(id="toolu_x", name="submit_ticket", input={"row_key": ROW_KEY})
            return ModelResult(
                content=[bad], stop_reason="tool_use", tokens_in=1, tokens_out=1, latency_ms=1, model_id="m"
            )

    client = build_app(gateway=Garbage())
    created = _run(client).json()["created"][0]
    assert created["status"] == "rejected_by_validator"
    detail = client.get(f"/proposals/{created['proposal_id']}", headers=ALEX).json()
    assert detail["validator"]["rules"][0]["id"] == "V0" and "title" in detail["validator"]["headline"]
    assert detail["error"] and detail["payload"]["run_status"] == "schema_error"


def test_f12_fr08_unknown_ids_and_non_air_gap_rows(build_app: Build) -> None:
    client = build_app()
    assert client.get("/proposals/99", headers=ALEX).status_code == 404
    assert client.post("/proposals/99/approve", headers=ALEX).status_code == 404
    assert client.get("/traces/TR-9999", headers=ALEX).status_code == 404
    response = _run(client, row_key="RM1|B1|1")
    assert response.status_code == 409 and "not an air gap" in response.json()["detail"]["message"]


def test_f12_fr12_the_agent_card(build_app: Build) -> None:
    client = build_app()
    card = client.get("/agents", headers=ALEX).json()[0]
    assert (card["key"], card["prompt_version"], card["can_run"], card["last_run_at"]) == (
        "air_gap",
        "v1",
        True,
        None,
    )
    assert card["tools"] == [
        "get_row",
        "get_lims_sample",
        "get_lims_results",
        "get_erp_lot",
        "list_deviations",
    ]
    assert client.get("/agents", headers=PAT).json()[0]["can_run"] is False
    _run(client)
    after = client.get("/agents", headers=ALEX).json()[0]
    assert after["proposals_total"] == 1 and after["last_run_at"] is not None


def test_f12_oq146_trace_payloads_never_carry_the_key(
    build_app: Build, owner_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-sentinel-0123456789")
    client = build_app()
    _run(client)
    with owner_engine.connect() as connection:
        dump = str(connection.execute(text("SELECT payload_json::text FROM agent_trace")).all())
        dump += str(
            connection.execute(
                text("SELECT payload_json::text, validator_result_json::text FROM proposal")
            ).all()
        )
    assert "sk-ant-test-sentinel" not in dump
