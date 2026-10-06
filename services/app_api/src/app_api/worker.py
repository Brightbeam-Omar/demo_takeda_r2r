"""``python -m app_api.worker``: the drain loop (F08-FR-04). The only code path that reads the lakehouse."""

import logging
import os
import socket
import threading
import time
from collections.abc import Callable

from r2r_core.contract import ContractReader, DeltaContractReader
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app_api.db import session_factory
from app_api.logs import configure_logging
from app_api.sync.drain import drain_once, new_pass_id

log = logging.getLogger("app_api.worker")  # not __name__: under `python -m` that is "__main__"
DEFAULT_INTERVAL_SECONDS = 20
WAKE_SECONDS = 2  # how often the loop looks for pending events and beats (F21-FR-04, OQ-131)

_BEAT = text(
    """
    INSERT INTO worker_heartbeat (worker_id, last_loop_at, last_pass_id) VALUES (:worker, now(), :pass_id)
    ON CONFLICT (worker_id) DO UPDATE SET last_loop_at = now(), last_pass_id = :pass_id
    """
)


def beat(factory: sessionmaker[Session], worker_id: str, pass_id: str) -> None:
    """Record that the loop is alive: the Webhook Sync Status page reads "Last Drain" from here."""
    with factory() as session:
        session.execute(_BEAT, {"worker": worker_id, "pass_id": pass_id})
        session.commit()


def run_forever(
    factory: sessionmaker[Session],
    reader: ContractReader,
    interval_seconds: float,
    stop: threading.Event,
    sleep: Callable[[float], object] | None = None,
    wake_seconds: float = WAKE_SECONDS,
    monotonic: Callable[[], float] = time.monotonic,
    worker_id: str | None = None,
) -> None:
    """Wake every ``wake_seconds``; run a full pass every ``interval_seconds``, until ``stop`` is set.

    Every wake beats the heartbeat and drains the pending events, so a manual or webhook event waits two
    seconds at most. A full pass also takes back claims that went stale (a crashed worker). A failed pass is
    logged and the loop carries on (OQ-131).
    """
    wait = sleep or stop.wait  # wall-clock waiting is infrastructure timing (OQ-003)
    worker = worker_id or socket.gethostname()
    last_full: float | None = None
    while not stop.is_set():
        pass_id = new_pass_id()
        now = monotonic()
        full = last_full is None or now - last_full >= interval_seconds
        if full:
            last_full = now
        try:
            beat(factory, worker, pass_id)
            drain_once(factory, reader, pass_id, include_stale=full)
        except Exception:
            log.exception("drain_failed")
        wait(wake_seconds)


def main() -> None:
    configure_logging("app-worker")
    interval = float(os.environ.get("DRAIN_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS))
    reader = DeltaContractReader(os.environ.get("LAKEHOUSE_PATH", "/lakehouse"))
    log.info("worker_started", extra={"interval_seconds": interval, "wake_seconds": WAKE_SECONDS})
    run_forever(session_factory(), reader, interval, threading.Event(), sleep=time.sleep)


if __name__ == "__main__":
    main()
