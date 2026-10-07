"""The worker's half of the reset lock (F13-FR-05, OQ-148).

A drain pass takes the lock shared, for the length of one transaction, so the demo reset (which takes it
exclusively) waits for a pass that is running and the worker skips every pass while the reset runs.
A transaction-level lock cannot leak: it is gone when the transaction ends, even if the worker crashes.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from r2r_core.sync_lock import RESET_LOCK_KEY
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker


@contextmanager
def drain_slot(factory: sessionmaker[Session]) -> Iterator[bool]:
    """Yields True when a drain pass may run, False while a reset holds the lock."""
    with factory() as session:
        granted = session.execute(
            text("SELECT pg_try_advisory_xact_lock_shared(:key)"), {"key": RESET_LOCK_KEY}
        ).scalar_one()
        try:
            yield bool(granted)
        finally:
            session.rollback()
