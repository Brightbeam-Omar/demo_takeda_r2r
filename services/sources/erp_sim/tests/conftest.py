"""Fixtures for the ERP simulator's database tests."""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import pytest
from erp_sim.db import migrate
from erp_sim.models import Base, Lfa1, Mara, T001l
from r2r_core import clock
from r2r_core.clock import FixedClock
from r2r_core.db import make_engine, make_session_factory
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

DEMO_NOW = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)


@pytest.fixture(scope="session")
def erp_engine(make_test_database: Callable[[str], str]) -> Iterator[Engine]:
    dsn = make_test_database("erp_events")
    migrate(dsn)
    engine = make_engine(dsn)
    yield engine
    engine.dispose()


@pytest.fixture
def factory(erp_engine: Engine) -> Iterator[sessionmaker[Session]]:
    """Empty tables with master data (one material, one supplier, three locations) before each test."""
    clock.set_clock_source(FixedClock(DEMO_NOW))
    with erp_engine.begin() as connection:
        names = ", ".join(table.name for table in Base.metadata.sorted_tables)
        connection.execute(text(f"TRUNCATE {names} CASCADE"))
    factory = make_session_factory(erp_engine)
    with factory() as session:
        session.add_all(
            [
                Mara(
                    matnr="RM10001",
                    maktx="Excipient 001",
                    mtart="ROH",
                    zmolty="small_molecule",
                    zclass="consumable",
                ),
                Lfa1(lifnr="SUP001", name1="Supplier 001", land1="IE"),
                T001l(lgort="0100", lgobe="Main warehouse", zloctype="onsite"),
                T001l(lgort="0200", lgobe="3PL North", zloctype="3pl"),
                T001l(lgort="0300", lgobe="QC sampling room", zloctype="onsite"),
            ]
        )
        session.commit()
    yield factory
    clock.set_clock_source(None)
