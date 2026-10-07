"""T6: ``/api/demo/*`` hides the scenario token and is for admins in DEMO_MODE only [F13-FR-06, F13-AC-04, OQ-147]."""

import json
from collections.abc import Iterator

import httpx
import pytest
from app_api.routers import demo
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

ADMIN = {"X-Demo-User": "admin"}
STREAM = 'id: 0\ndata: {"seq": 0, "kind": "start", "message": "hello"}\n\nid: 1\ndata: {"seq": 1, "kind": "done", "message": "bye"}\n\n'


class Scenario:
    """A stand-in for the scenario service behind an httpx mock transport."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.status = 200

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/scenario/steps":
            return httpx.Response(200, json=[{"id": "run-pipeline"}])
        if path.endswith("/events"):
            if self.status != 200:
                return httpx.Response(self.status, json={"detail": "unknown run nope"})
            return httpx.Response(200, content=STREAM.encode(), headers={"content-type": "text/event-stream"})
        if self.status != 200:
            return httpx.Response(
                self.status, json={"detail": {"error": "precondition_failed", "message": "not now"}}
            )
        return httpx.Response(202, json={"run_id": "abc123"})


@pytest.fixture
def scenario(monkeypatch: pytest.MonkeyPatch) -> Iterator[Scenario]:
    fake = Scenario()
    monkeypatch.setenv("SCENARIO_TOKEN", "s3cret-token")
    monkeypatch.setattr(
        demo,
        "make_client",
        lambda: httpx.Client(base_url="http://scenario.test", transport=httpx.MockTransport(fake)),
    )
    yield fake


def test_f13_fr06_outside_demo_mode_every_route_is_a_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, scenario: Scenario
) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    for method, path in (
        ("get", "/api/demo/steps"),
        ("post", "/api/demo/reset"),
        ("post", "/api/demo/steps/x/run"),
        ("get", "/api/demo/runs/x/events"),
    ):
        assert getattr(client, method)(path, headers=ADMIN).status_code == 404, path
    assert scenario.requests == []


@pytest.mark.parametrize("user", ["pat", "quinn", "alex", "sam"])
def test_f13_ac04_only_an_admin_may_use_it(client: TestClient, scenario: Scenario, user: str) -> None:
    """Planner, QC lead, QA release and viewer: all refused, and nothing reaches the scenario service."""
    response = client.post("/api/demo/reset", headers={"X-Demo-User": user})
    assert response.status_code == 403
    assert scenario.requests == []


def test_f13_ac04_a_planner_is_forbidden_and_it_is_audited(client: TestClient, scenario: Scenario) -> None:
    response = client.post("/api/demo/steps/run-pipeline/run", headers={"X-Demo-User": "pat"})
    assert response.status_code == 403
    items = client.get("/api/audit", headers=ADMIN).json()["items"]
    assert any(row["action"] == "forbidden" and row["actor_user_key"] == "pat" for row in items)


def test_f13_fr06_the_token_goes_upstream_and_never_comes_back(
    client: TestClient, scenario: Scenario
) -> None:
    responses = [
        client.get("/api/demo/steps", headers=ADMIN),
        client.post("/api/demo/steps/run-pipeline/run", headers=ADMIN),
        client.post("/api/demo/reset", headers=ADMIN),
        client.get("/api/demo/runs/abc123/events", headers=ADMIN),
    ]
    assert all(r.status_code in (200, 202) for r in responses)
    assert {r.headers["X-Scenario-Token"] for r in scenario.requests} == {"s3cret-token"}
    assert {r.headers["X-Actor-User"] for r in scenario.requests} == {"admin"}
    for response in responses:
        assert "s3cret-token" not in response.text and "x-scenario-token" not in {
            k.lower() for k in response.headers
        }


def test_f13_fr06_a_step_is_started_and_its_events_are_relayed_from_a_given_seq(
    client: TestClient, scenario: Scenario
) -> None:
    assert client.post("/api/demo/steps/run-pipeline/run", headers=ADMIN).json() == {"run_id": "abc123"}
    stream = client.get("/api/demo/runs/abc123/events?after=1", headers=ADMIN)
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert stream.text == STREAM
    assert scenario.requests[-1].url.params["after"] == "1"
    first = json.loads(stream.text.split("data: ")[1].split("\n")[0])
    assert first["message"] == "hello"


def test_f13_ac02_a_refused_step_keeps_its_status_and_message(client: TestClient, scenario: Scenario) -> None:
    scenario.status = 409
    response = client.post("/api/demo/steps/lims-approve-B1042/run", headers=ADMIN)
    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "not now"


def test_f13_fr06_an_unknown_run_is_a_404_not_a_broken_stream(client: TestClient, scenario: Scenario) -> None:
    scenario.status = 404
    response = client.get("/api/demo/runs/nope/events", headers=ADMIN)
    assert response.status_code == 404 and response.json()["detail"] == "unknown run nope"


def test_f13_fr06_an_unreachable_scenario_service_is_a_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    monkeypatch.setattr(
        demo,
        "make_client",
        lambda: httpx.Client(base_url="http://scenario.test", transport=httpx.MockTransport(refuse)),
    )
    assert client.get("/api/demo/steps", headers=ADMIN).status_code == 502
    assert client.get("/api/demo/runs/x/events", headers=ADMIN).status_code == 502
