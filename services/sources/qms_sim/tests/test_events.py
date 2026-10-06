"""T6: QMS event functions and API [F04-FR-05, F04-AC-03]. Needs Postgres (integration)."""

from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from qms_sim import events, schemas
from qms_sim.app import app
from qms_sim.db import get_session
from qms_sim.models import ChangeControl, Deviation
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


# --- F19: quality data -------------------------------------------------------------------------


def test_f19_fr03_a_deviation_carries_causal_factor_and_investigation_summary(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        opened = events.deviation_opened(
            session,
            schemas.DeviationOpenedIn(
                **OPENED, causal_factor="Transport", investigation_summary="Probe was out of calibration."
            ),
        )
        plain = events.deviation_opened(session, schemas.DeviationOpenedIn(title="x", severity="moderate"))
        closed = events.deviation_closed(
            session,
            schemas.DeviationClosedIn(
                deviation_no="DEV-000002", investigation_summary="Handled with the carrier."
            ),
        )
    assert opened["deviation"]["causal_factor"] == "Transport"
    assert opened["deviation"]["investigation_summary"] == "Probe was out of calibration."
    assert (plain["deviation"]["causal_factor"], plain["deviation"]["investigation_summary"]) == (None, None)
    assert closed["deviation"]["investigation_summary"] == "Handled with the carrier."


def test_f19_fr03_the_severity_vocabulary_is_minor_moderate_major() -> None:
    for value in ("minor", "moderate", "major"):
        schemas.DeviationOpenedIn(title="x", severity=value)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        schemas.DeviationOpenedIn(title="x", severity="critical")  # type: ignore[arg-type]


CHANGE = {
    "title": "Update the storage specification",
    "current_state": "Store at 2-8 C",
    "proposed_state": "Store at 2-25 C",
    "links": [LINK],
}


def test_f19_fr03_change_control_opened_numbers_links_and_stamps(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        first = events.change_control_opened(session, schemas.ChangeControlOpenedIn(**CHANGE))
        second = events.change_control_opened(
            session, schemas.ChangeControlOpenedIn(**{**CHANGE, "links": []}, status="approved")
        )
        session.commit()
    assert first["change_control"]["cc_no"] == "CC-000001"
    assert second["change_control"]["cc_no"] == "CC-000002"
    assert (first["change_control"]["status"], first["change_control"]["opened_on"]) == (
        "open",
        date(2026, 10, 12),
    )
    assert first["change_control"]["updated_at"] == datetime(2026, 10, 12, 7, 0, tzinfo=UTC)
    assert [(c["material_no"], c["batch_no"]) for c in first["links"]] == [("RM10001", "B1001")]
    assert second["change_control"]["status"] == "approved" and second["links"] == []


def test_f19_fr03_change_control_status_moves_forward_and_validates(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        events.change_control_opened(session, schemas.ChangeControlOpenedIn(**CHANGE))
        done = events.change_control_status(
            session,
            schemas.ChangeControlStatusIn(
                cc_no="CC-000001", status="closed", effective_on=date(2026, 10, 30)
            ),
        )
        assert (done["change_control"]["status"], done["change_control"]["effective_on"]) == (
            "closed",
            date(2026, 10, 30),
        )
        with pytest.raises(Invalid, match="unknown change control"):
            events.change_control_status(
                session, schemas.ChangeControlStatusIn(cc_no="CC-999999", status="closed")
            )
        with pytest.raises(Invalid, match="twice"):
            events.change_control_opened(
                session, schemas.ChangeControlOpenedIn(**{**CHANGE, "links": [LINK, LINK]})
            )
        with pytest.raises(Conflict):
            events.change_control_opened(session, schemas.ChangeControlOpenedIn(**CHANGE, cc_no="CC-000001"))
        assert session.get(ChangeControl, "CC-000001") is not None


def test_f19_fr03_change_controls_can_be_read_over_http(client: TestClient) -> None:
    client.post("/events/change-control-opened", json=CHANGE, headers=TOKEN)
    client.post(
        "/events/change-control-opened",
        json={**CHANGE, "links": [{"material_no": "RM10002", "batch_no": "B2002"}]},
        headers=TOKEN,
    )
    assert len(client.get("/change-controls").json()) == 2
    found = client.get("/change-controls", params={"batch_no": "B1001"}).json()
    assert [c["cc_no"] for c in found] == ["CC-000001"] and found[0]["links"][0]["batch_no"] == "B1001"
    assert client.get("/change-controls/CC-000002").json()["proposed_state"] == "Store at 2-25 C"
    assert client.get("/change-controls/CC-999999").status_code == 404
