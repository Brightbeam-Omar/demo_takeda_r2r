"""T5: QMS API without a database: docs, health and the token guard [F04-AC-03]."""

import pytest
from fastapi.testclient import TestClient
from qms_sim.app import app

WRITE_PATHS = sorted(path for path, operations in app.openapi()["paths"].items() if "post" in operations)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SCENARIO_TOKEN", "s3cret")
    return TestClient(app)


def test_f04_fr05_the_expected_write_endpoints_exist() -> None:
    assert WRITE_PATHS == [
        "/events/change-control-opened",
        "/events/change-control-status",
        "/events/deviation-closed",
        "/events/deviation-opened",
    ]


@pytest.mark.parametrize("path", WRITE_PATHS)
def test_f04_ac03_writes_without_or_with_a_wrong_token_are_401(client: TestClient, path: str) -> None:
    assert client.post(path, json={}).status_code == 401
    assert client.post(path, json={}, headers={"X-Scenario-Token": "wrong"}).status_code == 401


def test_f04_fr08_health_and_docs_are_open(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok", "service": "qms-sim"}
    assert client.get("/docs").status_code == 200
