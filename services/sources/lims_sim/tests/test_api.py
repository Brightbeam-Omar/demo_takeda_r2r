"""T5: LIMS API against a real database [F04-FR-04, F04-AC-06]. Needs Postgres (integration)."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from lims_sim.app import app
from lims_sim.db import get_session
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration

TOKEN = {"X-Scenario-Token": "s3cret"}
LOT = {"inspection_lot_no": "10000001", "material_no": "RM10001", "batch_no": "B1001"}


@pytest.fixture
def client(factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("SCENARIO_TOKEN", "s3cret")

    def session_for_request() -> Iterator[Session]:
        with factory() as session:
            try:
                yield session
                session.commit()
            except BaseException:
                session.rollback()
                raise

    app.dependency_overrides[get_session] = session_for_request
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_f04_ac06_approved_over_http_sets_status_and_approved_at(client: TestClient) -> None:
    sample_id = client.post("/events/sample-collected", json=LOT, headers=TOKEN).json()["sample"]["sample_id"]
    response = client.post("/events/approved", json={"sample_id": sample_id}, headers=TOKEN)
    assert response.status_code == 200
    sample = response.json()["sample"]
    assert sample["status"] == "approved"
    assert datetime.fromisoformat(sample["approved_at"]) == datetime(2026, 10, 12, 7, 0, tzinfo=UTC)


def test_f04_fr04_reads_filter_by_batch_and_material(client: TestClient) -> None:
    client.post("/events/sample-collected", json=LOT, headers=TOKEN)
    other = {**LOT, "inspection_lot_no": "10000002", "batch_no": "B2002", "material_no": "RM10002"}
    client.post("/events/sample-collected", json=other, headers=TOKEN)
    assert len(client.get("/samples").json()) == 2
    assert [s["batch_no"] for s in client.get("/samples", params={"batch_no": "B1001"}).json()] == ["B1001"]
    assert [s["material_no"] for s in client.get("/samples", params={"material_no": "RM10002"}).json()] == [
        "RM10002"
    ]
    assert client.get("/samples/S-0000001").json()["inspection_lot_no"] == "10000001"
    assert client.get("/samples/S-0000001/results").json() == []


def test_f04_fr04_unknown_samples_are_404_and_bad_events_422_or_409(client: TestClient) -> None:
    assert client.get("/samples/S-9999999").status_code == 404
    assert client.get("/samples/S-9999999/results").status_code == 404
    assert client.post("/events/approved", json={"sample_id": "S-9999999"}, headers=TOKEN).status_code == 422
    client.post("/events/sample-collected", json={**LOT, "sample_id": "S-0000050"}, headers=TOKEN)
    again = {**LOT, "inspection_lot_no": "10000009", "sample_id": "S-0000050"}
    assert client.post("/events/sample-collected", json=again, headers=TOKEN).status_code == 409
