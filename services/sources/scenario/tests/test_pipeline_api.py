"""T7: POST /pipeline/run launches the Dagster job over GraphQL (F07-FR-06)."""

import json
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from scenario.pipeline_api import DagsterClient, build_router

HEADERS = {"X-Scenario-Token": "s3cret"}


class FakeDagster:
    """A Dagster GraphQL endpoint: one repository with the job, a run that finishes after some polls."""

    def __init__(
        self, statuses: list[str], jobs: tuple[str, ...] = ("r2r_pipeline", "r2r_reset_lakehouse")
    ) -> None:
        self.statuses = list(statuses)
        self.jobs = jobs
        self.launched: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        query = payload["query"]
        if "FindJob" in query:
            nodes = [{"name": "__repository__", "location": {"name": "r2r_pipeline.dagster_defs"},
                      "jobs": [{"name": j} for j in self.jobs]}]  # fmt: skip
            data: dict[str, Any] = {
                "repositoriesOrError": {"__typename": "RepositoryConnection", "nodes": nodes}
            }
        elif "Launch" in query:
            self.launched.append(payload["variables"]["selector"])
            data = {"launchRun": {"__typename": "LaunchRunSuccess", "run": {"runId": "run-abc"}}}
        else:
            status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
            data = {"runOrError": {"__typename": "Run", "status": status}}
        return httpx.Response(200, json={"data": data})


def client_for(fake: FakeDagster, slept: list[float] | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(
        build_router(
            lambda: DagsterClient("http://dagster.test/graphql", httpx.MockTransport(fake)),
            sleep=(slept if slept is not None else []).append,
        )
    )
    return TestClient(app)


@pytest.fixture(autouse=True)
def token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCENARIO_TOKEN", "s3cret")


def test_f07_fr06_the_endpoint_needs_the_scenario_token() -> None:
    client = client_for(FakeDagster(["SUCCESS"]))
    assert client.post("/pipeline/run").status_code == 401
    assert client.post("/pipeline/run", headers={"X-Scenario-Token": "wrong"}).status_code == 401


def test_f07_fr06_without_wait_it_returns_the_dagster_run_id_at_once() -> None:
    fake = FakeDagster(["STARTED"])
    response = client_for(fake).post("/pipeline/run", headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == {"run_id": "run-abc", "status": "STARTED"}
    assert fake.launched == [
        {
            "repositoryLocationName": "r2r_pipeline.dagster_defs",
            "repositoryName": "__repository__",
            "jobName": "r2r_pipeline",
        }
    ]


def test_f07_fr06_wait_polls_until_the_run_succeeds() -> None:
    slept: list[float] = []
    response = client_for(FakeDagster(["STARTING", "STARTED", "SUCCESS"]), slept).post(
        "/pipeline/run?wait=true", headers=HEADERS
    )
    assert (response.status_code, response.json()) == (200, {"run_id": "run-abc", "status": "SUCCESS"})
    assert len(slept) == 2


def test_f07_fr06_wait_answers_502_when_the_run_fails() -> None:
    response = client_for(FakeDagster(["STARTED", "FAILURE"])).post(
        "/pipeline/run?wait=true", headers=HEADERS
    )
    assert (response.status_code, response.json()["status"]) == (502, "FAILURE")


def test_f07_fr06_wait_gives_up_after_the_timeout() -> None:
    response = client_for(FakeDagster(["STARTED"])).post(
        "/pipeline/run?wait=true&timeout_seconds=3", headers=HEADERS
    )
    assert (response.status_code, response.json()["status"]) == (502, "STARTED")


def test_f07_fr06_a_missing_job_is_a_clear_error() -> None:
    response = client_for(FakeDagster(["SUCCESS"], jobs=("other",))).post("/pipeline/run", headers=HEADERS)
    assert response.status_code == 502
    assert "r2r_pipeline" in response.json()["detail"]


def test_f07_fr06_an_unreachable_dagster_is_a_502() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    app = FastAPI()
    app.include_router(build_router(lambda: DagsterClient("http://x/graphql", httpx.MockTransport(refuse))))
    response = TestClient(app).post("/pipeline/run", headers=HEADERS)
    assert response.status_code == 502
    assert "not reachable" in response.json()["detail"]


def test_f07_fr06_a_dagster_python_error_is_reported_with_its_message() -> None:
    class Failing(FakeDagster):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            if "Launch" in json.loads(request.content)["query"]:
                body = {"data": {"launchRun": {"__typename": "PythonError", "message": "storage is down"}}}
                return httpx.Response(500, json=body)  # Dagster answers HTTP 500 with a GraphQL body
            return super().__call__(request)

    response = client_for(Failing(["SUCCESS"])).post("/pipeline/run", headers=HEADERS)
    assert response.status_code == 502
    assert "storage is down" in response.json()["detail"]


def test_f07_fr06_a_non_graphql_answer_is_a_502() -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="bad gateway")

    app = FastAPI()
    app.include_router(build_router(lambda: DagsterClient("http://x/graphql", httpx.MockTransport(broken))))
    response = TestClient(app).post("/pipeline/run", headers=HEADERS)
    assert response.status_code == 502
    assert "HTTP 503" in response.json()["detail"]
