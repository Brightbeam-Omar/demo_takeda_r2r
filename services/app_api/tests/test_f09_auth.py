"""F09 T1: persona dependency, role checks, /me, /users, /clock (F09-FR-05, F09-AC-01)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration


def audit(factory: sessionmaker[Session]) -> list[tuple[str, str | None, str | None, dict[str, object]]]:
    with factory() as session:
        rows = session.execute(
            text("SELECT action, actor_user_key, row_key, details_json FROM audit_event ORDER BY id")
        )
        return [(r[0], r[1], r[2], r[3]) for r in rows]


def test_f09_fr05_me_defaults_to_pat_and_follows_the_header(client: TestClient) -> None:
    assert client.get("/api/me").json() == {"user_key": "pat", "display_name": "Pat", "role": "planner"}
    sam = client.get("/api/me", headers={"X-Demo-User": "sam"}).json()
    assert sam["role"] == "viewer"


def test_f09_fr05_an_unknown_user_is_401(client: TestClient) -> None:
    assert client.get("/api/me", headers={"X-Demo-User": "nobody"}).status_code == 401


def test_f09_fr05_the_header_is_rejected_outside_demo_mode(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    assert client.get("/api/me", headers={"X-Demo-User": "pat"}).status_code == 401
    assert client.get("/api/users").status_code == 404


def test_f09_fr05_users_lists_the_five_personas_without_an_identity(client: TestClient) -> None:
    keys = [u["user_key"] for u in client.get("/api/users").json()]
    assert keys == ["admin", "alex", "pat", "quinn", "sam"]


def test_f09_ac01_a_forbidden_call_is_403_and_audited(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    response = client.post("/api/sync/trigger", headers={"X-Demo-User": "sam"})
    assert response.status_code == 403
    [(action, actor, row_key, details)] = audit(app_factory)
    assert (action, actor, row_key) == ("forbidden", "sam", None)
    assert details == {
        "method": "POST",
        "path": "/api/sync/trigger",
        "required_roles": ["admin"],
        "role": "viewer",
    }


def test_f09_fr05_clock_falls_back_to_the_app_clock_when_scenario_is_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCENARIO_URL", "http://127.0.0.1:9")
    body = client.get("/api/clock").json()
    assert body["now_utc"].startswith("2026-10-12T07:00:00") and body["today_local"] == "2026-10-12"
