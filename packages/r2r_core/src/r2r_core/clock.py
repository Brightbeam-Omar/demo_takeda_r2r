"""The demo clock. All "now" in the system comes from here, never from the wall clock (constitution).

The clock moves only when the scenario service sets or advances it. Sources:

* ``FixedClock``: a fixed instant, for tests.
* ``DbClock``: reads ``demo_clock`` (id = 1) from the ``app`` database.
* ``HttpClock``: asks the scenario service (``GET /clock``), caches for 1 s, falls back to a ``DbClock``.

The default source comes from env ``CLOCK_SOURCE=http|db|fixed`` (default ``http``). This module is the
one place the wall-clock guard allows; it does not need to read the real time at all.
"""

import functools
import os
import time
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from typing import Any, Protocol
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
import psycopg

from r2r_core.profile import ProfileError, load_profile


class ClockError(Exception):
    """The demo clock could not be read or configured."""


class ClockSource(Protocol):
    def now(self) -> datetime: ...


def _as_utc(value: datetime) -> datetime:
    """Aware datetimes convert to UTC; naive ones are taken to be UTC already."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class FixedClock:
    def __init__(self, instant: datetime) -> None:
        if instant.tzinfo is None:
            raise ValueError("FixedClock needs a timezone-aware datetime")
        self._instant = instant.astimezone(UTC)

    def now(self) -> datetime:
        return self._instant


class DbClock:
    def __init__(self, dsn: str, connect: Callable[[str], Any] | None = None) -> None:
        self.dsn = dsn
        self._connect = connect or (lambda dsn: psycopg.connect(dsn, connect_timeout=2))

    def now(self) -> datetime:
        with self._connect(self.dsn) as connection:
            row = connection.execute("SELECT now_utc FROM demo_clock WHERE id = 1").fetchone()
        if row is None:
            raise ClockError("demo_clock has no row with id = 1")
        return _as_utc(row[0])


class HttpClock:
    def __init__(
        self,
        url: str,
        fallback: ClockSource,
        *,
        timeout: float = 0.3,
        cache_seconds: float = 1.0,
        transport: httpx.BaseTransport | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.url = url
        self.fallback = fallback
        self.timeout = timeout
        self.cache_seconds = cache_seconds
        self._client = httpx.Client(transport=transport, timeout=timeout)
        self._monotonic = monotonic
        self._value: datetime | None = None
        self._fetched_at = 0.0

    def now(self) -> datetime:
        if self._value is not None and self._monotonic() - self._fetched_at < self.cache_seconds:
            return self._value
        try:
            value = self._fetch()
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            # A failure is cached too, so a dead service costs one timeout per second.
            value = self.fallback.now()
        self._value, self._fetched_at = value, self._monotonic()
        return value

    def _fetch(self) -> datetime:
        response = self._client.get(f"{self.url.rstrip('/')}/clock")
        response.raise_for_status()
        return _as_utc(datetime.fromisoformat(response.json()["now_utc"]))


def db_dsn(env: Mapping[str, str]) -> str:
    """DSN for the ``app`` database: ``CLOCK_DSN`` if set, else built from ``POSTGRES_*``."""
    if env.get("CLOCK_DSN"):
        return env["CLOCK_DSN"]
    user = quote(env.get("POSTGRES_USER", "r2r"), safe="")
    password = quote(env.get("POSTGRES_PASSWORD", "r2r_dev_only"), safe="")
    host = env.get("POSTGRES_HOST", "postgres")
    port = env.get("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/app"


def source_from_env(env: Mapping[str, str]) -> ClockSource:
    kind = env.get("CLOCK_SOURCE", "").strip().lower() or "http"
    if kind == "fixed":
        raw = env.get("CLOCK_FIXED_NOW", "").strip()
        if raw:
            return FixedClock(datetime.fromisoformat(raw))
        return FixedClock(load_profile(env.get("SITE_PROFILE", "site_a")).demo.start_datetime)
    if kind == "db":
        return DbClock(db_dsn(env))
    if kind == "http":
        url = env.get("SCENARIO_URL", "http://scenario:8100")
        return HttpClock(url, fallback=DbClock(db_dsn(env)))
    raise ClockError(f"CLOCK_SOURCE must be http, db or fixed (got {kind!r})")


_source: ClockSource | None = None


def set_clock_source(source: ClockSource | None) -> None:
    """Use ``source`` from now on; ``None`` goes back to the environment default."""
    global _source
    _source = source


def get_clock_source() -> ClockSource:
    global _source
    if _source is None:
        _source = source_from_env(os.environ)
    return _source


def now() -> datetime:
    """The current demo time, timezone-aware, in UTC."""
    return get_clock_source().now()


@functools.cache
def _profile_timezone(name: str) -> ZoneInfo:
    return load_profile(name).site.tz


def _default_timezone() -> ZoneInfo:
    try:
        return _profile_timezone(os.environ.get("SITE_PROFILE", "site_a"))
    except ProfileError:
        return ZoneInfo("UTC")


def today(tz: ZoneInfo | None = None) -> date:
    """The current demo date in ``tz`` (default: the default profile's timezone, else UTC)."""
    return now().astimezone(tz or _default_timezone()).date()
