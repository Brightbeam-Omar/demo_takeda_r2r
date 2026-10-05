"""F15 T7: the feedback endpoints (F15-FR-06, F15-AC-04, OQ-083)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration

SAM = {"X-Demo-User": "sam"}
ADMIN = {"X-Demo-User": "admin"}


def test_f15_ac04_feedback_posted_by_sam_is_listed_for_admin(client: TestClient) -> None:
    posted = client.post(
        "/api/feedback", json={"page": "/overview", "message": "Love the filters"}, headers=SAM
    )
    assert posted.status_code == 201
    [entry] = client.get("/api/feedback", headers=ADMIN).json()
    assert (entry["user_key"], entry["page"], entry["message"]) == ("sam", "/overview", "Love the filters")
    assert entry["at"].startswith("2026-10-12T07:00")  # the demo clock, not wall time


def test_f15_oq083_any_persona_may_post_but_only_admin_may_list(client: TestClient) -> None:
    for user in ("pat", "quinn", "alex", "sam", "admin"):
        assert (
            client.post(
                "/api/feedback", json={"page": "/", "message": "hi"}, headers={"X-Demo-User": user}
            ).status_code
            == 201
        )
    assert client.get("/api/feedback", headers=SAM).status_code == 403
    assert client.get("/api/feedback").status_code == 403  # pat is the default persona


def test_f15_oq083_the_list_is_newest_first(client: TestClient) -> None:
    for message in ("first", "second", "third"):
        client.post("/api/feedback", json={"page": "/audit", "message": message})
    assert [e["message"] for e in client.get("/api/feedback", headers=ADMIN).json()] == [
        "third",
        "second",
        "first",
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"page": "/", "message": ""},
        {"page": "/", "message": "   "},
        {"page": "/", "message": "x" * 2001},
        {"page": "/" * 201, "message": "ok"},
        {"message": "no page"},
    ],
)
def test_f15_oq083_invalid_feedback_is_422(client: TestClient, payload: dict[str, str]) -> None:
    assert client.post("/api/feedback", json=payload).status_code == 422


def test_f15_oq083_limits_are_inclusive_and_feedback_is_not_audited(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    assert client.post("/api/feedback", json={"page": "/" * 200, "message": "x" * 2000}).status_code == 201
    with app_factory() as session:
        assert session.execute(text("SELECT count(*) FROM audit_event")).scalar_one() == 0
