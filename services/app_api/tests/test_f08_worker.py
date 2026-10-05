"""F08-FR-06, FR-08: the worker loop, structured logs and the read-only lakehouse mount."""

import json
import logging
import threading
from pathlib import Path
from typing import Any

import pytest
import yaml
from app_api.logs import JsonFormatter, bind
from app_api.models import SyncEvent
from app_api.sync.drain import drain_once
from app_api.worker import run_forever
from sqlalchemy.orm import Session, sessionmaker
from support import FakeReader, published

COMPOSE = yaml.safe_load((Path(__file__).parents[3] / "docker-compose.yml").read_text())


def test_f08_fr08_json_formatter_emits_service_event_and_run_ids() -> None:
    formatter = JsonFormatter("app-worker")
    record = logging.LogRecord("app_api.sync", logging.INFO, __file__, 1, "contract_pulled", None, None)
    record.duration_ms = 12.5
    with bind(event_id=7, run_id="run-A"):
        line = json.loads(formatter.format(record))
    assert line["service"] == "app-worker"
    assert line["message"] == "contract_pulled"
    assert line["level"] == "INFO"
    assert (line["event_id"], line["run_id"], line["duration_ms"]) == (7, "run-A", 12.5)
    assert "event_id" not in json.loads(formatter.format(record))  # the binding ends with the block


def test_f08_fr06_only_the_worker_mounts_the_lakehouse_read_only() -> None:
    services: dict[str, Any] = COMPOSE["services"]
    mounts = {
        name: [v for v in service.get("volumes", []) if "/lakehouse" in str(v)]
        for name, service in services.items()
    }
    assert mounts["app-worker"] and all(str(v).endswith(":ro") for v in mounts["app-worker"])
    assert not mounts["app-api"]
    writers = {
        name for name, found in mounts.items() if found and not all(str(v).endswith(":ro") for v in found)
    }
    assert writers == {"dagster-web", "dagster-daemon"}


def test_f08_fr06_the_worker_runs_from_the_app_image_with_its_own_command() -> None:
    services: dict[str, Any] = COMPOSE["services"]
    assert services["app-worker"]["image"] == services["app-api"]["image"]
    assert services["app-worker"]["command"] == ["python", "-m", "app_api.worker"]


@pytest.mark.integration
def test_f08_fr08_claim_pull_and_upsert_are_logged_with_event_run_and_duration(
    app_factory: sessionmaker[Session],
) -> None:
    lines: list[str] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            lines.append(self.format(record))

    handler = Capture()
    handler.setFormatter(JsonFormatter("app-worker"))
    logger = logging.getLogger("app_api")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    with app_factory() as session:
        event = SyncEvent(source="webhook", run_id="run-A")
        session.add(event)
        session.commit()
        event_id = event.id
    try:
        drain_once(app_factory, FakeReader(published("run-A")))
    finally:
        logger.removeHandler(handler)
    by_message = {line["message"]: line for line in map(json.loads, lines)}
    assert {"event_claimed", "contract_pulled", "mirror_upserted", "event_done"} <= set(by_message)
    for message in ("contract_pulled", "mirror_upserted", "event_done"):
        line = by_message[message]
        assert (line["service"], line["event_id"], line["run_id"]) == ("app-worker", event_id, "run-A")
        assert line["duration_ms"] >= 0


@pytest.mark.integration
def test_f08_fr04_the_worker_loop_drains_on_every_pass_and_stops_when_asked(
    app_factory: sessionmaker[Session],
) -> None:
    stop = threading.Event()
    passes: list[int] = []

    def sleep(seconds: float) -> None:
        passes.append(int(seconds))
        if len(passes) == 1:  # an event that arrives while the worker sleeps
            with app_factory() as session:
                session.add(SyncEvent(source="manual"))
                session.commit()
        else:
            stop.set()

    with app_factory() as session:
        session.add(SyncEvent(source="manual"))
        session.commit()
    run_forever(app_factory, FakeReader(published("run-A")), interval_seconds=20, stop=stop, sleep=sleep)
    assert passes == [20, 20]
    with app_factory() as session:
        statuses = [e.status for e in session.query(SyncEvent)]
    assert statuses == ["done", "done"]
