"""F08-FR-04: claiming events with SKIP LOCKED and reclaiming stale claims. Covers F08-AC-03 and the claim half of AC-04."""

import threading

import pytest
from app_api.models import SyncEvent
from app_api.sync.drain import claim_next
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration


def add_event(factory: sessionmaker[Session], **values: object) -> int:
    with factory() as session:
        event = SyncEvent(source="webhook", **values)
        session.add(event)
        session.commit()
        return event.id


def set_claimed(factory: sessionmaker[Session], event_id: int, minutes_ago: int) -> None:
    with factory() as session:
        session.execute(
            text(
                "UPDATE sync_event SET status = 'claimed', claimed_at = now() - make_interval(mins => :m) WHERE id = :i"
            ),
            {"m": minutes_ago, "i": event_id},
        )
        session.commit()


def test_f08_fr04_claims_the_oldest_pending_event_and_marks_it_claimed(
    app_factory: sessionmaker[Session],
) -> None:
    first = add_event(app_factory, run_id="r1")
    add_event(app_factory, run_id="r2")
    with app_factory() as session:
        claimed = claim_next(session)
        assert claimed is not None
        assert (claimed.id, claimed.status, claimed.run_id) == (first, "claimed", "r1")
        assert claimed.claimed_at is not None
    with app_factory() as session:
        assert session.get(SyncEvent, first).status == "claimed"


def test_f08_fr04_returns_none_when_nothing_is_claimable(app_factory: sessionmaker[Session]) -> None:
    with app_factory() as session:
        assert claim_next(session) is None
    done = add_event(app_factory, run_id="r1")
    with app_factory() as session:
        session.execute(text("UPDATE sync_event SET status = 'done' WHERE id = :i"), {"i": done})
        session.commit()
    failed = add_event(app_factory, run_id="r2")
    with app_factory() as session:
        session.execute(text("UPDATE sync_event SET status = 'failed' WHERE id = :i"), {"i": failed})
        session.commit()
    with app_factory() as session:
        assert claim_next(session) is None


def test_f08_ac03_a_row_locked_by_another_transaction_is_skipped(app_factory: sessionmaker[Session]) -> None:
    locked = add_event(app_factory, run_id="r1")
    other = add_event(app_factory, run_id="r2")
    with app_factory() as holder:
        holder.execute(text("SELECT id FROM sync_event WHERE id = :i FOR UPDATE"), {"i": locked})
        with app_factory() as session:
            claimed = claim_next(session)
            assert claimed is not None
            assert claimed.id == other  # skipped the locked row instead of waiting for it
            assert claim_next(session) is None
        holder.rollback()


def test_f08_ac03_two_workers_never_claim_the_same_event(app_factory: sessionmaker[Session]) -> None:
    add_event(app_factory, run_id="only")
    barrier = threading.Barrier(2)
    results: list[int | None] = []

    def worker() -> None:
        with app_factory() as session:
            barrier.wait()
            event = claim_next(session)
            results.append(None if event is None else event.id)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results, key=lambda r: (r is None, r)) == [1, None]


def test_f08_ac03_many_workers_and_events_claim_each_event_exactly_once(
    app_factory: sessionmaker[Session],
) -> None:
    ids = {add_event(app_factory, run_id=f"r{n}") for n in range(12)}
    claimed: list[int] = []
    guard = threading.Lock()

    def worker() -> None:
        while True:
            with app_factory() as session:
                event = claim_next(session)
            if event is None:
                return
            with guard:
                claimed.append(event.id)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(claimed) == sorted(ids)


def test_f08_ac04_a_claim_older_than_five_minutes_is_reclaimed(app_factory: sessionmaker[Session]) -> None:
    event_id = add_event(app_factory, run_id="r1")
    set_claimed(app_factory, event_id, minutes_ago=6)
    with app_factory() as session:
        reclaimed = claim_next(session)
        assert reclaimed is not None
        assert reclaimed.id == event_id
        assert reclaimed.status == "claimed"
    with app_factory() as session:
        age = session.execute(
            text("SELECT now() - claimed_at FROM sync_event WHERE id = :i"), {"i": event_id}
        ).scalar_one()
        assert age.total_seconds() < 60  # claimed_at was refreshed


def test_f08_ac04_a_recent_claim_is_left_alone(app_factory: sessionmaker[Session]) -> None:
    event_id = add_event(app_factory, run_id="r1")
    set_claimed(app_factory, event_id, minutes_ago=4)
    with app_factory() as session:
        assert claim_next(session) is None


def test_f08_fr04_pending_events_are_claimed_in_arrival_order(app_factory: sessionmaker[Session]) -> None:
    ids = [add_event(app_factory, run_id=f"r{n}") for n in range(3)]
    order: list[int] = []
    for _ in ids:
        with app_factory() as session:
            event = claim_next(session)
            assert event is not None
            order.append(event.id)
    assert order == ids
