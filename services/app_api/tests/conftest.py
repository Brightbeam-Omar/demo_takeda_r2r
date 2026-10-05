"""Fixtures for the app API tests: a migrated throwaway ``app`` database and a client wired to it."""

import sys
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app_api.db import get_session, migrate
from app_api.main import create_app
from app_api.services import store
from fastapi.testclient import TestClient
from r2r_core import clock
from r2r_core.clock import FixedClock
from r2r_core.db import make_engine, make_session_factory
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).parent))  # lets tests import support

DEMO_NOW = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)


@pytest.fixture(scope="session")
def app_dsn(make_test_database: Callable[[str], str]) -> str:
    dsn = make_test_database("app_sync")
    migrate(dsn)
    return dsn


@pytest.fixture(scope="session")
def app_engine(app_dsn: str) -> Iterator[Engine]:
    engine = make_engine(app_dsn)
    yield engine
    engine.dispose()


@pytest.fixture
def app_factory(app_engine: Engine) -> Iterator[sessionmaker[Session]]:
    """Empty sync, mirror and audit tables (users stay seeded) and a fixed demo clock."""
    clock.set_clock_source(FixedClock(DEMO_NOW))
    store.clear_cache()
    with app_engine.begin() as connection:
        connection.execute(
            text("TRUNCATE sync_event, watermark, audit_event, feedback, bookmark, filter_preset, override_value, comment, mirror_batch_pipeline, mirror_weekly_metrics, "
                 "mirror_weekly_metric_rows, mirror_pipeline_status, mirror_stage_reference, "
                 "mirror_metric_reference, mirror_reason_codes, mirror_deviations RESTART IDENTITY")
        )  # fmt: skip
    yield make_session_factory(app_engine)
    clock.set_clock_source(None)


@pytest.fixture
def client(app_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DEMO_MODE", "true")
    app = create_app()

    def session() -> Iterator[Session]:
        with app_factory() as db:
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    app.dependency_overrides[get_session] = session
    with TestClient(app) as test_client:
        yield test_client
