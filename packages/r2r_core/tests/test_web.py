"""T1: shared web helpers: scenario-token guard, error mapping, health [F04-FR-06, F04-FR-10]."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from r2r_core.errors import Conflict, Invalid
from r2r_core.web import health_router, install_error_handlers, require_scenario_token


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SCENARIO_TOKEN", "s3cret")
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(health_router("demo"))

    @app.post("/write", dependencies=[Depends(require_scenario_token)])
    def write() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/dup")
    def dup() -> None:
        raise Conflict("already exists")

    @app.post("/bad")
    def bad() -> None:
        raise Invalid("unknown material RM9")

    return TestClient(app)


def test_f04_ac03_missing_token_is_401(client: TestClient) -> None:
    assert client.post("/write").status_code == 401


def test_f04_ac03_wrong_token_is_401(client: TestClient) -> None:
    assert client.post("/write", headers={"X-Scenario-Token": "nope"}).status_code == 401


def test_f04_fr06_right_token_passes(client: TestClient) -> None:
    response = client.post("/write", headers={"X-Scenario-Token": "s3cret"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_f04_fr06_an_unset_server_token_rejects_everything(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SCENARIO_TOKEN")
    assert client.post("/write", headers={"X-Scenario-Token": ""}).status_code == 401
    assert client.post("/write", headers={"X-Scenario-Token": "s3cret"}).status_code == 401


def test_f04_fr10_conflict_maps_to_409_and_invalid_to_422(client: TestClient) -> None:
    dup = client.post("/dup")
    bad = client.post("/bad")
    assert (dup.status_code, dup.json()) == (409, {"detail": "already exists"})
    assert (bad.status_code, bad.json()) == (422, {"detail": "unknown material RM9"})


def test_f04_fr03_health_names_the_service(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "demo"}
