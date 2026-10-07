"""Fixtures for the agents tests: a migrated throwaway ``app`` database, opened as the restricted role."""

import sys
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from agents.db import DEFAULT_PASSWORD, ROLE
from app_api.db import migrate
from fastapi import FastAPI
from fastapi.testclient import TestClient
from r2r_core import clock
from r2r_core.clock import FixedClock
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).parent))  # lets tests import agent_support


@pytest.fixture(scope="session")
def owner_dsn(make_test_database: Callable[[str], str]) -> str:
    dsn = make_test_database("agents_app")
    migrate(dsn)
    return dsn


@pytest.fixture(scope="session")
def agents_dsn_test(owner_dsn: str) -> str:
    return (
        make_url(owner_dsn)
        .set(username=ROLE, password=DEFAULT_PASSWORD)
        .render_as_string(hide_password=False)
    )


@pytest.fixture(scope="session")
def owner_engine(owner_dsn: str) -> Iterator[Engine]:
    engine = create_engine(owner_dsn)
    yield engine
    engine.dispose()


@pytest.fixture
def agents_engine(agents_dsn_test: str, owner_engine: Engine) -> Iterator[Engine]:
    """Empty agent tables, then an engine connected as ``agents_rw``."""
    with owner_engine.begin() as connection:
        connection.execute(text("TRUNCATE action_log, proposal, agent_trace, audit_event RESTART IDENTITY"))
    engine = create_engine(agents_dsn_test)
    yield engine
    engine.dispose()


@pytest.fixture
def make_client(agents_engine: Engine) -> Callable[[], TestClient]:
    from agents.main import create_app
    from agents.settings import Settings

    def build() -> TestClient:
        from agent_support import fake_app_api

        app: FastAPI = create_app(Settings.from_env({}), agents_engine, fake_app_api())
        return TestClient(app)

    return build


DEMO_NOW = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def fixed_clock() -> Iterator[None]:
    """Every test runs at the canonical demo-start instant; nothing reads the wall clock or a database."""
    clock.set_clock_source(FixedClock(DEMO_NOW))
    yield
    clock.set_clock_source(None)
