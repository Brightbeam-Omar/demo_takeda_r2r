"""The application API (port 8000). F08 adds the sync endpoints; F09 adds reads, overrides and audit."""

from fastapi import FastAPI
from r2r_core.web import health_router

from app_api.routers import audit, export, me, metrics, overview, reference, rows
from app_api.sync import status, webhook


def create_app() -> FastAPI:
    app = FastAPI(title="R2R Intelligence application API")
    app.include_router(health_router("app-api"), prefix="/api")
    app.include_router(me.router, prefix="/api")
    app.include_router(overview.router, prefix="/api")
    for router in (audit.router, export.router, metrics.router, reference.router, rows.router):
        app.include_router(router, prefix="/api")
    app.include_router(webhook.router, prefix="/api/sync")
    app.include_router(status.router, prefix="/api/sync")
    return app


app = create_app()
