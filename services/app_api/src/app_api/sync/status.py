"""``GET /api/sync/status`` and ``POST /api/sync/trigger`` (F08-FR-03, FR-07, FR-11).

Sync times are wall-clock (Postgres ``now()``) while the UI shows the demo clock, so events are returned as
ISO timestamps plus ``age_seconds`` and ``duration_ms``; the UI shows relative ages, never absolute dates
(OQ-054). ``freshness_minutes`` is the one demo-clock value: demo now minus ``last_success_at``.
"""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from r2r_core import clock
from sqlalchemy import text
from sqlalchemy.orm import Session

from app_api.auth import require_role
from app_api.db import get_session
from app_api.models import AppUser, AuditEvent, SyncEvent

router = APIRouter()
EVENT_LIMIT = 50


class SyncEventOut(BaseModel):
    id: int
    source: str
    run_id: str | None
    status: str
    received_at: datetime
    claimed_at: datetime | None
    finished_at: datetime | None
    error: str | None
    rows_upserted: int | None
    attempts: int
    objects_synced: int | None
    drain_pass_id: str | None
    age_seconds: int
    duration_ms: int | None


class WatermarkOut(BaseModel):
    object_name: str
    run_id: str
    synced_at: datetime
    age_seconds: int


class PipelineStatusOut(BaseModel):
    last_run_id: str
    started_at: datetime
    last_success_at: datetime
    row_count: int
    source_freshness: dict[str, Any]


class SyncStatusOut(BaseModel):
    events: list[SyncEventOut]
    watermarks: list[WatermarkOut]
    pipeline_status: PipelineStatusOut | None
    freshness_minutes: int | None


@router.get("/status")
def sync_status(session: Annotated[Session, Depends(get_session, scope="function")]) -> SyncStatusOut:
    events = session.execute(
        text(
            """
            SELECT id, source, run_id, status, received_at, claimed_at, finished_at, error, rows_upserted,
                   attempts, objects_synced, drain_pass_id,
                   floor(extract(epoch FROM now() - received_at))::int AS age_seconds,
                   round(extract(epoch FROM finished_at - claimed_at) * 1000)::int AS duration_ms
            FROM sync_event ORDER BY id DESC LIMIT :limit
            """
        ),
        {"limit": EVENT_LIMIT},
    ).mappings()
    watermarks = session.execute(
        text(
            """
            SELECT object_name, run_id, synced_at,
                   floor(extract(epoch FROM now() - synced_at))::int AS age_seconds
            FROM watermark ORDER BY object_name
            """
        )
    ).mappings()
    row = (
        session.execute(
            text(
                "SELECT last_run_id, started_at, last_success_at, row_count, source_freshness_json "
                "FROM mirror_pipeline_status"
            )
        )
        .mappings()
        .first()
    )
    pipeline = (
        None
        if row is None
        else PipelineStatusOut(
            last_run_id=row["last_run_id"],
            started_at=row["started_at"],
            last_success_at=row["last_success_at"],
            row_count=row["row_count"],
            source_freshness=row["source_freshness_json"] or {},
        )
    )
    freshness = None
    if pipeline is not None:
        freshness = max(0, int((clock.now() - pipeline.last_success_at).total_seconds() // 60))
    return SyncStatusOut(
        events=[SyncEventOut(**event) for event in events],
        watermarks=[WatermarkOut(**mark) for mark in watermarks],
        pipeline_status=pipeline,
        freshness_minutes=freshness,
    )


@router.post("/trigger")
def trigger(
    session: Annotated[Session, Depends(get_session, scope="function")],
    admin: Annotated[AppUser, Depends(require_role("admin"))],
) -> JSONResponse:
    """Queue a manual sync (the worker mirrors whatever is published now)."""
    event = SyncEvent(source="manual", status="pending")
    session.add(event)
    session.flush()
    session.add(
        AuditEvent(
            at=clock.now(),
            actor_user_key=admin.user_key,
            action="sync_triggered",
            details_json={"event_id": event.id},
        )
    )
    return JSONResponse(status_code=202, content={"event_id": event.id})
