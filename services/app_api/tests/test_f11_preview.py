"""F11 T1: need-by preview and the audit date range (F11-FR-02, F11-FR-06, OQ-067, OQ-068)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from r2r_core.profile import load_profile
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import batch, load_mirror

pytestmark = pytest.mark.integration

ROW = "RM10031|B2077|9001"
PREVIEW = f"/api/rows/{ROW}/need-by/preview"
PULLED = {"adjusted_date": "2026-11-26", "reason_code": "CAMPAIGN_PULLED_FORWARD"}


@pytest.fixture(autouse=True)
def mirror(app_factory: sessionmaker[Session]) -> None:
    load_mirror(
        app_factory, load_profile("site_a"), [batch(), batch("B9", stage_key="released", ud_effective=True)]
    )


def count(factory: sessionmaker[Session], table: str) -> int:
    with factory() as session:
        return int(session.execute(text(f"SELECT count(*) FROM {table}")).scalar() or 0)


def test_f11_fr02_the_preview_shows_the_compressed_plan_and_writes_nothing(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    response = client.post(PREVIEW, json=PULLED)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["current"]["expected_completion"] == "2026-10-15" and body["current"]["rag"] == "green"
    plan = body["preview"]
    assert plan["compressed"] is True
    assert plan["effective_slas"] == {"sampling": 6, "qc_testing": 37, "qa_release": 6}
    assert (plan["expected_completion"], plan["rag"]) == ("2026-10-14", "amber")
    assert body["operative_need_by"] == "2026-11-26"
    assert count(app_factory, "override_value") == 0 and count(app_factory, "audit_event") == 0


def test_f11_fr02_the_preview_matches_what_the_put_then_returns(client: TestClient) -> None:
    previewed = client.post(PREVIEW, json=PULLED).json()["preview"]
    saved = client.put(PREVIEW.removesuffix("/preview"), json=PULLED).json()["plan"]
    assert previewed == saved


def test_f11_oq067_any_identified_role_may_preview_and_no_reason_is_needed(client: TestClient) -> None:
    sam = client.post(PREVIEW, json={"adjusted_date": "2026-11-26"}, headers={"X-Demo-User": "sam"})
    assert sam.status_code == 200 and sam.json()["preview"]["compressed"] is True
    assert client.post(PREVIEW, json=PULLED, headers={"X-Demo-User": "nobody"}).status_code == 401


def test_f11_oq067_clearing_the_date_previews_the_system_plan(client: TestClient) -> None:
    client.put(PREVIEW.removesuffix("/preview"), json=PULLED)
    body = client.post(PREVIEW, json={"adjusted_date": None}).json()
    assert body["operative_need_by"] == body["system_need_by_locked"]
    assert body["preview"]["expected_completion"] == "2026-10-15"
    assert body["current"]["expected_completion"] == "2026-10-14"


def test_f11_oq067_errors_follow_the_put(client: TestClient) -> None:
    assert client.post("/api/rows/NOPE|B1|1/need-by/preview", json=PULLED).status_code == 404
    released = client.post("/api/rows/RM10031%7CB9%7C9001/need-by/preview", json=PULLED)
    assert released.status_code == 409
    assert client.post(PREVIEW, json=PULLED | {"reason_code": "NOT_A_CODE"}).status_code == 422


def test_f11_oq068_the_audit_log_filters_by_demo_date_range(client: TestClient) -> None:
    client.put(PREVIEW.removesuffix("/preview"), json=PULLED)  # audited at the demo clock: 12 Oct 2026
    everything: dict[str, Any] = client.get("/api/audit").json()
    assert everything["total"] == 1
    inside = client.get("/api/audit", params={"from": "2026-10-12", "to": "2026-10-12"}).json()
    assert inside["total"] == 1 and inside["items"][0]["details"]["new"] == "2026-11-26"
    assert client.get("/api/audit", params={"from": "2026-10-13"}).json()["total"] == 0
    assert client.get("/api/audit", params={"to": "2026-10-11"}).json()["total"] == 0
    assert client.get("/api/audit", params={"from": "2026-10-13", "to": "2026-10-12"}).status_code == 422
