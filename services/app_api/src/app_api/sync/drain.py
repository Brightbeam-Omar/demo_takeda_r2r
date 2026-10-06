"""The drain worker's queue half: claim one event at a time (F08-FR-04).

A claim is one atomic ``UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1)``, committed at
once, so a locked or already claimed event is never handed out twice. A crash after the claim leaves a
``claimed`` row that becomes claimable again after five minutes. Queue timing is infrastructure time
(Postgres ``now()``, OQ-003 and OQ-054), never the demo clock.
"""

import logging
import time
import uuid

from r2r_core.contract import ContractReader
from sqlalchemy import func, text, update
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql.elements import TextClause

from app_api.logs import bind
from app_api.models import SyncEvent
from app_api.sync.limits import STALE_CLAIM_MINUTES
from app_api.sync.mirror import sync_mirror

MAX_ERROR_CHARS = 2000
log = logging.getLogger(__name__)


def _claim_sql(include_stale: bool) -> TextClause:
    stale = (
        f"OR (status = 'claimed' AND claimed_at < now() - interval '{STALE_CLAIM_MINUTES} minutes')"
        if include_stale
        else ""
    )
    return text(
        f"""
        UPDATE sync_event
        SET status = 'claimed', claimed_at = now(), attempts = attempts + 1, drain_pass_id = :pass_id
        WHERE id = (
            SELECT id FROM sync_event
            WHERE status = 'pending' {stale}
            ORDER BY id
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id
        """
    )


_CLAIM = _claim_sql(True)
_CLAIM_PENDING_ONLY = _claim_sql(False)


def new_pass_id() -> str:
    return uuid.uuid4().hex[:12]


def claim_next(session: Session, pass_id: str | None = None, include_stale: bool = True) -> SyncEvent | None:
    """Claim the oldest claimable event and commit the claim; ``None`` when there is nothing to do.

    A claim counts as an attempt and records the drain pass that made it (F21-FR-04). ``include_stale=False``
    leaves events whose claim went stale to the next full pass (OQ-131).
    """
    statement = _CLAIM if include_stale else _CLAIM_PENDING_ONLY
    event_id = session.execute(statement, {"pass_id": pass_id or new_pass_id()}).scalar_one_or_none()
    session.commit()
    if event_id is None:
        return None
    return session.get(SyncEvent, event_id, populate_existing=True)


def process_event(factory: sessionmaker[Session], reader: ContractReader, event_id: int) -> None:
    """Mirror the published contract for a claimed event and mark it ``done`` or ``failed`` (F08-FR-05).

    The mirror and the ``done`` mark share one transaction. Any error rolls the mirror back and marks the
    event ``failed`` with the error text; the next webhook or manual trigger retries.
    """
    began = time.perf_counter()
    try:
        with factory() as session:
            result = sync_mirror(session, reader)
            session.execute(
                update(SyncEvent)
                .where(SyncEvent.id == event_id)
                .values(
                    status="done",
                    finished_at=func.now(),
                    rows_upserted=result.rows_upserted,
                    objects_synced=result.objects,
                    error=None,
                )
            )
            session.commit()
        log.info(
            "event_done",
            extra={"rows_upserted": result.rows_upserted, "noop": result.noop, "duration_ms": _ms(began)},
        )
    except Exception as error:
        message = f"{type(error).__name__}: {error}"[:MAX_ERROR_CHARS]
        with factory() as session:
            session.execute(
                update(SyncEvent)
                .where(SyncEvent.id == event_id)
                .values(status="failed", finished_at=func.now(), objects_synced=0, error=message)
            )
            session.commit()
        log.error("event_failed", extra={"error": message, "duration_ms": _ms(began)})


def _ms(began: float) -> float:
    return round((time.perf_counter() - began) * 1000, 1)


def drain_once(
    factory: sessionmaker[Session],
    reader: ContractReader,
    pass_id: str | None = None,
    include_stale: bool = True,
) -> int:
    """Claim and process events one at a time until none is claimable. Returns how many were processed."""
    processed = 0
    pass_id = pass_id or new_pass_id()
    while True:
        with factory() as session:
            event = claim_next(session, pass_id, include_stale)
            event_id, run_id = (None, None) if event is None else (event.id, event.run_id)
        if event_id is None:
            return processed
        with bind(event_id=event_id, run_id=run_id):
            log.info("event_claimed")
            process_event(factory, reader, event_id)
        processed += 1
