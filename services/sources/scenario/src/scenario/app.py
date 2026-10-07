"""Scenario service API (port 8100): the demo clock, pipeline trigger, scenario steps and demo reset (F13)."""

import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from r2r_core import clock
from r2r_core.db import make_engine, postgres_dsn
from r2r_core.profile import SiteProfile
from r2r_core.web import health_router, install_error_handlers
from sqlalchemy import Engine

from scenario.api import build_router as build_scenario_router
from scenario.clock_api import build_router, default_profile, seed_clock
from scenario.gateway import Endpoints, Gateway
from scenario.pipeline_api import DagsterClient
from scenario.pipeline_api import build_router as build_pipeline_router
from scenario.runner import Runner, RunRegistry
from scenario.steps import Step, load_steps


def create_app(
    engine: Engine | None = None,
    profile: SiteProfile | None = None,
    gateway: Gateway | None = None,
    dagster: Callable[[], DagsterClient] | None = None,
    steps: list[Step] | None = None,
) -> FastAPI:
    db_engine = engine or make_engine(os.environ.get("APP_DSN") or postgres_dsn("app"))
    site = profile or default_profile()
    registry = RunRegistry()
    runner = Runner(
        steps if steps is not None else load_steps(),
        gateway or Gateway(Endpoints.from_env()),
        db_engine,
        dagster
        or (lambda: DagsterClient(os.environ.get("DAGSTER_GRAPHQL_URL", "http://dagster-web:3001/graphql"))),
        registry,
        now=clock.now,
    )

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
    app.include_router(build_pipeline_router())
    app.include_router(build_scenario_router(runner, registry))
    return app


app = create_app()
