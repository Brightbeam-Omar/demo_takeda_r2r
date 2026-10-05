"""``POST /api/sync/webhook``: the pipeline's signed "a run was published" notice (F08-FR-02).

The endpoint verifies the HMAC over the raw bytes, queues one ``sync_event`` and answers 202. It never reads
the lakehouse: this module does not import the contract reader (F08-AC-07). A rejected call leaves an
``audit_event`` and no queue row (so the 401 and 422 answers are returned, not raised: raising would roll the
audit row back).
"""

import hashlib
import hmac
import json
import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from r2r_core import clock
from sqlalchemy.orm import Session

from app_api.db import get_session
from app_api.models import AuditEvent, SyncEvent

MAX_BODY_BYTES = 1024 * 1024
router = APIRouter()


def verify_signature(secret: str, body: bytes, header: str | None) -> bool:
    """True when ``header`` is ``sha256=<hex>``, the HMAC-SHA256 of ``body``. An unset secret rejects all."""
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header.removeprefix("sha256=").encode(), expected.encode())


def _reject(session: Session, status: int, reason: str) -> JSONResponse:
    session.add(
        AuditEvent(
            at=clock.now(),
            actor_user_key="system",
            action="webhook_rejected",
            details_json={"reason": reason},
        )
    )
    return JSONResponse(status_code=status, content={"detail": reason})


def _run_id(body: bytes) -> str | None:
    try:
        payload: Any = json.loads(body)
    except ValueError:
        return None
    run_id = payload.get("run_id") if isinstance(payload, dict) else None
    return run_id if isinstance(run_id, str) and run_id else None


@router.post("/webhook")
async def webhook(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    x_signature: Annotated[str | None, Header()] = None,
) -> JSONResponse:
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        return _reject(session, 413, "body_too_large")  # refused before the body is read
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        return _reject(session, 413, "body_too_large")
    if not verify_signature(os.environ.get("WEBHOOK_SECRET", ""), body, x_signature):
        return _reject(session, 401, "bad_signature")
    run_id = _run_id(body)
    if run_id is None:
        return _reject(session, 422, "invalid_body")
    event = SyncEvent(source="webhook", status="pending", run_id=run_id)
    session.add(event)
    session.flush()
    return JSONResponse(status_code=202, content={"event_id": event.id})
