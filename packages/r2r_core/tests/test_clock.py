"""T2: demo clock sources, fallback and default selection [F03-FR-03, F03-AC-14]."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from r2r_core import clock
from r2r_core.clock import ClockError, DbClock, FixedClock, HttpClock

NOON = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
DUBLIN = ZoneInfo("Europe/Dublin")


@pytest.fixture(autouse=True)
def _reset_source() -> Iterator[None]:
    yield
    clock.set_clock_source(None)


class FakeConnection:
    """Stands in for a psycopg connection: context manager with execute(...).fetchone()."""

    def __init__(self, row: tuple[Any, ...] | None) -> None:
        self.row = row

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str) -> "FakeConnection":
        assert "demo_clock" in sql
        return self

    def fetchone(self) -> tuple[Any, ...] | None:
        return self.row


def _db(value: datetime | None, seen: list[str] | None = None) -> DbClock:
    def connect(dsn: str) -> FakeConnection:
        if seen is not None:
            seen.append(dsn)
        return FakeConnection(None if value is None else (value,))

    return DbClock("postgresql://db/app", connect=connect)


class Ticker:
    """A controllable monotonic clock for the 1 s cache."""

    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


def _http(handler: Any, fallback: Any, ticker: Ticker | None = None) -> HttpClock:
    return HttpClock(
        "http://scenario:8100/",
        fallback=fallback,
        transport=httpx.MockTransport(handler),
        monotonic=ticker or Ticker(),
    )


def _ok(now_utc: str) -> Any:
    return lambda request: httpx.Response(200, json={"now_utc": now_utc, "frozen": False, "today_local": "x"})


def test_f03_ac14_fixed_clock_drives_now_and_today() -> None:
    """F03-AC-14: FixedClock drives now() and today()."""
    clock.set_clock_source(FixedClock(NOON))
    assert clock.now() == NOON
    assert clock.today(ZoneInfo("UTC")).isoformat() == "2026-10-12"


def test_f03_fr03_today_uses_the_given_timezone() -> None:
    clock.set_clock_source(FixedClock(datetime(2026, 10, 12, 23, 30, tzinfo=UTC)))
    assert clock.today(ZoneInfo("UTC")).isoformat() == "2026-10-12"
    assert clock.today(DUBLIN).isoformat() == "2026-10-13"  # 00:30 local


def test_f03_oq018_today_defaults_to_the_default_profile_timezone() -> None:
    clock.set_clock_source(FixedClock(datetime(2026, 10, 12, 23, 30, tzinfo=UTC)))
    assert clock.today().isoformat() == "2026-10-13"  # site_a is Europe/Dublin


def test_f03_fr03_now_is_always_utc() -> None:
    clock.set_clock_source(FixedClock(datetime(2026, 10, 12, 13, 0, tzinfo=DUBLIN)))
    assert clock.now().utcoffset() == timedelta(0)
    assert clock.now().hour == 12


def test_f03_fr03_fixed_clock_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="timezone"):
        FixedClock(datetime(2026, 10, 12, 12, 0))


def test_f03_fr03_db_clock_reads_demo_clock_row() -> None:
    seen: list[str] = []
    assert _db(NOON, seen).now() == NOON
    assert seen == ["postgresql://db/app"]


def test_f03_fr03_db_clock_treats_naive_values_as_utc() -> None:
    assert _db(datetime(2026, 10, 12, 12, 0)).now() == NOON


def test_f03_fr03_db_clock_without_a_row_is_a_clock_error() -> None:
    with pytest.raises(ClockError, match="demo_clock"):
        _db(None).now()


def test_f03_fr03_http_clock_reads_now_utc_and_ignores_other_fields() -> None:
    http = _http(_ok("2026-10-12T14:00:00+02:00"), fallback=_db(None))
    assert http.now() == NOON
    assert http.timeout == 0.3


def test_f03_fr03_http_clock_requests_the_clock_endpoint() -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(200, json={"now_utc": NOON.isoformat(), "frozen": False})

    _http(handler, fallback=_db(None)).now()
    assert urls == ["http://scenario:8100/clock"]


def test_f03_fr03_http_clock_caches_for_one_second() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json={"now_utc": NOON.isoformat(), "frozen": False})

    ticker = Ticker()
    http = _http(handler, fallback=_db(None), ticker=ticker)
    http.now()
    ticker.t += 0.9
    http.now()
    assert len(calls) == 1
    ticker.t += 0.2  # 1.1 s since the fetch
    http.now()
    assert len(calls) == 2


def _down(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("scenario service is down")


@pytest.mark.parametrize(
    "handler",
    [
        _down,
        lambda request: httpx.Response(500),
        lambda request: httpx.Response(200, text="not json"),
        lambda request: httpx.Response(200, json={"frozen": False}),
        lambda request: httpx.Response(200, json={"now_utc": "yesterday-ish"}),
    ],
    ids=["connect-error", "http-500", "bad-json", "missing-field", "bad-timestamp"],
)
def test_f03_ac14_http_clock_falls_back_to_db_clock(handler: Any) -> None:
    """F03-AC-14: HttpClock falls back to DbClock when the scenario service is down (mocked)."""
    assert _http(handler, fallback=_db(NOON)).now() == NOON


def test_f03_ac14_a_failed_fetch_is_cached_so_a_dead_service_costs_one_timeout_per_second() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        raise httpx.ConnectError("down")

    ticker = Ticker()
    http = _http(handler, fallback=_db(NOON), ticker=ticker)
    http.now()
    http.now()
    assert len(attempts) == 1
    ticker.t += 1.5
    http.now()
    assert len(attempts) == 2


def test_f03_oq018_default_source_is_http_with_db_fallback() -> None:
    source = clock.source_from_env({"SCENARIO_URL": "http://s:1", "POSTGRES_PASSWORD": "p@ss/word"})
    assert isinstance(source, HttpClock)
    assert source.url == "http://s:1"
    assert isinstance(source.fallback, DbClock)
    assert source.fallback.dsn == "postgresql://r2r:p%40ss%2Fword@postgres:5432/app"


def test_f03_oq018_db_source_and_dsn_override() -> None:
    assert isinstance(clock.source_from_env({"CLOCK_SOURCE": "db"}), DbClock)
    override = clock.source_from_env({"CLOCK_SOURCE": "db", "CLOCK_DSN": "postgresql://x/y"})
    assert isinstance(override, DbClock)
    assert override.dsn == "postgresql://x/y"


def test_f03_oq018_fixed_source_reads_clock_fixed_now() -> None:
    source = clock.source_from_env({"CLOCK_SOURCE": "fixed", "CLOCK_FIXED_NOW": "2026-10-12T12:00:00+00:00"})
    assert source.now() == NOON


def test_f03_oq018_fixed_source_falls_back_to_profile_start() -> None:
    source = clock.source_from_env({"CLOCK_SOURCE": "fixed"})
    assert source.now() == datetime(2026, 10, 12, 7, 0, tzinfo=UTC)  # 08:00 +01:00


def test_f03_oq018_unknown_source_is_rejected() -> None:
    with pytest.raises(ClockError, match="CLOCK_SOURCE"):
        clock.source_from_env({"CLOCK_SOURCE": "wall"})


def test_f03_fr03_default_source_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLOCK_SOURCE", "fixed")
    monkeypatch.setenv("CLOCK_FIXED_NOW", "2026-10-12T12:00:00+00:00")
    clock.set_clock_source(None)
    assert clock.now() == NOON
