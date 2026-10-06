"""T3: attempts, objects_synced and drain pass id, the worker heartbeat and 2 s wake, health cards and the
admin pipeline trigger (F21-FR-03, F21-FR-04, F21-FR-05; OQ-130, OQ-131)."""

import threading
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from app_api.models import MIRROR_TABLES, SyncEvent
from app_api.sync.drain import claim_next, drain_once
from app_api.worker import WAKE_SECONDS, run_forever
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from support import FakeReader, published, queue

pytestmark = pytest.mark.integration
ADMIN = {"X-Demo-User": "admin"}


def event(factory: sessionmaker[Session], event_id: int) -> SyncEvent:
    with factory() as session:
        return session.get_one(SyncEvent, event_id)


def sql(factory: sessionmaker[Session], statement: str, **params: Any) -> None:
    with factory() as session:
        session.execute(text(statement), params)
        session.commit()


def test_f21_fr04_each_claim_counts_an_attempt_and_records_the_drain_pass(
    app_factory: sessionmaker[Session],
) -> None:
    event_id = queue(app_factory)
    assert event(app_factory, event_id).attempts == 0
    with app_factory() as session:
        claimed = claim_next(session, "pass-a")
        assert claimed is not None
        assert (claimed.attempts, claimed.drain_pass_id) == (1, "pass-a")
    sql(app_factory, "UPDATE sync_event SET claimed_at = now() - interval '6 minutes'")
    with app_factory() as session:
        again = claim_next(session, "pass-b")  # the stale claim is taken back
        assert again is not None
        assert (again.attempts, again.drain_pass_id) == (2, "pass-b")


def test_f21_fr04_a_pending_only_claim_leaves_stale_claims_alone(app_factory: sessionmaker[Session]) -> None:
    event_id = queue(app_factory)
    sql(
        app_factory,
        "UPDATE sync_event SET status = 'claimed', claimed_at = now() - interval '9 minutes', attempts = 1",
    )
    with app_factory() as session:
        assert claim_next(session, "p", include_stale=False) is None
        taken = claim_next(session, "p", include_stale=True)
        assert taken is not None and taken.id == event_id


def test_f21_fr04_a_done_event_records_how_many_objects_were_synced(
    app_factory: sessionmaker[Session],
) -> None:
    first, second = queue(app_factory, "run-A"), queue(app_factory, "run-A")
    drain_once(app_factory, FakeReader(published("run-A")), "pass-1")
    done, noop = event(app_factory, first), event(app_factory, second)
    assert (done.status, done.objects_synced, done.attempts, done.drain_pass_id) == (
        "done",
        len(MIRROR_TABLES),
        1,
        "pass-1",
    )
    assert (noop.status, noop.objects_synced, noop.rows_upserted) == ("done", 0, 0)


def test_f21_fr04_a_failed_event_keeps_its_error_and_syncs_no_object(
    app_factory: sessionmaker[Session],
) -> None:
    event_id = queue(app_factory, "run-A")
    broken = FakeReader(published("run-A"))
    broken.unavailable = True
    drain_once(app_factory, broken)
    failed = event(app_factory, event_id)
    assert (failed.status, failed.objects_synced, failed.attempts) == ("failed", 0, 1)
    assert failed.error and "no published data" in failed.error


def test_f21_fr04_every_wake_beats_and_a_full_pass_runs_on_the_interval(
    app_factory: sessionmaker[Session],
) -> None:
    assert WAKE_SECONDS == 2
    stop = threading.Event()
    waits: list[float] = []
    ticks = iter(range(0, 1000, 2))  # the monotonic clock: 2 s per wake

    def sleep(seconds: float) -> None:
        waits.append(seconds)
        if len(waits) == 12:
            stop.set()

    stale = queue(app_factory, "run-A")
    sql(
        app_factory,
        "UPDATE sync_event SET status = 'claimed', claimed_at = now() - interval '9 minutes', attempts = 1",
    )
    run_forever(
        app_factory,
        FakeReader(published("run-A")),
        interval_seconds=20,
        stop=stop,
        sleep=sleep,
        monotonic=lambda: float(next(ticks)),
        worker_id="w1",
    )
    assert waits == [2] * 12
    with app_factory() as session:
        beat = session.execute(
            text("SELECT worker_id, last_pass_id, now() - last_loop_at FROM worker_heartbeat")
        ).one()
    assert beat[0] == "w1" and beat[1] and beat[2].total_seconds() < 30
    assert (
        event(app_factory, stale).status == "done"
    )  # the first wake was a full pass: it took the stale claim


def test_f21_fr04_between_full_passes_a_stale_claim_waits_but_pending_events_do_not(
    app_factory: sessionmaker[Session],
) -> None:
    stop = threading.Event()
    state = {"wakes": 0, "ids": []}  # type: ignore[var-annotated]
    ticks = iter([0.0, 2.0, 4.0, 6.0, 8.0])

    def sleep(seconds: float) -> None:
        state["wakes"] += 1
        if state["wakes"] == 1:  # after the first (full) pass: one stale claim and one fresh event appear
            stale = queue(app_factory, "run-A")
            sql(
                app_factory,
                "UPDATE sync_event SET status='claimed', claimed_at=now()-interval '9 minutes', attempts=1 WHERE id=:i",
                i=stale,
            )
            state["ids"] = [stale, queue(app_factory, "run-A")]
        elif state["wakes"] == 2:
            stop.set()

    run_forever(app_factory, FakeReader(published("run-A")), 20, stop, sleep, monotonic=lambda: next(ticks))
    stale_id, fresh_id = state["ids"]
    assert event(app_factory, fresh_id).status == "done"  # picked up by the second wake (not a full pass)
    assert event(app_factory, stale_id).status == "claimed"  # waits for the next full pass


def health(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/sync/health")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def test_f21_fr03_the_cards_at_rest_before_any_event_or_worker(client: TestClient) -> None:
    body = health(client)
    assert (body["pending"], body["error"], body["abandoned"], body["poll_fallbacks_24h"]) == (0, 0, 0, 0)
    assert body["last_webhook_age_seconds"] is None and body["last_drain_age_seconds"] is None
    assert body["poll_available"] is False and body["stale_claim_minutes"] == 5


def test_f21_fr03_oq130_abandoned_counts_only_claimed_events_and_error_only_failed_ones(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    ids = [queue(app_factory) for _ in range(6)]
    sql(
        app_factory,
        "UPDATE sync_event SET status='claimed', claimed_at=now(), attempts=1 WHERE id=:i",
        i=ids[0],
    )  # fresh claim
    sql(
        app_factory,
        "UPDATE sync_event SET status='claimed', claimed_at=now()-interval '6 minutes', attempts=1 WHERE id=:i",
        i=ids[1],
    )  # stale
    sql(
        app_factory,
        "UPDATE sync_event SET status='claimed', claimed_at=now(), attempts=2 WHERE id=:i",
        i=ids[2],
    )  # second attempt
    sql(
        app_factory, "UPDATE sync_event SET status='done', attempts=2 WHERE id=:i", i=ids[3]
    )  # recovered: not abandoned
    sql(app_factory, "UPDATE sync_event SET status='failed', attempts=3 WHERE id=:i", i=ids[4])  # error only
    body = health(client)
    assert (body["pending"], body["error"], body["abandoned"]) == (1, 1, 2)


def test_f21_fr03_last_webhook_poll_count_and_last_drain(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    queue(app_factory)
    sql(app_factory, "UPDATE sync_event SET received_at = now() - interval '90 seconds'")
    with app_factory() as session:
        session.add(SyncEvent(source="poll"))
        session.commit()
    sql(
        app_factory,
        "INSERT INTO worker_heartbeat VALUES ('w1', now() - interval '7 seconds', 'p'), ('w2', now() - interval '40 seconds', 'p')",
    )
    body = health(client)
    assert 89 <= body["last_webhook_age_seconds"] <= 95
    assert body["poll_fallbacks_24h"] == 1
    assert 6 <= body["last_drain_age_seconds"] <= 12  # the freshest worker counts


def test_f21_fr04_the_status_events_carry_attempts_objects_and_pass(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    queue(app_factory, "run-A")
    drain_once(app_factory, FakeReader(published("run-A")), "pass-9")
    [row] = client.get("/api/sync/status").json()["events"]
    assert (row["attempts"], row["objects_synced"], row["drain_pass_id"]) == (1, len(MIRROR_TABLES), "pass-9")


class FakeScenario:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.fail = fail

    def post(self, url: str, headers: dict[str, str], timeout: float) -> httpx.Response:
        self.calls.append((url, headers))
        request = httpx.Request("POST", url)
        if self.fail:
            return httpx.Response(503, request=request)
        return httpx.Response(200, json={"run_id": "dagster-run-1", "status": "STARTED"}, request=request)


@pytest.fixture
def scenario(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeScenario]:
    fake = FakeScenario()
    monkeypatch.setattr("app_api.routers.webhooks.httpx.post", fake.post)
    monkeypatch.setenv("SCENARIO_URL", "http://scenario.test")
    monkeypatch.setenv("SCENARIO_TOKEN", "t0ken")
    yield fake


def test_f21_fr05_admin_run_pipeline_proxies_to_the_scenario_service_and_audits(
    client: TestClient, app_factory: sessionmaker[Session], scenario: FakeScenario
) -> None:
    response = client.post("/api/sync/run-pipeline", headers=ADMIN)
    assert response.status_code == 202
    assert response.json() == {"run_id": "dagster-run-1", "status": "STARTED"}
    assert scenario.calls == [("http://scenario.test/pipeline/run", {"X-Scenario-Token": "t0ken"})]
    with app_factory() as session:
        audit = session.execute(text("SELECT action, actor_user_key, details_json FROM audit_event")).one()
    assert (audit[0], audit[1], audit[2]) == (
        "pipeline_triggered",
        "admin",
        {"pipeline_run_id": "dagster-run-1"},
    )


@pytest.mark.parametrize(("user", "expected"), [("pat", 403), ("sam", 403), ("quinn", 403), ("nobody", 401)])
def test_f21_fr05_only_admin_may_run_the_pipeline(
    client: TestClient, app_factory: sessionmaker[Session], scenario: FakeScenario, user: str, expected: int
) -> None:
    assert client.post("/api/sync/run-pipeline", headers={"X-Demo-User": user}).status_code == expected
    assert scenario.calls == []


def test_f21_fr05_a_scenario_failure_is_a_502_and_leaves_no_audit_row(
    client: TestClient, app_factory: sessionmaker[Session], scenario: FakeScenario
) -> None:
    scenario.fail = True
    assert client.post("/api/sync/run-pipeline", headers=ADMIN).status_code == 502
    with app_factory() as session:
        assert session.execute(text("SELECT count(*) FROM audit_event")).scalar_one() == 0
