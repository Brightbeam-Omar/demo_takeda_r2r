"""T6: QMS event functions and API [F04-FR-05, F04-AC-03]. Needs Postgres (integration)."""

from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from qms_sim import events, schemas
from qms_sim.app import app
from qms_sim.db import get_session
from qms_sim.models import Deviation
from r2r_core.errors import Conflict, Invalid
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration

TOKEN = {"X-Scenario-Token": "s3cret"}
LINK = {"material_no": "RM10001", "batch_no": "B1001"}
OPENED = {"title": "Temperature excursion", "severity": "major", "links": [LINK]}


def test_f04_fr05_deviation_opened_numbers_links_and_stamps(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        result = events.deviation_opened(session, schemas.DeviationOpenedIn(**OPENED))
        second = events.deviation_opened(
            session, schemas.DeviationOpenedIn(title="Late delivery", severity="minor")
        )
        session.commit()
    assert result["deviation"]["deviation_no"] == "DEV-000001"
    assert second["deviation"]["deviation_no"] == "DEV-000002"
    assert result["deviation"]["status"] == "open"
    assert result["deviation"]["opened_on"] == date(2026, 10, 12)
    assert result["deviation"]["updated_at"] == datetime(2026, 10, 12, 7, 0, tzinfo=UTC)
    assert [(link["material_no"], link["batch_no"]) for link in result["links"]] == [("RM10001", "B1001")]
    assert result["links"][0]["updated_at"] == datetime(2026, 10, 12, 7, 0, tzinfo=UTC)
    assert second["links"] == []


def test_f04_fr05_closing_sets_the_status_and_date_once(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        events.deviation_opened(session, schemas.DeviationOpenedIn(**OPENED))
        closed = events.deviation_closed(
            session, schemas.DeviationClosedIn(deviation_no="DEV-000001", closed_on=date(2026, 10, 20))
        )
        assert (closed["deviation"]["status"], closed["deviation"]["closed_on"]) == (
            "closed",
            date(2026, 10, 20),
        )
        with pytest.raises(Invalid, match="already closed"):
            events.deviation_closed(session, schemas.DeviationClosedIn(deviation_no="DEV-000001"))
        with pytest.raises(Invalid, match="unknown deviation"):
            events.deviation_closed(session, schemas.DeviationClosedIn(deviation_no="DEV-999999"))


def test_f04_fr10_duplicate_numbers_conflict_and_duplicate_links_are_invalid(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        events.deviation_opened(session, schemas.DeviationOpenedIn(**OPENED, deviation_no="DEV-000050"))
        with pytest.raises(Conflict):
            events.deviation_opened(session, schemas.DeviationOpenedIn(**OPENED, deviation_no="DEV-000050"))
        with pytest.raises(Invalid, match="twice"):
            events.deviation_opened(
                session, schemas.DeviationOpenedIn(title="x", severity="minor", links=[LINK, LINK])
            )
        assert session.get(Deviation, "DEV-000050") is not None


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


def test_f04_ac03_writes_need_the_token(client: TestClient) -> None:
    assert client.post("/events/deviation-opened", json=OPENED).status_code == 401
    assert (
        client.post("/events/deviation-closed", json={}, headers={"X-Scenario-Token": "x"}).status_code == 401
    )


def test_f04_fr05_reads_filter_by_batch_and_include_links(client: TestClient) -> None:
    client.post("/events/deviation-opened", json=OPENED, headers=TOKEN)
    other = {
        "title": "Other",
        "severity": "minor",
        "links": [{"material_no": "RM10002", "batch_no": "B2002"}],
    }
    client.post("/events/deviation-opened", json=other, headers=TOKEN)
    assert len(client.get("/deviations").json()) == 2
    found = client.get("/deviations", params={"batch_no": "B1001"}).json()
    assert [d["deviation_no"] for d in found] == ["DEV-000001"]
    assert found[0]["links"][0]["batch_no"] == "B1001"
    assert client.get("/deviations/DEV-000002").json()["title"] == "Other"
    assert client.get("/deviations/DEV-999999").status_code == 404
    assert (
        client.post(
            "/events/deviation-closed", json={"deviation_no": "DEV-999999"}, headers=TOKEN
        ).status_code
        == 422
    )
    assert client.get("/health").json() == {"status": "ok", "service": "qms-sim"}
    assert client.get("/docs").status_code == 200
