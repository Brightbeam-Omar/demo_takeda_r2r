"""T7: the clock service against a real `app` database [F04-FR-07, F04-AC-04]. Needs Postgres (integration)."""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from app_api.db import migrate
from fastapi.testclient import TestClient
from r2r_core.db import make_engine
from r2r_core.profile import load_profile
from scenario.app import create_app
from sqlalchemy import Engine, text

pytestmark = pytest.mark.integration

TOKEN = {"X-Scenario-Token": "s3cret"}
OPENING = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)  # site_a: 08:00 Europe/Dublin (+01:00)


@pytest.fixture(scope="module")
def engine(make_test_database: Callable[[str], str]) -> Iterator[Engine]:
    dsn = make_test_database("app_clock")
    migrate(dsn)
    engine = make_engine(dsn)
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("SCENARIO_TOKEN", "s3cret")
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM demo_clock"))
    with TestClient(create_app(engine, load_profile("site_a"))) as client:  # startup seeds the row
        yield client


def now_of(client: TestClient) -> datetime:
    return datetime.fromisoformat(client.get("/clock").json()["now_utc"])


def test_f04_fr07_first_start_seeds_the_clock_from_the_profile(client: TestClient) -> None:
    body = client.get("/clock").json()
    assert datetime.fromisoformat(body["now_utc"]) == OPENING
    assert body["today_local"] == "2026-10-12"
    assert body["frozen"] is False


def test_f04_fr07_a_restart_never_overwrites_an_existing_clock(client: TestClient, engine: Engine) -> None:
    client.post("/clock/set", json={"iso": "2026-11-01T09:30:00+00:00"}, headers=TOKEN)
    with TestClient(create_app(engine, load_profile("site_a"))) as restarted:
        assert datetime.fromisoformat(restarted.get("/clock").json()["now_utc"]) == datetime(
            2026, 11, 1, 9, 30, tzinfo=UTC
        )


def test_f04_ac04_advance_by_one_day_moves_the_clock_exactly_24_hours(client: TestClient) -> None:
    """F04-AC-04 (the other-container half is covered by `make stack-test`)."""
    before = now_of(client)
    response = client.post("/clock/advance", json={"days": 1}, headers=TOKEN)
    assert response.status_code == 200
    assert datetime.fromisoformat(response.json()["now_utc"]) == before + timedelta(hours=24)
    assert now_of(client) == before + timedelta(hours=24)


def test_f04_fr07_advance_by_hours_and_today_local_follows_the_site_timezone(client: TestClient) -> None:
    client.post("/clock/advance", json={"hours": 16}, headers=TOKEN)  # 23:00 UTC = 00:00 next day in Dublin
    body = client.get("/clock").json()
    assert datetime.fromisoformat(body["now_utc"]) == OPENING + timedelta(hours=16)
    assert body["today_local"] == "2026-10-13"


def test_f04_fr07_set_accepts_any_offset_and_stores_utc(client: TestClient) -> None:
    response = client.post("/clock/set", json={"iso": "2026-12-01T10:00:00+02:00"}, headers=TOKEN)
    assert datetime.fromisoformat(response.json()["now_utc"]) == datetime(2026, 12, 1, 8, 0, tzinfo=UTC)


def test_f04_fr07_the_clock_does_not_tick_with_wall_time(client: TestClient) -> None:
    first = now_of(client)
    assert now_of(client) == first


def test_f04_fr07_the_table_allows_a_single_row_only(engine: Engine) -> None:
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("INSERT INTO demo_clock (id, now_utc) VALUES (2, now())"))
