"""Scenario service API (port 8100): the demo clock now; scenario steps later (F13)."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from r2r_core.db import make_engine, postgres_dsn
from r2r_core.profile import SiteProfile
from r2r_core.web import health_router, install_error_handlers
from sqlalchemy import Engine

from scenario.clock_api import build_router, default_profile, seed_clock


def create_app(engine: Engine | None = None, profile: SiteProfile | None = None) -> FastAPI:
    db_engine = engine or make_engine(os.environ.get("APP_DSN") or postgres_dsn("app"))
    site = profile or default_profile()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        seed_clock(db_engine, site)  # first start only: an existing row is never overwritten
        yield

    app = FastAPI(
        title="Scenario service",
        description="Owns the demo clock. `POST /clock/*` need `X-Scenario-Token`.",
        lifespan=lifespan,
    )
    install_error_handlers(app)
    app.include_router(health_router("scenario"))
    app.include_router(build_router(db_engine, site))
    return app


app = create_app()
