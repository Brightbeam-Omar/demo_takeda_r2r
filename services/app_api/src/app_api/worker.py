"""``python -m app_api.worker``: the drain loop (F08-FR-04). The only code path that reads the lakehouse."""

import logging
import os
import threading
import time
from collections.abc import Callable

from r2r_core.contract import ContractReader, DeltaContractReader
from sqlalchemy.orm import Session, sessionmaker

from app_api.db import session_factory
from app_api.logs import configure_logging
from app_api.sync.drain import drain_once

log = logging.getLogger(__name__)
DEFAULT_INTERVAL_SECONDS = 20


def run_forever(
    factory: sessionmaker[Session],
    reader: ContractReader,
    interval_seconds: float,
    stop: threading.Event,
    sleep: Callable[[float], object] | None = None,
) -> None:
    """Drain, wait, repeat until ``stop`` is set. A failed pass is logged and the loop carries on."""
    wait = sleep or stop.wait  # wall-clock waiting is infrastructure timing (OQ-003)
    while not stop.is_set():
        try:
            drain_once(factory, reader)
        except Exception:
            log.exception("drain_failed")
        wait(interval_seconds)


def main() -> None:
    configure_logging("app-worker")
    interval = float(os.environ.get("DRAIN_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS))
    reader = DeltaContractReader(os.environ.get("LAKEHOUSE_PATH", "/lakehouse"))
    log.info("worker_started", extra={"interval_seconds": interval})
    run_forever(session_factory(), reader, interval, threading.Event(), sleep=time.sleep)


if __name__ == "__main__":
    main()
