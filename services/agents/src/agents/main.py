"""Agents service API (port 8200). The nginx and Vite proxies strip the ``/agents-api`` prefix."""

import os
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from r2r_core.profile import SiteProfile, load_profile
from r2r_core.web import health_router, install_error_handlers
from sqlalchemy import Engine

from agents.auth import Principal, current_principal
from agents.db import make_engine
from agents.deps import Deps
from agents.gateway import build_gateway
from agents.gateway.base import ModelGateway
from agents.harness.proposals import ProposalError
from agents.routes import router as agents_router
from agents.settings import Settings
from agents.tools.http import ReadOnlyHttp


class MeOut(BaseModel):
    user_key: str
    display_name: str
    role: str


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    app_client: httpx.Client | None = None,
    *,
    http: ReadOnlyHttp | None = None,
    gateway: ModelGateway | None = None,
    profile: SiteProfile | None = None,
) -> FastAPI:
    config = settings or Settings.from_env()
    app = FastAPI(
        title="Agents service",
        description="Runs agents that propose; a validator and a person decide (F12).",
    )
    app.state.settings = config
    app.state.engine = engine or make_engine()
    app.state.app_client = app_client or httpx.Client(base_url=config.app_api_url, timeout=10)
    app.state.deps = Deps(
        settings=config,
        engine=app.state.engine,
        http=http or ReadOnlyHttp.from_settings(config),
        gateway=gateway or build_gateway(config),
        profile=profile or load_profile(os.environ.get("SITE_PROFILE", "site_a")),
    )
    install_error_handlers(app)

    @app.exception_handler(ProposalError)
    async def _proposal_error(request: Request, error: ProposalError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"detail": error.detail})

    app.include_router(health_router("agents"))
    app.include_router(agents_router)

    router = APIRouter()

    @router.get("/me")
    def me(principal: Annotated[Principal, Depends(current_principal)]) -> MeOut:
        return MeOut(user_key=principal.user_key, display_name=principal.display_name, role=principal.role)

    app.include_router(router)
    return app


app = create_app()
