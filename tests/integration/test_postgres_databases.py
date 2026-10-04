"""Integration: the compose Postgres creates the five R2R databases [F01-AC-01].

Needs a running Postgres (``make up`` locally, or the CI integration job's service container).
Skipped by ``make check``; run with ``uv run pytest tests/integration -m integration``.
Connects from the host, so the host defaults to localhost (``postgres`` only resolves inside compose).
"""

import os

import psycopg
import pytest

EXPECTED = {"erp_sim", "lims_sim", "qms_sim", "app", "dagster"}


@pytest.mark.integration
def test_f01_ac01_five_databases_exist() -> None:
    conn = psycopg.connect(
        host=os.environ.get("R2R_TEST_PG_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ.get("POSTGRES_USER", "r2r"),
        password=os.environ.get("POSTGRES_PASSWORD", "r2r_dev_only"),
        dbname="postgres",
    )
    with conn, conn.cursor() as cur:
        cur.execute("SELECT datname FROM pg_database")
        names = {row[0] for row in cur.fetchall()}
    assert names >= EXPECTED
