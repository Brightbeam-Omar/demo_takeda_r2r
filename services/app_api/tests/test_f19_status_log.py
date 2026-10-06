"""F19 T5 [TDD]: the status log replaces manual status and comments (F19-FR-05, F19-AC-04, OQ-111)."""

from collections.abc import Callable
from typing import Any

import pytest
from app_api.db import migrate
from fastapi.testclient import TestClient
from r2r_core.db import make_engine
from r2r_core.profile import load_profile
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import batch, load_mirror

pytestmark = pytest.mark.integration

ROW = "RM10031|B2077|9001"
URL = f"/api/rows/{ROW}/status-log"
QUINN = {"X-Demo-User": "quinn"}
AT_RISK = {
    "status": "at_risk",
    "team": "QC Lab",
    "reason_code": "resource_constraint",
    "comment": "Waiting for a free analyst",
}


@pytest.fixture(autouse=True)
def mirror(app_factory: sessionmaker[Session]) -> None:
    load_mirror(app_factory, load_profile("site_a"), [batch(), batch("B9", lot="9002")])


def query(factory: sessionmaker[Session], sql: str) -> list[Any]:
    with factory() as session:
        return [tuple(r) for r in session.execute(text(sql))]


def overview_row(client: TestClient, row_key: str = ROW) -> dict[str, Any]:
    return next(r for r in client.get("/api/overview").json()["rows"] if r["row_key"] == row_key)  # type: ignore[no-any-return]


def test_f19_ac04_quinn_adds_a_status_and_it_tops_latest_with_the_comment_beneath_the_status_cell(
    client: TestClient,
) -> None:
    assert overview_row(client)["latest_status"] is None and overview_row(client)["status_log_count"] == 0
    created = client.post(URL, json=AT_RISK, headers=QUINN)
    assert created.status_code == 201, created.text
    entry = created.json()
    assert (entry["status"], entry["team"], entry["reason_code"], entry["author_user_key"]) == (
        "at_risk",
        "QC Lab",
        "resource_constraint",
        "quinn",
    )
    latest = overview_row(client)["latest_status"]
    assert latest["status"] == "at_risk" and latest["label"] == "At Risk" and latest["colour"] == "amber"
    assert (latest["comment"], latest["author_user_key"], latest["team"]) == (
        "Waiting for a free analyst",
        "quinn",
        "QC Lab",
    )
    assert latest["reason_label"] == "Resource constraint" and latest["at"]


def test_f19_ac04_the_history_counts_two_after_a_second_entry_newest_first(client: TestClient) -> None:
    client.post(URL, json=AT_RISK, headers=QUINN)
    second = {"status": "escalated", "team": "QA", "comment": "Escalated to the site lead"}
    assert client.post(URL, json=second, headers={"X-Demo-User": "alex"}).status_code == 201
    log = client.get(URL).json()
    assert log["count"] == 2
    assert [e["status"] for e in log["entries"]] == ["escalated", "at_risk"]  # newest first
    assert log["latest"]["status"] == "escalated"
    assert overview_row(client)["status_log_count"] == 2
    assert client.get(f"/api/rows/{ROW}").json()["status_log"][0]["comment"] == "Escalated to the site lead"


@pytest.mark.parametrize(
    ("user", "allowed"), [("pat", True), ("quinn", True), ("alex", True), ("admin", True), ("sam", False)]
)
def test_f19_ac04_everyone_except_the_viewer_may_add_an_entry(
    client: TestClient, user: str, allowed: bool
) -> None:
    response = client.post(URL, json=AT_RISK, headers={"X-Demo-User": user})
    assert response.status_code == (201 if allowed else 403)


def test_f19_fr05_the_viewer_is_refused_and_the_refusal_is_audited(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    client.post(URL, json=AT_RISK, headers={"X-Demo-User": "sam"})
    assert query(app_factory, "SELECT count(*) FROM status_log") == [(0,)]
    assert query(app_factory, "SELECT action, actor_user_key FROM audit_event") == [("forbidden", "sam")]


@pytest.mark.parametrize(
    "body",
    [
        AT_RISK | {"comment": "   "},
        AT_RISK | {"comment": ""},
        AT_RISK | {"status": "fine"},
        AT_RISK | {"status": None},
        AT_RISK | {"reason_code": "mood"},
        AT_RISK | {"team": "Nobody"},
    ],
)
def test_f19_fr05_a_blank_comment_or_unknown_status_reason_or_team_is_422(
    client: TestClient, body: dict[str, Any]
) -> None:
    assert client.post(URL, json=body, headers=QUINN).status_code == 422
    assert client.get(URL).json()["count"] == 0


def test_f19_fr05_reason_and_team_are_optional_and_the_comment_is_trimmed(client: TestClient) -> None:
    created = client.post(URL, json={"status": "on_track", "comment": "  All good  "}, headers=QUINN).json()
    assert (created["team"], created["reason_code"], created["comment"]) == (None, None, "All good")


def test_f19_fr05_an_unknown_row_is_404_and_a_released_row_can_still_be_logged(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    assert client.post("/api/rows/nope/status-log", json=AT_RISK, headers=QUINN).status_code == 404
    assert client.get("/api/rows/nope/status-log").status_code == 404
    load_mirror(
        app_factory,
        load_profile("site_a"),
        [batch("B9", lot="9002", stage_key="released", ud_effective=True)],
    )
    done = {"status": "resolved", "comment": "Released after the review"}
    assert client.post("/api/rows/RM10031|B9|9002/status-log", json=done, headers=QUINN).status_code == 201


def test_f19_fr05_logging_writes_an_audit_event_status_logged(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    client.post(URL, json=AT_RISK, headers=QUINN)
    [(action, actor, row_key, details)] = query(
        app_factory, "SELECT action, actor_user_key, row_key, details_json FROM audit_event"
    )
    assert (action, actor, row_key) == ("status_logged", "quinn", ROW)
    assert details["status"] == "at_risk" and details["team"] == "QC Lab" and details["comment_id"] == 1


def test_f19_fr05_the_reference_lists_the_status_options_and_reasons(client: TestClient) -> None:
    reference = client.get("/api/reference").json()
    assert [o["key"] for o in reference["status_options"]] == [
        "on_track", "at_risk", "blocked", "escalated", "resolved",
    ]  # fmt: skip
    assert reference["status_options"][1] == {"key": "at_risk", "label": "At Risk", "colour": "amber"}
    assert [r["label"] for r in reference["status_reasons"]][:3] == [
        "Process delay", "Supplier issue", "Resource constraint",
    ]  # fmt: skip


# --- the one-off migration --------------------------------------------------------------------------


def test_f19_fr05_the_migration_copies_manual_status_versions_and_comments_in_time_order(
    make_test_database: Callable[[str], str],
) -> None:
    dsn = make_test_database("app_status_migration")
    migrate(dsn, "0008")
    engine = make_engine(dsn)
    with engine.begin() as c:
        c.execute(
            text("INSERT INTO demo_clock (id, now_utc, frozen) VALUES (1, '2026-10-12T07:00:00Z', false)")
        )
        insert = (
            "INSERT INTO override_value (row_key, field, value_json, reason_code, note, version, author_user_key, "
            "created_at, is_current) VALUES (:k, 'manual_status', CAST(:v AS jsonb), NULL, :n, :ver, :a, :t, :cur)"
        )
        c.execute(
            text(insert),
            {
                "k": "R1",
                "v": '{"rag": "green", "team": "QC Lab"}',
                "n": "Looks fine",
                "ver": 1,
                "a": "quinn",
                "t": "2026-10-05T09:00:00Z",
                "cur": False,
            },
        )
        c.execute(
            text(insert),
            {
                "k": "R1",
                "v": '{"rag": "amber", "team": "QC Lab"}',
                "n": "Slipping",
                "ver": 2,
                "a": "alex",
                "t": "2026-10-07T09:00:00Z",
                "cur": False,
            },
        )
        c.execute(
            text(insert),
            {
                "k": "R1",
                "v": "null",
                "n": None,
                "ver": 3,
                "a": "quinn",
                "t": "2026-10-09T09:00:00Z",
                "cur": False,
            },
        )
        c.execute(
            text(insert),
            {
                "k": "R1",
                "v": '{"rag": "red", "team": "QA"}',
                "n": "Stuck",
                "ver": 4,
                "a": "alex",
                "t": "2026-10-10T09:00:00Z",
                "cur": True,
            },
        )
        c.execute(
            text(
                "INSERT INTO comment (row_key, body, author_user_key, created_at) VALUES ('R1', 'Called them', 'pat', '2026-10-06T09:00:00Z')"
            )
        )
    migrate(dsn)
    with engine.connect() as c:
        rows = [
            tuple(r)
            for r in c.execute(
                text("SELECT status, team, reason_code, comment, author_user_key FROM status_log ORDER BY id")
            )
        ]
        audit = [
            tuple(r)
            for r in c.execute(text("SELECT action, actor_user_key, row_key, details_json FROM audit_event"))
        ]
        untouched = c.execute(text("SELECT count(*) FROM override_value")).scalar()
    engine.dispose()
    assert rows == [
        ("on_track", "QC Lab", None, "Looks fine", "quinn"),
        (None, None, None, "Called them", "pat"),
        ("at_risk", "QC Lab", None, "Slipping", "alex"),
        (None, None, None, "Status cleared", "quinn"),
        ("blocked", "QA", None, "Stuck", "alex"),
    ]
    assert audit == [("status_log_migrated", "system", None, {"statuses": 4, "comments": 1})]
    assert untouched == 4  # nothing was updated or deleted


def test_f19_fr05_migrating_an_empty_database_logs_nothing(make_test_database: Callable[[str], str]) -> None:
    dsn = make_test_database("app_status_migration_empty")
    migrate(dsn)
    engine = make_engine(dsn)
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM status_log")).scalar() == 0
        assert (
            c.execute(text("SELECT count(*) FROM audit_event WHERE action = 'status_log_migrated'")).scalar()
            == 0
        )
    engine.dispose()
