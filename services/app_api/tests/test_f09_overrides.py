"""F09 T4 [TDD]: overrides with versioning and audit: need-by, status, comments (F09-FR-04, AC-01..03)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from r2r_core.profile import load_profile
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import batch, load_mirror

pytestmark = pytest.mark.integration

ROW = "RM10031|B2077|9001"
URL = f"/api/rows/{ROW}/need-by"
PULLED = {"adjusted_date": "2026-11-26", "reason_code": "CAMPAIGN_PULLED_FORWARD", "note": "campaign moved"}


@pytest.fixture(autouse=True)
def mirror(app_factory: sessionmaker[Session]) -> None:
    load_mirror(
        app_factory, load_profile("site_a"), [batch(), batch("B9", stage_key="released", ud_effective=True)]
    )


def query(factory: sessionmaker[Session], sql: str) -> list[Any]:
    with factory() as session:
        return [tuple(r) for r in session.execute(text(sql))]


def versions(factory: sessionmaker[Session], field: str = "adjusted_need_by_date") -> list[Any]:
    return query(
        factory,
        f"SELECT version, value_json, reason_code, is_current, author_user_key FROM override_value "
        f"WHERE field = '{field}' ORDER BY id",
    )


def row(client: TestClient) -> dict[str, Any]:
    found = [r for r in client.get("/api/overview").json()["rows"] if r["row_key"] == ROW]
    return found[0]  # type: ignore[no-any-return]


def test_f09_ac02_pulling_b2077_forward_compresses_the_plan(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    before = row(client)
    assert before["plan"]["expected_completion"] == "2026-10-15" and before["plan"]["rag"] == "green"

    response = client.put(URL, json=PULLED)
    assert response.status_code == 200, response.text
    plan = response.json()["plan"]
    assert plan["compressed"] is True
    assert plan["effective_slas"] == {"sampling": 6, "qc_testing": 37, "qa_release": 6}
    assert (plan["expected_completion"], plan["rag"]) == ("2026-10-14", "amber")
    assert response.json()["operative_need_by"] == "2026-11-26"
    assert versions(app_factory) == [(1, "2026-11-26", "CAMPAIGN_PULLED_FORWARD", True, "pat")]
    assert row(client)["plan"]["rag"] == "amber"  # the next read sees it

    again = client.put(URL, json=PULLED | {"adjusted_date": "2026-11-20"})
    assert again.status_code == 200
    assert [(v[0], v[3]) for v in versions(app_factory)] == [(1, False), (2, True)]


def test_f09_ac03_clearing_restores_the_system_date_and_keeps_history(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    client.put(URL, json=PULLED)
    cleared = client.put(URL, json={"adjusted_date": None}).json()
    assert cleared["operative_need_by"] == "2026-12-03" == cleared["system_need_by_locked"]
    assert cleared["adjusted_need_by_date"] is None and cleared["plan"]["expected_completion"] == "2026-10-15"
    assert [(v[0], v[1], v[3]) for v in versions(app_factory)] == [
        (1, "2026-11-26", False),
        (2, None, True),
    ]
    actions = query(app_factory, "SELECT action FROM audit_event ORDER BY id")
    assert actions == [("need_by_set",), ("need_by_cleared",)]


def test_f09_fr04_the_audit_event_holds_field_old_new_reason_and_note(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    client.put(URL, json=PULLED)
    client.put(URL, json=PULLED | {"adjusted_date": "2026-11-20", "reason_code": "EXPEDITE_SHIPPING"})
    [first, second] = query(
        app_factory, "SELECT actor_user_key, row_key, details_json FROM audit_event ORDER BY id"
    )
    assert first[:2] == ("pat", ROW)
    assert first[2] == {"field": "adjusted_need_by_date", "old": None, "new": "2026-11-26",
                        "reason_code": "CAMPAIGN_PULLED_FORWARD", "note": "campaign moved"}  # fmt: skip
    assert second[2]["old"] == "2026-11-26" and second[2]["new"] == "2026-11-20"


def test_f09_fr04_only_changed_fields_are_versioned_and_a_noop_writes_nothing(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    client.put(URL, json=PULLED)
    client.put(URL, json=PULLED)  # identical: nothing happens
    assert len(versions(app_factory)) == 1 and len(query(app_factory, "SELECT 1 FROM audit_event")) == 1

    client.put(URL, json=PULLED | {"expedite": True})  # only expedite changes
    assert len(versions(app_factory)) == 1
    assert versions(app_factory, "expedite") == [(1, True, None, True, "pat")]
    assert query(app_factory, "SELECT action FROM audit_event ORDER BY id")[-1] == ("expedite_set",)
    assert row(client)["expedite"] is True and row(client)["flags"]["expedite"] is True

    client.put(URL, json={"adjusted_date": None, "expedite": False})  # clears both
    assert [a[0] for a in query(app_factory, "SELECT action FROM audit_event ORDER BY id")][-2:] == [
        "need_by_cleared",
        "expedite_cleared",
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"adjusted_date": "2026-11-26"},
        {"adjusted_date": "2026-11-26", "reason_code": "NOT_A_CODE"},
    ],
)
def test_f09_fr04_a_date_needs_a_known_reason_code(client: TestClient, body: dict[str, Any]) -> None:
    assert client.put(URL, json=body).status_code == 422


def test_f09_fr04_unknown_rows_are_404_and_released_rows_409(client: TestClient) -> None:
    assert client.put("/api/rows/NOPE%7CX%7C1/need-by", json=PULLED).status_code == 404
    released = "RM10031|B9|9001"
    assert client.put(f"/api/rows/{released}/need-by", json=PULLED).status_code == 409


def test_f09_fr04_a_past_date_is_accepted(client: TestClient) -> None:
    response = client.put(URL, json=PULLED | {"adjusted_date": "2026-09-01"})
    assert response.status_code == 200 and response.json()["plan"]["late"] is True
    assert response.json()["plan"]["late_reason_auto"] == "CAMPAIGN_PULLED_FORWARD"


def test_f09_ac01_a_viewer_cannot_set_a_need_by(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    response = client.put(URL, json=PULLED, headers={"X-Demo-User": "sam"})
    assert response.status_code == 403
    assert versions(app_factory) == []
    [(action, actor, row_key)] = query(app_factory, "SELECT action, actor_user_key, row_key FROM audit_event")
    assert (action, actor, row_key) == ("forbidden", "sam", ROW)


@pytest.mark.parametrize(
    ("method", "path", "user", "ok"),
    [
        ("PUT", f"/api/rows/{ROW}/need-by", "pat", True),
        ("PUT", f"/api/rows/{ROW}/need-by", "admin", True),
        ("PUT", f"/api/rows/{ROW}/need-by", "quinn", False),
        ("PUT", f"/api/rows/{ROW}/need-by", "alex", False),
        ("PUT", f"/api/rows/{ROW}/status", "quinn", True),
        ("PUT", f"/api/rows/{ROW}/status", "alex", True),
        ("PUT", f"/api/rows/{ROW}/status", "admin", True),
        ("PUT", f"/api/rows/{ROW}/status", "pat", False),
        ("PUT", f"/api/rows/{ROW}/status", "sam", False),
        ("POST", f"/api/rows/{ROW}/comments", "sam", False),
        ("POST", f"/api/rows/{ROW}/comments", "pat", True),
        ("POST", f"/api/rows/{ROW}/comments", "quinn", True),
    ],
)
def test_f09_fr05_the_role_matrix(client: TestClient, method: str, path: str, user: str, ok: bool) -> None:
    bodies = {"need-by": PULLED, "status": {"rag": "red", "reason": "waiting", "team": "QC Lab"},
              "comments": {"body": "hello"}}  # fmt: skip
    response = client.request(
        method, path, json=bodies[path.rsplit("/", 1)[1]], headers={"X-Demo-User": user}
    )
    assert (response.status_code < 300) is ok, response.text
    assert ok or response.status_code == 403


def test_f09_fr04_manual_status_is_versioned_and_display_only(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    quinn = {"X-Demo-User": "quinn"}
    body = {"rag": "red", "reason": "Instrument down", "team": "QC Lab"}
    response = client.put(f"/api/rows/{ROW}/status", json=body, headers=quinn).json()
    assert response["manual_status"] == {"rag": "red", "team": "QC Lab"}
    assert response["plan"]["rag"] == "green" and response["late"] is False  # OQ-057
    overview = client.get("/api/overview").json()
    assert [r["batch_no"] for r in overview["rows"]] == ["B2077", "B9"]  # order unchanged
    assert next(e for e in overview["flow_strip"] if e["stage_key"] == "sampling")["breached"] is False
    assert {a["kind"]: a["count"] for a in overview["alerts"]} == {
        "air_gap": 0,
        "late": 0,
        "on_hold": 0,
        "rejected": 0,
    }
    assert versions(app_factory, "manual_status") == [
        (1, {"rag": "red", "team": "QC Lab"}, None, True, "quinn")
    ]
    assert query(app_factory, "SELECT note FROM override_value WHERE field = 'manual_status'") == [
        ("Instrument down",)
    ]
    assert client.put(f"/api/rows/{ROW}/status", json=body, headers=quinn).status_code == 200
    assert len(versions(app_factory, "manual_status")) == 1  # unchanged: no new version
    assert client.put(f"/api/rows/{ROW}/status", json={"rag": "red"}, headers=quinn).status_code == 422
    cleared = client.put(f"/api/rows/{ROW}/status", json={"rag": None}, headers=quinn).json()
    assert cleared["manual_status"] is None
    assert [a[0] for a in query(app_factory, "SELECT action FROM audit_event ORDER BY id")] == [
        "status_set",
        "status_cleared",
    ]


def test_f09_fr04_comments_are_stored_counted_and_audited(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    created = client.post(f"/api/rows/{ROW}/comments", json={"body": "  Called the supplier  "})
    assert created.status_code == 201 and created.json()["body"] == "Called the supplier"
    assert row(client)["comment_count"] == 1
    assert query(app_factory, "SELECT action, actor_user_key FROM audit_event") == [("comment_added", "pat")]
    assert client.post(f"/api/rows/{ROW}/comments", json={"body": "   "}).status_code == 422
    assert client.post("/api/rows/NOPE%7CX%7C1/comments", json={"body": "x"}).status_code == 404


def test_f09_fr04_a_failed_write_leaves_no_version_behind(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    client.put(URL, json=PULLED | {"reason_code": "NOT_A_CODE"})
    assert versions(app_factory) == [] and query(app_factory, "SELECT 1 FROM audit_event") == []
