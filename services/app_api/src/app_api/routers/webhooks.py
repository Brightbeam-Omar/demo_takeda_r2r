"""Webhook Sync Status data and the admin pipeline trigger (F21-FR-03, F21-FR-05).

``GET /api/sync/health`` is the six cards of the page, counted from ``sync_event`` and ``worker_heartbeat``
in infrastructure time (OQ-054). ``POST /api/sync/run-pipeline`` asks the scenario service to start the
Dagster job; the published run then reaches the app through the usual webhook, queue and drain.
"""

import os
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from r2r_core import clock
from sqlalchemy import text
from sqlalchemy.orm import Session

from app_api.auth import current_user, require_role
from app_api.db import get_session
from app_api.models import AppUser, AuditEvent
from app_api.sync.limits import STALE_CLAIM_MINUTES

router = APIRouter()
POLL_WINDOW_HOURS = 24
PROXY_TIMEOUT_SECONDS = 10


class SyncHealthOut(BaseModel):
    last_webhook_age_seconds: int | None
    pending: int
    error: int
    abandoned: int
    poll_fallbacks_24h: int
    poll_available: bool
    last_drain_age_seconds: int | None
    stale_claim_minutes: int


_HEALTH = text(
    f"""
    SELECT
      (SELECT floor(extract(epoch FROM now() - max(received_at)))::int
         FROM sync_event WHERE source = 'webhook') AS last_webhook_age_seconds,
      (SELECT count(*) FROM sync_event WHERE status = 'pending') AS pending,
      (SELECT count(*) FROM sync_event WHERE status = 'failed') AS error,
      (SELECT count(*) FROM sync_event
        WHERE status = 'claimed'
          AND (claimed_at < now() - interval '{STALE_CLAIM_MINUTES} minutes' OR attempts >= 2)) AS abandoned,
      (SELECT count(*) FROM sync_event
        WHERE source = 'poll' AND received_at > now() - interval '{POLL_WINDOW_HOURS} hours')
        AS poll_fallbacks_24h,
      (SELECT floor(extract(epoch FROM now() - max(last_loop_at)))::int
         FROM worker_heartbeat) AS last_drain_age_seconds
    """
)


@router.get("/health", dependencies=[Depends(current_user)])
def sync_health(session: Annotated[Session, Depends(get_session, scope="function")]) -> SyncHealthOut:
    row = session.execute(_HEALTH).mappings().one()
    return SyncHealthOut(**row, poll_available=False, stale_claim_minutes=STALE_CLAIM_MINUTES)


class PipelineTriggerOut(BaseModel):
    run_id: str
    status: str


@router.post("/run-pipeline", status_code=202)
def run_pipeline(
    session: Annotated[Session, Depends(get_session, scope="function")],
    admin: Annotated[AppUser, Depends(require_role("admin"))],
) -> PipelineTriggerOut:
    """Start a pipeline run through the scenario service (admin). Its webhook flows as usual."""
    url = os.environ.get("SCENARIO_URL", "http://scenario:8100")
    token = os.environ.get("SCENARIO_TOKEN", "")
    try:
        response = httpx.post(
            f"{url}/pipeline/run", headers={"X-Scenario-Token": token}, timeout=PROXY_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        body = response.json()
        result = PipelineTriggerOut(run_id=str(body["run_id"]), status=str(body["status"]))
    except (httpx.HTTPError, ValueError, KeyError) as error:
        raise HTTPException(status_code=502, detail=f"the pipeline could not be started: {error}") from error
    session.add(
        AuditEvent(
            at=clock.now(),
            actor_user_key=admin.user_key,
            action="pipeline_triggered",
            details_json={"pipeline_run_id": result.run_id},
        )
    )
    return result
