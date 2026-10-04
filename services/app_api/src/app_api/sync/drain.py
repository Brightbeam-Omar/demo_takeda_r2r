"""The drain worker's queue half: claim one event at a time (F08-FR-04).

A claim is one atomic ``UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1)``, committed at
once, so a locked or already claimed event is never handed out twice. A crash after the claim leaves a
``claimed`` row that becomes claimable again after five minutes. Queue timing is infrastructure time
(Postgres ``now()``, OQ-003 and OQ-054), never the demo clock.
"""

from r2r_core.contract import ContractReader
from sqlalchemy import func, text, update
from sqlalchemy.orm import Session, sessionmaker

from app_api.models import SyncEvent
from app_api.sync.mirror import sync_mirror

MAX_ERROR_CHARS = 2000

STALE_CLAIM_MINUTES = 5

_CLAIM = text(
    f"""
    UPDATE sync_event SET status = 'claimed', claimed_at = now()
    WHERE id = (
        SELECT id FROM sync_event
        WHERE status = 'pending'
           OR (status = 'claimed' AND claimed_at < now() - interval '{STALE_CLAIM_MINUTES} minutes')
        ORDER BY id
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING id
    """
)


def claim_next(session: Session) -> SyncEvent | None:
    """Claim the oldest claimable event and commit the claim; ``None`` when there is nothing to do."""
    event_id = session.execute(_CLAIM).scalar_one_or_none()
    session.commit()
    if event_id is None:
        return None
    return session.get(SyncEvent, event_id, populate_existing=True)


def process_event(factory: sessionmaker[Session], reader: ContractReader, event_id: int) -> None:
    """Mirror the published contract for a claimed event and mark it ``done`` or ``failed`` (F08-FR-05).

    The mirror and the ``done`` mark share one transaction. Any error rolls the mirror back and marks the
    event ``failed`` with the error text; the next webhook or manual trigger retries.
    """
    try:
        with factory() as session:
            result = sync_mirror(session, reader)
            session.execute(
                update(SyncEvent)
                .where(SyncEvent.id == event_id)
                .values(status="done", finished_at=func.now(), rows_upserted=result.rows_upserted, error=None)
            )
            session.commit()
    except Exception as error:
        message = f"{type(error).__name__}: {error}"[:MAX_ERROR_CHARS]
        with factory() as session:
            session.execute(
                update(SyncEvent)
                .where(SyncEvent.id == event_id)
                .values(status="failed", finished_at=func.now(), error=message)
            )
            session.commit()


def drain_once(factory: sessionmaker[Session], reader: ContractReader) -> int:
    """Claim and process events one at a time until none is claimable. Returns how many were processed."""
    processed = 0
    while True:
        with factory() as session:
            event = claim_next(session)
            event_id = None if event is None else event.id
        if event_id is None:
            return processed
        process_event(factory, reader, event_id)
        processed += 1
