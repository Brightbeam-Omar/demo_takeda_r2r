"""Repo-wide pytest fixtures: throwaway Postgres databases for `integration` tests.

Each test session creates its own databases (named after the process id) on the compose Postgres, so
tests never touch the data of a running stack. Connection settings come from the same variables as the
services (``POSTGRES_*``), with ``R2R_TEST_PG_HOST`` (default ``localhost``) for the host.
"""

import os
from collections.abc import Callable, Iterator

import pytest


def _setting(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _conninfo(database: str, driver: str | None) -> str:
    user = _setting("POSTGRES_USER", "r2r")
    password = _setting("POSTGRES_PASSWORD", "r2r_dev_only")
    host = _setting("R2R_TEST_PG_HOST", "localhost")
    port = _setting("POSTGRES_PORT", "5432")
    scheme = "postgresql" if driver is None else f"postgresql+{driver}"
    return f"{scheme}://{user}:{password}@{host}:{port}/{database}"


@pytest.fixture(scope="session")
def make_test_database() -> Iterator[Callable[[str], str]]:
    """Factory: ``make_test_database("erp_sim")`` creates an empty database and returns its SQLAlchemy DSN."""
    import psycopg

    created: list[str] = []

    def create(base: str) -> str:
        name = f"{base}_test_{os.getpid()}"
        with psycopg.connect(_conninfo("postgres", None), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
            admin.execute(f'CREATE DATABASE "{name}"')
        created.append(name)
        return _conninfo(name, "psycopg")

    yield create

    with psycopg.connect(_conninfo("postgres", None), autocommit=True) as admin:
        for name in created:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
