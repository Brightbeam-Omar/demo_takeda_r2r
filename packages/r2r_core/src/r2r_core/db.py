"""Database helpers shared by the source simulators and the app (F04).

* ``postgres_dsn``: a DSN for one of the databases on the shared Postgres server.
* ``TimestampMixin`` and ``make_session_factory``: every row gets ``updated_at`` from the **demo clock**
  (``r2r_core.clock.now()``), set in service code on each insert and update, never by a DB trigger. All rows
  written through one session get the same timestamp.
* ``CounterMixin`` and ``allocate_number``: per-database counters for document, lot, sample and deviation
  numbers, so a reset restarts numbering deterministically.
* ``upgrade`` and ``run_migrations_env``: a small Alembic runner used by each service's ``migrations``.
"""

import os
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from alembic import command
from alembic.config import Config
from sqlalchemy import DateTime, Engine, create_engine, event
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from r2r_core import clock


class TimestampMixin:
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class CounterMixin(TimestampMixin):
    """Columns of a ``counter`` table: one row per sequence name."""

    name: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[int] = mapped_column(default=0)


def postgres_dsn(database: str, env: Mapping[str, str] | None = None, driver: str | None = "psycopg") -> str:
    """DSN for ``database`` on the shared server, built from ``POSTGRES_*`` (SQLAlchemy driver by default)."""
    source = os.environ if env is None else env
    user = quote(source.get("POSTGRES_USER", "r2r"), safe="")
    password = quote(source.get("POSTGRES_PASSWORD", "r2r_dev_only"), safe="")
    host = source.get("POSTGRES_HOST", "postgres")
    port = source.get("POSTGRES_PORT", "5432")
    scheme = "postgresql" if driver is None else f"postgresql+{driver}"
    return f"{scheme}://{user}:{password}@{host}:{port}/{database}"


def make_engine(dsn: str) -> Engine:
    return create_engine(dsn, pool_pre_ping=True)


def stamp[T: TimestampMixin](obj: T) -> T:
    """Set ``updated_at`` to the demo clock's now and return the object."""
    obj.updated_at = clock.now()
    return obj


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Sessions that stamp ``updated_at`` on every new or modified row (one timestamp per session)."""
    factory = sessionmaker(engine, expire_on_commit=False)

    @event.listens_for(factory, "before_flush")
    def _stamp(session: Session, flush_context: object, instances: object) -> None:
        now = session.info.setdefault("stamp_now", clock.now())
        for obj in list(session.new) + list(session.dirty):
            if isinstance(obj, TimestampMixin) and (obj in session.new or session.is_modified(obj)):
                obj.updated_at = now

    return factory


def allocate_number(
    session: Session,
    counter_model: type[CounterMixin],
    name: str,
    fmt: Callable[[int], str],
    exists: Callable[[str], bool] | None = None,
) -> str:
    """Next number of sequence ``name`` formatted by ``fmt``, skipping numbers for which ``exists`` holds."""
    row = session.get(counter_model, name, with_for_update=True)
    if row is None:
        row = counter_model()
        row.name, row.value = name, 0
        session.add(row)
    while True:
        row.value += 1
        number = fmt(row.value)
        if exists is None or not exists(number):
            return number


def upgrade(script_location: str | Path, dsn: str) -> None:
    """Run ``alembic upgrade head`` for a migrations directory against ``dsn``."""
    config = Config()
    config.set_main_option("script_location", str(script_location))
    config.set_main_option("sqlalchemy.url", dsn.replace("%", "%%"))
    command.upgrade(config, "head")


def run_migrations_env(context: Any, metadata: Any) -> None:
    """Body of a service's Alembic ``env.py`` (online mode only)."""
    if context.is_offline_mode():
        raise RuntimeError("offline migrations are not supported")
    engine = create_engine(context.config.get_main_option("sqlalchemy.url"))
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
