"""F16 T2 [TDD]: bookmarks and filter presets (F16-FR-04, FR-05, OQ-089, OQ-091)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from r2r_core.profile import load_profile
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import batch, load_mirror

pytestmark = pytest.mark.integration

ROW = "RM10031|B2077|9001"
OTHER = "RM10032|B2078|9002"
QUERY = "type=small_molecule&class=drug_substance&period=this_week"


@pytest.fixture(autouse=True)
def mirror(app_factory: sessionmaker[Session]) -> None:
    load_mirror(app_factory, load_profile("site_a"), [batch(), batch("B2078", "RM10032", lot="9002")])


def as_user(client: TestClient, user: str) -> dict[str, str]:
    return {"X-Demo-User": user}


def bookmarks(client: TestClient, user: str = "pat") -> list[str]:
    response = client.get("/api/bookmarks", headers=as_user(client, user))
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


# --- bookmarks (F16-FR-04, OQ-091) -----------------------------------------------------------------------


def test_f16_fr04_a_bookmark_can_be_added_listed_and_removed(client: TestClient) -> None:
    assert bookmarks(client) == []
    assert client.post(f"/api/bookmarks/{ROW}").status_code == 201
    assert bookmarks(client) == [ROW]
    assert client.delete(f"/api/bookmarks/{ROW}").status_code == 204
    assert bookmarks(client) == []


def test_f16_fr04_adding_and_removing_are_idempotent(client: TestClient) -> None:
    assert client.post(f"/api/bookmarks/{ROW}").status_code == 201
    assert client.post(f"/api/bookmarks/{ROW}").status_code == 201
    assert bookmarks(client) == [ROW]
    assert client.delete(f"/api/bookmarks/{ROW}").status_code == 204
    assert client.delete(f"/api/bookmarks/{ROW}").status_code == 204


def test_f16_fr04_bookmarks_are_personal(client: TestClient) -> None:
    client.post(f"/api/bookmarks/{ROW}", headers=as_user(client, "pat"))
    assert bookmarks(client, "pat") == [ROW]
    assert bookmarks(client, "quinn") == []


def test_f16_oq091_any_persona_including_viewer_may_bookmark(client: TestClient) -> None:
    for user in ("pat", "quinn", "alex", "sam", "admin"):
        assert client.post(f"/api/bookmarks/{ROW}", headers=as_user(client, user)).status_code == 201
        assert bookmarks(client, user) == [ROW]


def test_f16_fr04_an_unknown_row_is_404(client: TestClient) -> None:
    assert client.post("/api/bookmarks/NOPE|X|1").status_code == 404


def test_f16_oq091_a_bookmark_is_not_audited(client: TestClient, app_factory: sessionmaker[Session]) -> None:
    client.post(f"/api/bookmarks/{ROW}")
    client.delete(f"/api/bookmarks/{ROW}")
    with app_factory() as session:
        assert session.execute(text("SELECT count(*) FROM audit_event")).scalar_one() == 0


def test_f16_fr04_the_bookmark_is_committed_before_the_response(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    client.post(f"/api/bookmarks/{ROW}")
    with app_factory() as session:
        rows = session.execute(text("SELECT user_key, row_key FROM bookmark")).all()
    assert [tuple(r) for r in rows] == [("pat", ROW)]


# --- presets (F16-FR-05, OQ-089) -------------------------------------------------------------------------


def save(client: TestClient, name: str = "My small molecules", query: str = QUERY, user: str = "pat") -> Any:
    return client.post("/api/presets", json={"name": name, "query": query}, headers=as_user(client, user))


def test_f16_fr05_no_presets_to_start_with(client: TestClient) -> None:
    assert client.get("/api/presets").json() == []


def test_f16_fr05_a_preset_is_saved_with_its_query_and_period_literally(client: TestClient) -> None:
    response = save(client)
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["name"], body["query"]) == ("My small molecules", QUERY)
    assert "period=this_week" in body["query"]  # stays relative (OQ-089)
    assert client.get("/api/presets").json() == [body]


def test_f16_oq089_a_duplicate_name_is_409(client: TestClient) -> None:
    assert save(client).status_code == 201
    again = save(client, query="type=peptide")
    assert again.status_code == 409
    assert [p["query"] for p in client.get("/api/presets").json()] == [QUERY]


def test_f16_oq089_the_same_name_is_fine_for_another_user(client: TestClient) -> None:
    assert save(client, user="pat").status_code == 201
    assert save(client, user="quinn").status_code == 201


def test_f16_oq089_put_overwrites_the_query_and_keeps_the_name(client: TestClient) -> None:
    created = save(client).json()
    response = client.put(f"/api/presets/{created['id']}", json={"query": "type=peptide"})
    assert response.status_code == 200, response.text
    assert (response.json()["id"], response.json()["name"], response.json()["query"]) == (
        created["id"],
        "My small molecules",
        "type=peptide",
    )
    assert [p["query"] for p in client.get("/api/presets").json()] == ["type=peptide"]


def test_f16_fr05_presets_are_personal(client: TestClient) -> None:
    mine = save(client, user="pat").json()
    assert client.get("/api/presets", headers=as_user(client, "quinn")).json() == []
    other = as_user(client, "quinn")
    assert client.put(f"/api/presets/{mine['id']}", json={"query": "x=1"}, headers=other).status_code == 404
    assert client.delete(f"/api/presets/{mine['id']}", headers=other).status_code == 404
    assert len(client.get("/api/presets").json()) == 1


def test_f16_fr05_a_preset_can_be_deleted(client: TestClient) -> None:
    created = save(client).json()
    assert client.delete(f"/api/presets/{created['id']}").status_code == 204
    assert client.get("/api/presets").json() == []
    assert client.delete(f"/api/presets/{created['id']}").status_code == 404


def test_f16_fr05_the_name_and_query_are_validated(client: TestClient) -> None:
    assert save(client, name="").status_code == 422
    assert save(client, name="   ").status_code == 422
    assert save(client, name="x" * 61).status_code == 422
    assert save(client, query="q" * 2001).status_code == 422


def test_f16_fr05_viewer_may_save_presets_and_they_are_not_audited(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    assert save(client, user="sam").status_code == 201
    with app_factory() as session:
        assert session.execute(text("SELECT count(*) FROM audit_event")).scalar_one() == 0
