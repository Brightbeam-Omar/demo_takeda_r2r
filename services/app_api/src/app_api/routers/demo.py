"""``/api/demo/*``: what the Demo Controls page calls (F13-FR-06, OQ-147).

The browser never sees the scenario token. These routes answer 404 unless ``DEMO_MODE`` is on and 403 unless
the caller is an admin, then forward to the scenario service with the token and the clicking admin's user
key (the audit actor). A step is started with ``POST`` and followed with ``GET .../events`` (Server-Sent
Events, replayed from ``?after=``).
"""

import os
from collections.abc import Iterator
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app_api.auth import demo_mode, require_role
from app_api.models import AppUser


def demo_only() -> None:
    if not demo_mode():
        raise HTTPException(status_code=404, detail="Not Found")


Admin = Annotated[AppUser, Depends(require_role("admin"))]
router = APIRouter(prefix="/demo", tags=["demo"], dependencies=[Depends(demo_only)])


def make_client() -> httpx.Client:
    return httpx.Client(base_url=os.environ.get("SCENARIO_URL", "http://scenario:8100"), timeout=30.0)


def _headers(user: AppUser) -> dict[str, str]:
    return {"X-Scenario-Token": os.environ.get("SCENARIO_TOKEN", ""), "X-Actor-User": user.user_key}


def _relay(method: str, path: str, user: AppUser) -> Response:
    with make_client() as client:
        try:
            upstream = client.request(method, path, headers=_headers(user))
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=502, detail=f"the scenario service is not reachable: {error}"
            ) from error
    body: Any = upstream.json() if upstream.content else None
    return JSONResponse(body, status_code=upstream.status_code)


@router.get("/steps")
def steps(user: Admin) -> Response:
    return _relay("GET", "/scenario/steps", user)


@router.post("/steps/{step_id}/run")
def run_step(step_id: str, user: Admin) -> Response:
    return _relay("POST", f"/scenario/steps/{step_id}/run", user)


@router.post("/reset")
def reset(user: Admin) -> Response:
    return _relay("POST", "/scenario/reset", user)


@router.get("/runs/{run_id}/events")
def run_events(run_id: str, user: Admin, after: Annotated[int, Query(ge=0)] = 0) -> Response:
    client = make_client()
    try:
        request = client.build_request(
            "GET", f"/scenario/runs/{run_id}/events", params={"after": after}, headers=_headers(user)
        )
        upstream = client.send(request, stream=True)
    except httpx.HTTPError as error:
        client.close()
        raise HTTPException(
            status_code=502, detail=f"the scenario service is not reachable: {error}"
        ) from error
    if upstream.status_code != 200:
        body = upstream.read()
        client.close()
        return JSONResponse(
            httpx.Response(upstream.status_code, content=body).json(), status_code=upstream.status_code
        )

    def relay() -> Iterator[bytes]:
        try:
            yield from upstream.iter_bytes()
        finally:
            upstream.close()
            client.close()

    return StreamingResponse(
        relay(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
