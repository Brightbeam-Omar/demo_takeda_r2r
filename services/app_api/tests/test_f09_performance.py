"""F09 T7: the composed-row cache (OQ-061) and the Overview speed on ~800 rows (F09-FR-07, F09-AC-09)."""

import statistics
import time
from datetime import timedelta
from typing import Any

import pytest
from app_api.services import store
from fastapi.testclient import TestClient
from r2r_core import clock
from r2r_core.clock import FixedClock
from r2r_core.profile import SiteProfile, load_profile
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import NOW, D, batch, load_mirror

pytestmark = pytest.mark.integration

STAGES = ("sampling", "qc_testing", "qa_release")
ROWS = 800


@pytest.fixture
def big_mirror(app_factory: sessionmaker[Session]) -> SiteProfile:
    profile = load_profile("site_a")
    rows = [
        batch(
            f"B{n:04d}", f"RM{10000 + n % 60}", lot=str(9000 + n), stage_key=STAGES[n % 3],
            current_stage_entry_date=D(10, 1 + n % 11), system_need_by_locked=D(10, 20) + timedelta(days=n % 40),
            campaign=f"CMP-{n % 5}", molecule_type=("small_molecule", "peptide")[n % 2],
            on_hold=n % 37 == 0, ud_rejected=n % 41 == 0,
        )
        for n in range(ROWS)
    ]  # fmt: skip
    load_mirror(app_factory, profile, rows)
    return profile


def p95(samples: list[float]) -> float:
    return sorted(samples)[int(len(samples) * 0.95) - 1]


def timed(client: TestClient, before: Any = None) -> list[float]:
    samples = []
    for _ in range(30):
        if before:
            before()
        began = time.perf_counter()
        response = client.get("/api/overview")
        samples.append((time.perf_counter() - began) * 1000)
        assert response.status_code == 200 and response.json()["total"] == ROWS
    return samples


def test_f09_ac09_overview_p95_is_under_300_ms_for_800_rows_even_with_a_cold_cache(
    client: TestClient, big_mirror: SiteProfile
) -> None:
    client.get("/api/overview")  # import and connection warm-up
    cold = timed(client, store.clear_cache)
    warm = timed(client)
    print(
        f"overview p95: cold {p95(cold):.0f} ms, warm {p95(warm):.0f} ms, warm median {statistics.median(warm):.0f} ms"
    )
    assert p95(cold) < 300 and p95(warm) < 300


def test_f09_fr07_a_burst_of_reads_shares_one_composition(
    client: TestClient, big_mirror: SiteProfile, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []
    original = store._compose

    def counting(*args: Any, **kwargs: Any) -> store.Composed:
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(store, "_compose", counting)
    for _ in range(5):
        client.get("/api/overview")
    assert len(calls) == 1


def test_f09_fr07_an_override_a_comment_or_a_clock_advance_is_visible_at_once(
    client: TestClient, big_mirror: SiteProfile
) -> None:
    key = "RM10000|B0000|9000"
    first = client.get("/api/overview").json()
    assert next(r for r in first["rows"] if r["row_key"] == key)["status_log_count"] == 0
    client.post(f"/api/rows/{key}/comments", json={"body": "hello"})
    again = client.get("/api/overview").json()
    assert next(r for r in again["rows"] if r["row_key"] == key)["status_log_count"] == 1

    days_before = next(r for r in again["rows"] if r["row_key"] == key)["days_in_stage"]
    clock.set_clock_source(FixedClock(NOW + timedelta(days=1)))
    later = client.get("/api/overview").json()
    assert next(r for r in later["rows"] if r["row_key"] == key)["days_in_stage"] == days_before + 1


def test_f09_fr07_the_cache_expires_after_five_seconds(
    client: TestClient, big_mirror: SiteProfile, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []
    original = store._compose
    monkeypatch.setattr(store, "_compose", lambda *a, **k: (calls.append(1), original(*a, **k))[1])
    client.get("/api/overview")
    store._cache["at"] -= store.CACHE_SECONDS + 1  # as if the entry were older than its time to live
    client.get("/api/overview")
    assert len(calls) == 2
