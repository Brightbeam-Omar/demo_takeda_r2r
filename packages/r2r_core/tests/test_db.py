"""T1: database helpers [F04 plan]: DSNs, timestamp stamping, counters.

Uses in-memory SQLite, so it runs in `make check`. SQLite drops time zones on read, hence the
`as_utc` helper in the assertions.
"""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from r2r_core import clock
from r2r_core.clock import FixedClock
from r2r_core.db import (
    CounterMixin,
    TimestampMixin,
    allocate_number,
    make_session_factory,
    postgres_dsn,
    stamp,
)
from r2r_core.errors import Conflict
from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Thing(TimestampMixin, Base):
    __tablename__ = "thing"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(default="")


class Counter(CounterMixin, Base):
    __tablename__ = "counter"


T1 = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)
T2 = datetime(2026, 10, 13, 7, 0, tzinfo=UTC)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@pytest.fixture(autouse=True)
def _reset_clock() -> Iterator[None]:
    yield
    clock.set_clock_source(None)


@pytest.fixture
def factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


def test_f04_fr02_stamp_uses_the_demo_clock() -> None:
    clock.set_clock_source(FixedClock(T1))
    thing = stamp(Thing(id=1))
    assert thing.updated_at == T1


def test_f04_fr02_session_stamps_inserts_and_updates_with_the_demo_clock(
    factory: sessionmaker[Session],
) -> None:
    clock.set_clock_source(FixedClock(T1))
    with factory() as session:
        session.add(Thing(id=1, label="a"))
        session.commit()
    clock.set_clock_source(FixedClock(T2))
    with factory() as session:
        thing = session.get(Thing, 1)
        assert thing is not None
        assert as_utc(thing.updated_at) == T1
        thing.label = "b"
        session.commit()
    with factory() as session:
        thing = session.get(Thing, 1)
        assert thing is not None
        assert as_utc(thing.updated_at) == T2


def test_f04_fr02_an_untouched_row_keeps_its_timestamp(factory: sessionmaker[Session]) -> None:
    clock.set_clock_source(FixedClock(T1))
    with factory() as session:
        session.add(Thing(id=1))
        session.commit()
    clock.set_clock_source(FixedClock(T2))
    with factory() as session:
        thing = session.get(Thing, 1)
        assert thing is not None
        thing.label = thing.label  # assigned, but unchanged
        session.commit()
        assert as_utc(thing.updated_at) == T1


def test_f04_fr02_all_rows_of_one_event_share_one_timestamp(factory: sessionmaker[Session]) -> None:
    class Ticking:
        def __init__(self) -> None:
            self.calls = 0

        def now(self) -> datetime:
            self.calls += 1
            return T1.replace(minute=self.calls)

    clock.set_clock_source(Ticking())
    with factory() as session:
        session.add(Thing(id=1))
        session.flush()
        session.add(Thing(id=2))
        session.commit()
        stamps = {as_utc(t.updated_at) for t in session.scalars(select(Thing))}
    assert len(stamps) == 1


def test_f04_fr10_allocate_number_counts_up_and_formats(factory: sessionmaker[Session]) -> None:
    clock.set_clock_source(FixedClock(T1))
    with factory() as session:
        first = allocate_number(session, Counter, "sample", lambda n: f"S-{n:07d}")
        second = allocate_number(session, Counter, "sample", lambda n: f"S-{n:07d}")
        other = allocate_number(session, Counter, "lot", lambda n: f"{10000000 + n}")
        session.commit()
    assert (first, second, other) == ("S-0000001", "S-0000002", "10000001")


def test_f04_fr10_allocate_number_skips_numbers_already_in_use(factory: sessionmaker[Session]) -> None:
    clock.set_clock_source(FixedClock(T1))
    taken = {"S-0000001", "S-0000002"}
    with factory() as session:
        number = allocate_number(
            session, Counter, "sample", lambda n: f"S-{n:07d}", exists=taken.__contains__
        )
        session.commit()
    assert number == "S-0000003"


def test_f04_fr10_conflict_is_a_plain_exception_with_a_message() -> None:
    assert str(Conflict("lot 10000001 already exists")) == "lot 10000001 already exists"


def test_f04_fr09_postgres_dsn_is_built_from_the_environment_and_quotes_the_password() -> None:
    env = {
        "POSTGRES_USER": "u",
        "POSTGRES_PASSWORD": "p@ss/word",
        "POSTGRES_HOST": "db",
        "POSTGRES_PORT": "5433",
    }
    assert postgres_dsn("erp_sim", env) == "postgresql+psycopg://u:p%40ss%2Fword@db:5433/erp_sim"
    assert postgres_dsn("app", {}) == "postgresql+psycopg://r2r:r2r_dev_only@postgres:5432/app"
    assert postgres_dsn("app", env, driver=None) == "postgresql://u:p%40ss%2Fword@db:5433/app"


def test_f04_fr09_session_factory_is_bound_to_the_engine(factory: sessionmaker[Session]) -> None:
    with factory() as session:
        assert isinstance(session, Session)


def test_f04_fr10_a_reused_session_restamps_after_each_commit_and_rollback(
    factory: sessionmaker[Session],
) -> None:
    """The generator reuses one session across simulated days: each transaction takes the clock afresh."""
    clock.set_clock_source(FixedClock(T1))
    with factory() as session:
        session.add(Thing(id=1))
        session.commit()
        clock.set_clock_source(FixedClock(T2))
        session.add(Thing(id=2))
        session.commit()
        session.add(Thing(id=3))
        session.flush()
        session.rollback()
        clock.set_clock_source(FixedClock(T1.replace(day=20)))
        session.add(Thing(id=4))
        session.commit()
        stamps = {t.id: as_utc(t.updated_at) for t in session.scalars(select(Thing))}
    assert stamps == {1: T1, 2: T2, 4: T1.replace(day=20)}
