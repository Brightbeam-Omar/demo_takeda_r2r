"""Database wiring for the application (the `app` database)."""

import functools
import os
from collections.abc import Iterator
from pathlib import Path

from r2r_core.db import make_engine, make_session_factory, postgres_dsn, upgrade
from sqlalchemy.orm import Session, sessionmaker

DATABASE = "app"
MIGRATIONS = Path(__file__).parent / "migrations"


def dsn() -> str:
    return os.environ.get("APP_DSN") or postgres_dsn(DATABASE)


@functools.cache
def session_factory() -> sessionmaker[Session]:
    return make_session_factory(make_engine(dsn()))


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request; commit on success, roll back on any error."""
    with session_factory()() as session:
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise


def migrate(database_dsn: str | None = None) -> None:
    upgrade(MIGRATIONS, database_dsn or dsn())
