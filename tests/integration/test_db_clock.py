"""Integration: DbClock against a real Postgres [F03-FR-03].

Creates its own table in a scratch schema (F04 owns the real ``demo_clock``), so it never touches
shared state. Needs the CI integration job's Postgres, or ``make up``.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import psycopg
import pytest
from r2r_core.clock import DbClock

SCHEMA = "r2r_clock_test"


def _conninfo(**extra: str) -> str:
    host = os.environ.get("R2R_TEST_PG_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "r2r")
    password = os.environ.get("POSTGRES_PASSWORD", "r2r_dev_only")
    base = f"postgresql://{user}:{password}@{host}:{port}/app"
    return base + (("?" + "&".join(f"{k}={v}" for k, v in extra.items())) if extra else "")


@pytest.fixture
def scratch_schema() -> Iterator[None]:
    with psycopg.connect(_conninfo(), autocommit=True) as conn:
        conn.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
        conn.execute(f"CREATE SCHEMA {SCHEMA}")
        conn.execute(
            f"CREATE TABLE {SCHEMA}.demo_clock (id int PRIMARY KEY, now_utc timestamptz NOT NULL, "
            "frozen boolean NOT NULL DEFAULT false)"
        )
        conn.execute(f"INSERT INTO {SCHEMA}.demo_clock (id, now_utc) VALUES (1, '2026-10-12T07:00:00+00')")
        yield
        conn.execute(f"DROP SCHEMA {SCHEMA} CASCADE")


@pytest.mark.integration
def test_f03_fr03_db_clock_reads_a_real_demo_clock_table(scratch_schema: None) -> None:
    dsn = _conninfo(options=f"-csearch_path%3D{SCHEMA}")
    assert DbClock(dsn).now() == datetime(2026, 10, 12, 7, 0, tzinfo=UTC)
