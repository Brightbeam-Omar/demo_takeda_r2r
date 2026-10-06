"""F08-FR-03, FR-07, FR-11: the manual trigger, the status endpoint and the minimal demo-user check."""

from datetime import timedelta
from typing import Any

import pytest
from app_api.sync.drain import drain_once
from fastapi.testclient import TestClient
from r2r_core import clock
from r2r_core.clock import FixedClock
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from support import STAMP, FakeReader, published, queue

pytestmark = pytest.mark.integration


def events(factory: sessionmaker[Session]) -> list[Any]:
    with factory() as session:
        return list(session.execute(text("SELECT source, status, run_id FROM sync_event ORDER BY id")).all())


def test_f08_fr03_admin_trigger_queues_a_manual_event(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    response = client.post("/api/sync/trigger", headers={"X-Demo-User": "admin"})
    assert response.status_code == 202
    assert [tuple(e) for e in events(app_factory)] == [("manual", "pending", None)]
    assert response.json()["event_id"] == 1
    with app_factory() as session:
        audit = session.execute(text("SELECT action, actor_user_key FROM audit_event")).one()
    assert tuple(audit) == ("sync_triggered", "admin")


@pytest.mark.parametrize(
    ("user", "expected"), [("pat", 403), ("sam", 403), ("quinn", 403), ("nobody", 401), (None, 403)]
)
def test_f08_fr03_only_admin_may_trigger(
    client: TestClient, app_factory: sessionmaker[Session], user: str | None, expected: int
) -> None:
    headers = {} if user is None else {"X-Demo-User": user}
    assert client.post("/api/sync/trigger", headers=headers).status_code == expected
    assert events(app_factory) == []


def test_f08_fr03_the_demo_user_header_is_ignored_outside_demo_mode(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    assert client.post("/api/sync/trigger", headers={"X-Demo-User": "admin"}).status_code == 401


def test_f08_fr07_status_before_anything_was_synced(client: TestClient) -> None:
    body = client.get("/api/sync/status").json()
    assert body["events"] == []
    assert body["watermarks"] == []
    assert body["pipeline_status"] is None
    assert body["freshness_minutes"] is None


def test_f08_fr07_status_lists_the_last_50_events_newest_first(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    for number in range(55):
        queue(app_factory, f"run-{number}")
    body = client.get("/api/sync/status").json()
    assert len(body["events"]) == 50
    assert body["events"][0]["run_id"] == "run-54"
    assert body["events"][-1]["run_id"] == "run-5"


def test_f08_fr07_and_fr11_events_carry_iso_times_age_and_duration(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    queue(app_factory, "run-A")
    drain_once(app_factory, FakeReader(published("run-A")))
    with app_factory() as session:  # make the times deterministic: received 2 min ago, took 1.4 s
        session.execute(
            text("UPDATE sync_event SET received_at = now() - interval '120 seconds', "
                 "claimed_at = now() - interval '100 seconds', finished_at = now() - interval '98.6 seconds'")
        )  # fmt: skip
        session.commit()
    [event] = client.get("/api/sync/status").json()["events"]
    assert event["status"] == "done"
    assert event["source"] == "webhook"
    assert event["rows_upserted"] == 22
    assert event["duration_ms"] == 1400
    assert 119 <= event["age_seconds"] <= 125
    for field in ("received_at", "claimed_at", "finished_at"):
        assert "T" in event[field]  # ISO 8601


def test_f08_fr07_an_unfinished_event_has_no_duration(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    queue(app_factory, "run-A")
    [event] = client.get("/api/sync/status").json()["events"]
    assert event["duration_ms"] is None
    assert event["status"] == "pending"


def test_f08_fr07_status_shows_watermarks_and_the_pipeline_status_after_a_sync(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    queue(app_factory, "run-A")
    drain_once(app_factory, FakeReader(published("run-A")))
    body = client.get("/api/sync/status").json()
    assert {w["object_name"] for w in body["watermarks"]} == {
        "batch_pipeline_v", "weekly_metrics_v", "weekly_metric_rows_v", "stage_reference_v",
        "metric_reference_v", "reason_codes_v", "deviations_v", "expected_deliveries_v", "pipeline_status_v",
    }  # fmt: skip
    assert {w["run_id"] for w in body["watermarks"]} == {"run-A"}
    assert all(w["age_seconds"] >= 0 for w in body["watermarks"])
    status = body["pipeline_status"]
    assert status["last_run_id"] == "run-A"
    assert status["row_count"] == 0
    assert status["source_freshness"] == {"n": 0}
    assert status["last_success_at"].startswith("2026-10-12T07:00:00")


def test_f08_fr07_freshness_minutes_uses_the_demo_clock(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    queue(app_factory, "run-A")
    drain_once(app_factory, FakeReader(published("run-A")))
    clock.set_clock_source(FixedClock(STAMP + timedelta(minutes=95, seconds=30)))
    assert client.get("/api/sync/status").json()["freshness_minutes"] == 95
    clock.set_clock_source(
        FixedClock(STAMP - timedelta(hours=1))
    )  # a clock set back never gives a negative age
    assert client.get("/api/sync/status").json()["freshness_minutes"] == 0
