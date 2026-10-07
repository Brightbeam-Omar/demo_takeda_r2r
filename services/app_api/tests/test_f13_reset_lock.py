"""F13-FR-05 (OQ-148): the drain worker skips its passes while the demo reset holds the sync lock."""

import threading

import pytest
from app_api.models import SyncEvent
from app_api.sync.lock import drain_slot
from app_api.worker import run_forever
from r2r_core.sync_lock import RESET_LOCK_KEY
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from support import FakeReader, published

pytestmark = pytest.mark.integration


def hold_reset_lock(factory: sessionmaker[Session]) -> Session:
    """What the reset does: an exclusive, transaction-level advisory lock, kept until the session ends."""
    session = factory()
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": RESET_LOCK_KEY})
    return session


def test_f13_fr05_a_drain_pass_is_allowed_when_no_reset_runs(app_factory: sessionmaker[Session]) -> None:
    with drain_slot(app_factory) as allowed:
        assert allowed


def test_f13_fr05_a_drain_pass_is_refused_while_a_reset_holds_the_lock(
    app_factory: sessionmaker[Session],
) -> None:
    reset = hold_reset_lock(app_factory)
    try:
        with drain_slot(app_factory) as allowed:
            assert not allowed
    finally:
        reset.rollback()
        reset.close()
    with drain_slot(app_factory) as allowed:  # released: the worker carries on
        assert allowed


def test_f13_fr05_the_reset_waits_for_a_pass_that_is_running(app_factory: sessionmaker[Session]) -> None:
    """A pass holds the lock shared; the reset's exclusive request is not granted until the pass ends."""
    with drain_slot(app_factory) as allowed:
        assert allowed
        with app_factory() as other:
            other.execute(text("SET LOCAL lock_timeout = '300ms'"))
            with pytest.raises(Exception, match="lock timeout"):
                other.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": RESET_LOCK_KEY})


def test_f13_fr05_the_worker_loop_beats_but_does_not_drain_during_a_reset(
    app_factory: sessionmaker[Session],
) -> None:
    with app_factory() as session:
        session.add(SyncEvent(source="manual"))
        session.commit()
    reset = hold_reset_lock(app_factory)
    stop = threading.Event()
    passes: list[int] = []

    def sleep(seconds: float) -> None:
        passes.append(1)
        if len(passes) == 1:
            reset.rollback()  # the reset ends between two wakes
        else:
            stop.set()

    try:
        run_forever(app_factory, FakeReader(published("run-A")), 20, stop, sleep=sleep)
    finally:
        reset.close()
    with app_factory() as session:
        assert [e.status for e in session.query(SyncEvent)] == [
            "done"
        ]  # drained on the second wake, not the first
    assert passes == [1, 1]
