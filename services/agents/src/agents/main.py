"""Agents service API (port 8200). The nginx and Vite proxies strip the ``/agents-api`` prefix."""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, FastAPI
from pydantic import BaseModel
from r2r_core.web import health_router, install_error_handlers
from sqlalchemy import Engine

from agents.auth import Principal, current_principal
from agents.db import make_engine
from agents.settings import Settings


class MeOut(BaseModel):
    user_key: str
    display_name: str
    role: str


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    app_client: httpx.Client | None = None,
) -> FastAPI:
    config = settings or Settings.from_env()
    app = FastAPI(
        title="Agents service",
        description="Runs agents that propose; a validator and a person decide (F12).",
    )
    app.state.settings = config
    app.state.engine = engine or make_engine()
    app.state.app_client = app_client or httpx.Client(base_url=config.app_api_url, timeout=10)
    install_error_handlers(app)
    app.include_router(health_router("agents"))

    router = APIRouter()

    @router.get("/me")
    def me(principal: Annotated[Principal, Depends(current_principal)]) -> MeOut:
        return MeOut(user_key=principal.user_key, display_name=principal.display_name, role=principal.role)

    app.include_router(router)
    return app


app = create_app()
