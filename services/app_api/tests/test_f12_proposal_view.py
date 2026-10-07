"""F12-FR-13: the Insights rows and the row detail carry the newest agent proposal (read-only view)."""

from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from r2r_core.profile import SiteProfile, load_profile
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import NOW, batch, load_mirror

pytestmark = pytest.mark.integration


def _air_gap(batch_no: str, material: str, hours: int) -> dict[str, Any]:
    return batch(
        batch_no,
        material,
        stage_key="qa_release",
        stage_rule_id="R-QAR",
        lims_status="approved",
        lims_approved_at=NOW - timedelta(hours=hours),
    )


@pytest.fixture
def mirror(app_factory: sessionmaker[Session]) -> Iterator[None]:
    profile: SiteProfile = load_profile("site_a")
    load_mirror(app_factory, profile, [_air_gap("B5003", "RM10035", 30), _air_gap("B5001", "RM10036", 100)])
    with app_factory() as db:
        db.execute(text("DELETE FROM action_log"))
        db.execute(text("DELETE FROM proposal"))
        db.commit()
    yield


def _propose(app_factory: sessionmaker[Session], row_key: str, status: str, priority: str = "high") -> int:
    with app_factory() as db:
        proposal_id: int = db.execute(
            text(
                "INSERT INTO proposal (agent_key, row_key, kind, payload_json, status, required_role, created_at) "
                "VALUES ('air_gap', :k, 'airgap_ticket', CAST(:p AS jsonb), :s, 'qa_release', now()) RETURNING id"
            ),
            {"k": row_key, "s": status, "p": f'{{"priority": "{priority}"}}'},
        ).scalar_one()
        db.commit()
    return proposal_id


@pytest.mark.usefixtures("mirror")
def test_f12_fr13_insights_rows_have_no_proposal_until_the_agent_runs(client: TestClient) -> None:
    rows = client.get("/api/overview/insights").json()["rows"]
    assert [r["batch_no"] for r in rows] == ["B5001", "B5003"]
    assert [r["proposal"] for r in rows] == [None, None]


@pytest.mark.usefixtures("mirror")
def test_f12_fr13_insights_show_the_newest_proposal_of_each_row(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    _propose(app_factory, "RM10035|B5003|9001", "rejected_by_validator", "normal")
    newest = _propose(app_factory, "RM10035|B5003|9001", "pending_approval", "high")
    rows = {r["batch_no"]: r for r in client.get("/api/overview/insights").json()["rows"]}
    assert rows["B5003"]["proposal"] == {"id": newest, "status": "pending_approval", "priority": "high"}
    assert rows["B5001"]["proposal"] is None


@pytest.mark.usefixtures("mirror")
def test_f12_fr13_row_detail_carries_the_proposal_for_the_drawer_line(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    assert client.get("/api/rows/RM10035|B5003|9001").json()["proposal"] is None
    proposal_id = _propose(app_factory, "RM10035|B5003|9001", "executed")
    body = client.get("/api/rows/RM10035|B5003|9001").json()
    assert body["proposal"] == {"id": proposal_id, "status": "executed", "priority": "high"}
    assert client.get("/api/rows/RM10036|B5001|9001").json()["proposal"] is None
