"""F12 T1: the service skeleton, identity through app-api and the restricted database role."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError


def test_f12_fr01_health() -> None:
    from agent_support import fake_app_api
    from agents.main import create_app
    from agents.settings import Settings

    client = TestClient(create_app(Settings.from_env({}), None, fake_app_api()))
    assert client.get("/health").json() == {"status": "ok", "service": "agents"}


def test_f12_fr10_role_comes_from_app_api_not_the_request() -> None:
    from agent_support import fake_app_api
    from agents.main import create_app
    from agents.settings import Settings

    client = TestClient(create_app(Settings.from_env({}), None, fake_app_api()))
    assert client.get("/me", headers={"X-Demo-User": "alex"}).json() == {
        "user_key": "alex",
        "display_name": "Alex",
        "role": "qa_release",
    }
    assert client.get("/me").json()["user_key"] == "pat"  # no header: the app's default persona
    assert client.get("/me", headers={"X-Demo-User": "nobody"}).status_code == 401
    # a role in the request is ignored
    assert client.get("/me", headers={"X-Demo-User": "pat", "X-Role": "admin"}).json()["role"] == "planner"


@pytest.mark.integration
def test_f12_ac07_agents_role_cannot_insert_into_override_value(agents_engine: Engine) -> None:
    """F12-AC-07: permission denied on override_value (and on the rest of the app)."""
    with pytest.raises(DBAPIError, match="permission denied"), agents_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO override_value (row_key, field, value_json, version, author_user_key, created_at, is_current) "
                "VALUES ('k', 'expedite', 'true', 1, 'pat', now(), true)"
            )
        )
    for statement in (
        "SELECT 1 FROM override_value",
        "SELECT 1 FROM status_log",
        "UPDATE audit_event SET action = 'x'",
        "DELETE FROM proposal",
        "UPDATE agent_trace SET seq = 1",
    ):
        with pytest.raises(DBAPIError, match="permission denied"), agents_engine.begin() as connection:
            connection.execute(text(statement))


@pytest.mark.integration
def test_f12_fr01_agents_role_writes_exactly_the_four_tables(agents_engine: Engine) -> None:
    with agents_engine.begin() as connection:
        proposal_id = connection.execute(
            text(
                "INSERT INTO proposal (agent_key, row_key, kind, status, required_role, created_at) "
                "VALUES ('air_gap', 'r1', 'airgap_ticket', 'pending_approval', 'qa_release', now()) RETURNING id"
            )
        ).scalar_one()
        connection.execute(text("UPDATE proposal SET status = 'rejected' WHERE id = :i"), {"i": proposal_id})
        connection.execute(
            text("INSERT INTO action_log (proposal_id, action_type, executed_at) VALUES (:i, 'x', now())"),
            {"i": proposal_id},
        )
        connection.execute(
            text("INSERT INTO agent_trace (trace_id, seq, step_type, at) VALUES ('TR-1', 1, 'input', now())")
        )
        connection.execute(text("INSERT INTO audit_event (at, action) VALUES (now(), 'agent_run')"))
        assert connection.execute(text("SELECT nextval('agent_trace_seq')")).scalar_one() == 1


@pytest.mark.integration
def test_f12_fr08_one_open_proposal_per_row_and_kind(agents_engine: Engine) -> None:
    insert = (
        "INSERT INTO proposal (agent_key, row_key, kind, status, required_role, created_at) "
        "VALUES ('air_gap', 'r1', 'airgap_ticket', :s, 'qa_release', now())"
    )
    with agents_engine.begin() as connection:
        connection.execute(text(insert), {"s": "rejected_by_validator"})
        connection.execute(text(insert), {"s": "rejected"})  # closed ones may repeat
        connection.execute(text(insert), {"s": "pending_approval"})
    for status in ("pending_approval", "approved", "executed"):
        with pytest.raises(IntegrityError), agents_engine.begin() as connection:
            connection.execute(text(insert), {"s": status})
    with agents_engine.begin() as connection:  # another row is independent
        connection.execute(text(insert.replace("'r1'", "'r2'")), {"s": "pending_approval"})


@pytest.mark.integration
def test_f12_fr10_a_refused_write_leaves_a_forbidden_audit_row(
    make_client: Callable[[], TestClient], agents_engine: Engine, owner_engine: Engine
) -> None:
    from agents.auth import require_role
    from fastapi import Depends

    client = make_client()

    @client.app.post("/probe")  # type: ignore[attr-defined]
    def probe(_: object = Depends(require_role("qa_release", "admin"))) -> dict[str, bool]:
        return {"ok": True}

    assert client.post("/probe", headers={"X-Demo-User": "pat"}).status_code == 403
    assert client.post("/probe", headers={"X-Demo-User": "alex"}).status_code == 200
    with owner_engine.connect() as connection:
        rows = connection.execute(text("SELECT actor_user_key, action, details_json FROM audit_event")).all()
    assert [(r[0], r[1]) for r in rows] == [("pat", "forbidden")]
    assert rows[0][2]["required_roles"] == ["qa_release", "admin"]
