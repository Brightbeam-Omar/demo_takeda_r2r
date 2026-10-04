"""Fixtures for the LIMS simulator's database tests."""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import pytest
from lims_sim.db import migrate
from lims_sim.models import Base
from r2r_core import clock
from r2r_core.clock import FixedClock
from r2r_core.db import make_engine, make_session_factory
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

DEMO_NOW = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)


@pytest.fixture(scope="session")
def lims_engine(make_test_database: Callable[[str], str]) -> Iterator[Engine]:
    dsn = make_test_database("lims_events")
    migrate(dsn)
    engine = make_engine(dsn)
    yield engine
    engine.dispose()


@pytest.fixture
def factory(lims_engine: Engine) -> Iterator[sessionmaker[Session]]:
    clock.set_clock_source(FixedClock(DEMO_NOW))
    with lims_engine.begin() as connection:
        names = ", ".join(table.name for table in Base.metadata.sorted_tables)
        connection.execute(text(f"TRUNCATE {names} CASCADE"))
    yield make_session_factory(lims_engine)
    clock.set_clock_source(None)
