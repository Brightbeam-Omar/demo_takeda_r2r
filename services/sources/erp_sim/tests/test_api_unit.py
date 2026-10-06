"""T4: ERP API without a database: docs, health and the token guard on every write [F04-AC-03, F04-FR-06/08]."""

import pytest
from erp_sim.app import app
from fastapi.testclient import TestClient

WRITE_PATHS = sorted(path for path, operations in app.openapi()["paths"].items() if "post" in operations)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SCENARIO_TOKEN", "s3cret")
    return TestClient(app)


def test_f04_fr03_the_expected_write_endpoints_exist() -> None:
    assert WRITE_PATHS == [
        "/events/demand",
        "/events/expedite-requested",
        "/events/goods-receipt",
        "/events/goods-receipt-reversal",
        "/events/hold",
        "/events/inbound-check",
        "/events/po-line-closed",
        "/events/po-line-created",
        "/events/reeval-lot",
        "/events/results-recorded",
        "/events/stock-block",
        "/events/stock-unblock",
        "/events/transfer",
        "/events/usage-decision",
    ]


@pytest.mark.parametrize("path", WRITE_PATHS)
def test_f04_ac03_every_write_without_the_token_is_401(client: TestClient, path: str) -> None:
    """F04-AC-03: writes without the scenario token return 401, whatever the body."""
    assert client.post(path, json={}).status_code == 401


@pytest.mark.parametrize("path", WRITE_PATHS)
def test_f04_ac03_every_write_with_a_wrong_token_is_401(client: TestClient, path: str) -> None:
    assert client.post(path, json={}, headers={"X-Scenario-Token": "wrong"}).status_code == 401


def test_f04_fr08_health_and_docs_are_open(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok", "service": "erp-sim"}
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_f04_fr10_invalid_bodies_are_422_when_the_token_is_right(client: TestClient) -> None:
    response = client.post(
        "/events/goods-receipt",
        json={"matnr": "RM10001", "charg": "B1", "lifnr": "SUP001", "lgort": "0100", "menge": -5},
        headers={"X-Scenario-Token": "s3cret"},
    )
    assert response.status_code == 422
