"""Database wiring for the ERP simulator."""

import functools
import os
from collections.abc import Iterator
from pathlib import Path

from r2r_core.db import make_engine, make_session_factory, postgres_dsn, upgrade
from sqlalchemy.orm import Session, sessionmaker

DATABASE = "erp_sim"
MIGRATIONS = Path(__file__).parent / "migrations"


def dsn() -> str:
    return os.environ.get("ERP_SIM_DSN") or postgres_dsn(DATABASE)


@functools.cache
def _factory() -> sessionmaker[Session]:
    return make_session_factory(make_engine(dsn()))


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request; commit on success, roll back on any error."""
    with _factory()() as session:
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise


def migrate(database_dsn: str | None = None) -> None:
    upgrade(MIGRATIONS, database_dsn or dsn())
