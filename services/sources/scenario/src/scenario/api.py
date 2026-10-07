"""The scenario API (F13-FR-03): the step list, run a step, follow a run, reset.

Every route needs the scenario token. The browser never holds it: app-api forwards for an admin in
``DEMO_MODE`` (OQ-147). A run is started with ``POST`` and followed with ``GET .../events`` (Server-Sent
Events). The stream starts at ``?after=<seq>`` and replays every line since, so a late subscriber
misses nothing.
"""

import json
from collections.abc import Callable, Iterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from r2r_core.web import require_scenario_token

from scenario.runner import Busy, PreconditionFailed, Run, Runner, RunRegistry, UnknownStep

KEEPALIVE_SECONDS = 15.0
ActorHeader = Annotated[str, Header(alias="X-Actor-User")]


class RunStarted(BaseModel):
    run_id: str


class RunState(BaseModel):
    run_id: str
    kind: str
    name: str
    status: str
    events: int


def sse(run: Run, after: int, keepalive: float = KEEPALIVE_SECONDS) -> Iterator[str]:
    sent = after
    while True:
        events = run.wait_for_events(sent, keepalive)
        for event in events:
            yield f"id: {event['seq']}\ndata: {json.dumps(event)}\n\n"
        sent += len(events)
        if run.status != "running" and not run.wait_for_events(sent, 0):
            return
        if not events:
            yield ": keepalive\n\n"


def build_router(
    runner: Runner, registry: RunRegistry, start_reset: Callable[[str], Run] | None = None
) -> APIRouter:
    router = APIRouter(prefix="/scenario", tags=["scenario"], dependencies=[Depends(require_scenario_token)])

    @router.get("/steps")
    def steps() -> list[dict[str, Any]]:
        return runner.listing()

    @router.post("/steps/{step_id}/run", status_code=202)
    def run_step(step_id: str, actor: ActorHeader = "system") -> RunStarted:
        try:
            run = runner.start(step_id, actor)
        except UnknownStep as error:
            raise HTTPException(status_code=404, detail=f"unknown step {step_id}") from error
        except Busy as error:
            raise HTTPException(status_code=409, detail={"error": "busy", "message": str(error)}) from error
        except PreconditionFailed as error:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "precondition_failed",
                    "message": error.messages[0],
                    "messages": error.messages,
                },
            ) from error
        return RunStarted(run_id=run.id)

    if start_reset is not None:

        @router.post("/reset", status_code=202)
        def reset(actor: ActorHeader = "system") -> RunStarted:
            try:
                run = start_reset(actor)
            except Busy as error:
                raise HTTPException(
                    status_code=409, detail={"error": "busy", "message": str(error)}
                ) from error
            return RunStarted(run_id=run.id)

    def known(run_id: str) -> Run:
        run = registry.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"unknown run {run_id}")
        return run

    @router.get("/runs/{run_id}")
    def run_state(run_id: str) -> RunState:
        run = known(run_id)
        return RunState(
            run_id=run.id, kind=run.kind, name=run.name, status=run.status, events=len(run.events)
        )

    @router.get("/runs/{run_id}/events")
    def run_events(run_id: str, after: Annotated[int, Query(ge=0)] = 0) -> StreamingResponse:
        return StreamingResponse(
            sse(known(run_id), after),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router
