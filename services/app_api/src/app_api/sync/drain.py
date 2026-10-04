"""The drain worker's queue half: claim one event at a time (F08-FR-04).

A claim is one atomic ``UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1)``, committed at
once, so a locked or already claimed event is never handed out twice. A crash after the claim leaves a
``claimed`` row that becomes claimable again after five minutes. Queue timing is infrastructure time
(Postgres ``now()``, OQ-003 and OQ-054), never the demo clock.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app_api.models import SyncEvent

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
