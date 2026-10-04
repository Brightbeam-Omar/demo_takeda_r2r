"""FastAPI helpers shared by the simulator services (F04)."""

import hmac
import os
from collections.abc import Callable, Iterator, Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from r2r_core.errors import Conflict, Invalid

TOKEN_ENV = "SCENARIO_TOKEN"
TOKEN_HEADER = "X-Scenario-Token"


async def require_scenario_token(x_scenario_token: Annotated[str | None, Header()] = None) -> None:
    """Guard for write endpoints: a missing or wrong token gives 401; an unset server token rejects all."""
    expected = os.environ.get(TOKEN_ENV, "")
    given = x_scenario_token or ""
    if not expected or not hmac.compare_digest(given.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail=f"missing or invalid {TOKEN_HEADER}")


def install_error_handlers(app: FastAPI) -> None:
    """Map event errors to HTTP: ``Conflict`` is 409, ``Invalid`` is 422."""

    @app.exception_handler(Conflict)
    async def _conflict(request: Request, error: Conflict) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(Invalid)
    async def _invalid(request: Request, error: Invalid) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(error)})


def health_router(service: str) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": service}

    return router


EventFunction = Callable[[Session, Any], dict[str, Any]]


def add_event_routes(
    router: APIRouter,
    events: Sequence[tuple[str, type[BaseModel], EventFunction]],
    get_session: Callable[[], Iterator[Session]],
) -> None:
    """Register ``POST <path>`` for each ``(path, body model, event function)``.

    Each request gets one session from ``get_session``, which commits on success and rolls back on any error,
    so one event is one transaction.
    """

    def make(function: EventFunction, body_type: type[BaseModel]) -> Callable[..., dict[str, Any]]:
        def endpoint(body: Any, session: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
            return function(session, body)

        endpoint.__annotations__["body"] = body_type
        return endpoint

    for path, body_type, function in events:
        router.add_api_route(path, make(function, body_type), methods=["POST"], name=function.__name__)
