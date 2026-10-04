"""T7: clock service without a database: token guard, body validation, health [F04-AC-03, F04-FR-07]."""

import pytest
from fastapi.testclient import TestClient
from scenario.app import app

GUARDED = ["/clock/set", "/clock/advance"]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SCENARIO_TOKEN", "s3cret")
    return TestClient(app)  # no `with`: the startup seed (which needs a database) does not run


@pytest.mark.parametrize("path", GUARDED)
def test_f04_ac03_clock_posts_need_the_token(client: TestClient, path: str) -> None:
    assert client.post(path, json={}).status_code == 401
    assert client.post(path, json={}, headers={"X-Scenario-Token": "wrong"}).status_code == 401


@pytest.mark.parametrize(
    "body",
    [{}, {"hours": 2, "days": 1}, {"days": 0}, {"hours": -3}, {"days": 1.5}, {"minutes": 5}],
    ids=["neither", "both", "zero", "negative", "fraction", "unknown-field"],
)
def test_f04_fr07_advance_takes_exactly_one_positive_integer(
    client: TestClient, body: dict[str, object]
) -> None:
    response = client.post("/clock/advance", json=body, headers={"X-Scenario-Token": "s3cret"})
    assert response.status_code == 422


@pytest.mark.parametrize("iso", ["2026-10-12T08:00:00", "yesterday", 5])
def test_f04_fr07_set_needs_a_timezone_aware_iso_datetime(client: TestClient, iso: object) -> None:
    response = client.post("/clock/set", json={"iso": iso}, headers={"X-Scenario-Token": "s3cret"})
    assert response.status_code == 422


def test_f04_fr08_health_and_docs_are_open(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok", "service": "scenario"}
    assert client.get("/docs").status_code == 200
