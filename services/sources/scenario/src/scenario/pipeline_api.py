"""``POST /pipeline/run``: start the Dagster job ``r2r_pipeline`` through its GraphQL API (F07-FR-06).

Token-guarded like every scenario write. Without ``wait`` it returns the Dagster run id at once; with
``?wait=true`` it polls until the run ends and answers 200 for ``SUCCESS`` and 502 for anything else, so
``make pipeline`` (and F13's reset) can simply check the HTTP status. Nothing here knows about pipeline steps.
"""

import os
import time
from collections.abc import Callable
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from r2r_core.web import require_scenario_token

JOB_NAME = "r2r_pipeline"
FINISHED = {"SUCCESS", "FAILURE", "CANCELED"}
POLL_SECONDS = 1.0

FIND_JOB = """
query FindJob {
  repositoriesOrError {
    __typename
    ... on RepositoryConnection { nodes { name location { name } jobs { name } } }
    ... on PythonError { message }
  }
}
"""
LAUNCH = """
mutation Launch($selector: JobOrPipelineSelector!) {
  launchRun(executionParams: {selector: $selector}) {
    __typename
    ... on LaunchRunSuccess { run { runId } }
    ... on PythonError { message }
    ... on InvalidSubsetError { message }
    ... on RunConfigValidationInvalid { errors { message } }
    ... on UnauthorizedError { message }
  }
}
"""
STATUS = """
query Status($runId: ID!) {
  runOrError(runId: $runId) {
    __typename
    ... on Run { status }
    ... on RunNotFoundError { message }
    ... on PythonError { message }
  }
}
"""


class PipelineRunOut(BaseModel):
    run_id: str
    status: str


class DagsterClient:
    """The three GraphQL calls this service needs."""

    def __init__(self, url: str, transport: httpx.BaseTransport | None = None) -> None:
        self._url = url
        self._http = httpx.Client(transport=transport, timeout=30.0)

    def _query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self._http.post(self._url, json={"query": query, "variables": variables or {}})
        except httpx.HTTPError as error:
            raise HTTPException(status_code=502, detail=f"Dagster is not reachable: {error}") from error
        # Dagster answers HTTP 500 with a normal GraphQL body when a field fails, so read the body first.
        try:
            body: dict[str, Any] = response.json()
        except ValueError:
            body = {}
        if not isinstance(body.get("data"), dict):
            detail = body["errors"][0]["message"] if body.get("errors") else f"HTTP {response.status_code}"
            raise HTTPException(status_code=502, detail=f"Dagster GraphQL error: {detail}")
        data: dict[str, Any] = body["data"]
        return data

    def launch(self, job_name: str = JOB_NAME) -> str:
        found = self._query(FIND_JOB)["repositoriesOrError"]
        if found["__typename"] != "RepositoryConnection":
            raise HTTPException(
                status_code=502, detail=f"Dagster has no repositories: {found.get('message')}"
            )
        for repository in found["nodes"]:
            if job_name in {job["name"] for job in repository["jobs"]}:
                selector = {
                    "repositoryLocationName": repository["location"]["name"],
                    "repositoryName": repository["name"],
                    "jobName": job_name,
                }
                break
        else:
            raise HTTPException(status_code=502, detail=f"Dagster has no job named {job_name}")
        launched = self._query(LAUNCH, {"selector": selector})["launchRun"]
        if launched["__typename"] != "LaunchRunSuccess":
            raise HTTPException(status_code=502, detail=f"Dagster did not start the run: {launched}")
        run_id: str = launched["run"]["runId"]
        return run_id

    def status(self, run_id: str) -> str:
        result = self._query(STATUS, {"runId": run_id})["runOrError"]
        if result["__typename"] != "Run":
            raise HTTPException(status_code=502, detail=f"Dagster lost run {run_id}: {result.get('message')}")
        status: str = result["status"]
        return status


def wait_for_run(
    client: DagsterClient, run_id: str, timeout_seconds: float, sleep: Callable[[float], None] = time.sleep
) -> str:
    """Poll a Dagster run until it ends or the timeout passes; returns the last status seen."""
    waited, status = 0.0, "STARTED"
    while waited <= timeout_seconds:
        status = client.status(run_id)
        if status in FINISHED:
            break
        sleep(POLL_SECONDS)
        waited += POLL_SECONDS
    return status


def build_router(
    client_factory: Callable[[], DagsterClient] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> APIRouter:
    router = APIRouter(tags=["pipeline"])

    def make_client() -> DagsterClient:
        return DagsterClient(os.environ.get("DAGSTER_GRAPHQL_URL", "http://dagster-web:3001/graphql"))

    @router.post(
        "/pipeline/run", dependencies=[Depends(require_scenario_token)], response_model=PipelineRunOut
    )
    def run_pipeline(
        wait: bool = False, timeout_seconds: int = Query(default=300, ge=1, le=3600)
    ) -> JSONResponse:
        client = (client_factory or make_client)()
        run_id = client.launch()
        if not wait:
            return JSONResponse(PipelineRunOut(run_id=run_id, status="STARTED").model_dump())
        status = wait_for_run(client, run_id, timeout_seconds, sleep)
        body = PipelineRunOut(run_id=run_id, status=status).model_dump()
        return JSONResponse(body, status_code=200 if status == "SUCCESS" else 502)

    return router
