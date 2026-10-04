"""F04 acceptance tests against the real containers (`make stack-test`, or `make up` first).

These talk to the compose stack over HTTP on the published ports, to Postgres on localhost, and use
`docker compose exec` for the cross-container clock check. They leave data behind (a batch with a unique
name, a few master-data rows) and put the demo clock back where they found it, so run them on a
throwaway stack; `make demo-reset` (F13) wipes it.
"""

import os
import subprocess
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest

pytestmark = pytest.mark.stack

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO, ERP, LIMS, QMS = (
    f"http://localhost:{os.environ.get(name, default)}"
    for name, default in (
        ("SCENARIO_HOST_PORT", 8100),
        ("ERP_HOST_PORT", 8101),
        ("LIMS_HOST_PORT", 8102),
        ("QMS_HOST_PORT", 8103),
    )
)


def _env(name: str, default: str) -> str:
    if name in os.environ:
        return os.environ[name]
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return default


READ_CLOCK = "from r2r_core import clock; print(clock.now().isoformat())"
TOKEN = {"X-Scenario-Token": _env("SCENARIO_TOKEN", "dev-only-change-me")}


def _pg(database: str) -> psycopg.Connection[Any]:
    return psycopg.connect(
        host="localhost",
        port=int(os.environ.get("POSTGRES_HOST_PORT", "5432")),
        user=_env("POSTGRES_USER", "r2r"),
        password=_env("POSTGRES_PASSWORD", "r2r_dev_only"),
        dbname=database,
        autocommit=True,
    )


def demo_now() -> datetime:
    return datetime.fromisoformat(httpx.get(f"{SCENARIO}/clock", timeout=5).json()["now_utc"])


@pytest.fixture(scope="module", autouse=True)
def stack_is_up() -> None:
    try:
        httpx.get(f"{SCENARIO}/health", timeout=3).raise_for_status()
    except httpx.HTTPError:
        pytest.fail("the stack is not running: start it with `make up` (or run `make stack-test`)")


@pytest.fixture
def restore_clock() -> Iterator[None]:
    before = demo_now()
    yield
    httpx.post(
        f"{SCENARIO}/clock/set", json={"iso": before.isoformat()}, headers=TOKEN, timeout=5
    ).raise_for_status()


@pytest.fixture(scope="module")
def master_data() -> None:
    """The ERP simulator has no master-data endpoint (the generator seeds it in F05): insert a minimum."""
    now = demo_now()
    with _pg("erp_sim") as connection:
        connection.execute(
            "INSERT INTO mara (matnr, maktx, mtart, zmolty, zclass, updated_at) "
            "VALUES ('RM-STACK', 'Stack test material', 'ROH', 'small_molecule', 'consumable', %s) "
            "ON CONFLICT DO NOTHING",
            (now,),
        )
        connection.execute(
            "INSERT INTO lfa1 (lifnr, name1, land1, updated_at) VALUES ('SUP-STACK', 'Stack supplier', 'IE', %s) "
            "ON CONFLICT DO NOTHING",
            (now,),
        )
        connection.execute(
            "INSERT INTO t001l (lgort, lgobe, zloctype, updated_at) VALUES ('0100', 'Main warehouse', 'onsite', %s) "
            "ON CONFLICT DO NOTHING",
            (now,),
        )


def test_f04_ac01_health_and_clock_endpoints_return_200() -> None:
    """F04-AC-01: after `make up`, :8101/:8102/:8103 /health and :8100/clock return 200."""
    for url in (f"{ERP}/health", f"{LIMS}/health", f"{QMS}/health", f"{SCENARIO}/clock"):
        assert httpx.get(url, timeout=5).status_code == 200, url


def test_f04_fr08_openapi_docs_are_served_by_every_service() -> None:
    for base in (SCENARIO, ERP, LIMS, QMS):
        assert httpx.get(f"{base}/docs", timeout=5).status_code == 200, base


def test_f04_ac03_writes_without_the_token_return_401_on_every_service() -> None:
    writes = [
        f"{ERP}/events/goods-receipt",
        f"{LIMS}/events/sample-collected",
        f"{QMS}/events/deviation-opened",
        f"{SCENARIO}/clock/advance",
        f"{SCENARIO}/clock/set",
    ]
    for url in writes:
        assert httpx.post(url, json={}, timeout=5).status_code == 401, url
        assert (
            httpx.post(url, json={}, headers={"X-Scenario-Token": "wrong"}, timeout=5).status_code == 401
        ), url


WATCH_CLOCK = """
import time
from r2r_core import clock

old = clock.now()
print("ready", old.isoformat(), flush=True)
start = time.monotonic()
while time.monotonic() - start < 4:
    seen = clock.now()
    if seen != old:
        print("changed", seen.isoformat(), round(time.monotonic() - start, 3), flush=True)
        break
    time.sleep(0.05)
"""


def test_f04_ac04_advance_one_day_moves_the_clock_24h_and_another_container_sees_it_within_2s(
    restore_clock: None,
) -> None:
    """F04-AC-04: the clock moves exactly 24 h, and r2r_core.clock.now() in a running erp-sim process follows.

    The watcher reads the clock once (and so caches it), signals it is ready, then polls; the test advances the
    clock and the watcher reports how long it took to see the new time.
    """
    before = demo_now()
    expected = before + timedelta(hours=24)
    watcher = subprocess.Popen(
        ["docker", "compose", "exec", "-T", "erp-sim", "python", "-u", "-c", WATCH_CLOCK],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert watcher.stdout is not None
    try:
        ready = watcher.stdout.readline().split()
        assert ready[0] == "ready" and datetime.fromisoformat(ready[1]) == before
        response = httpx.post(f"{SCENARIO}/clock/advance", json={"days": 1}, headers=TOKEN, timeout=5)
        assert response.status_code == 200
        assert demo_now() == expected
        changed = watcher.stdout.readline().split()
    finally:
        watcher.kill()
    assert changed[0] == "changed", "the other container never saw the new time"
    assert datetime.fromisoformat(changed[1]) == expected
    assert float(changed[2]) < 2.0, f"the other container took {changed[2]} s to see the new time"


def test_f04_ac02_goods_receipt_writes_consistent_rows_stamped_with_the_demo_now(master_data: None) -> None:
    """F04-AC-02: GR for a new batch writes mseg, mchb, mcha, qals (01) and an open zinbchk, updated_at = demo now."""
    charg = f"S{uuid.uuid4().hex[:9].upper()}"
    body = {"matnr": "RM-STACK", "charg": charg, "lifnr": "SUP-STACK", "lgort": "0100", "menge": 25}
    now = demo_now()
    response = httpx.post(f"{ERP}/events/goods-receipt", json=body, headers=TOKEN, timeout=10)
    assert response.status_code == 200, response.text
    lot = response.json()["qals"]["prueflos"]
    with _pg("erp_sim") as connection:
        queries = {
            "mcha": ("SELECT updated_at FROM mcha WHERE charg = %s", charg),
            "mseg": ("SELECT updated_at FROM mseg WHERE charg = %s AND bwart = '101'", charg),
            "mchb": ("SELECT updated_at FROM mchb WHERE charg = %s", charg),
            "qals": ("SELECT updated_at FROM qals WHERE prueflos = %s AND art = '01'", lot),
            "zinbchk": ("SELECT updated_at FROM zinbchk WHERE prueflos = %s AND status = 'open'", lot),
        }
        for table, (sql, key) in queries.items():
            rows = connection.execute(sql, (key,)).fetchall()
            assert len(rows) == 1, table
            assert rows[0][0] == now, table
    assert httpx.post(f"{ERP}/events/goods-receipt", json=body, headers=TOKEN, timeout=10).status_code == 409


def test_f04_ac05_usage_decision_with_an_unknown_code_returns_422(master_data: None) -> None:
    charg = f"S{uuid.uuid4().hex[:9].upper()}"
    body = {"matnr": "RM-STACK", "charg": charg, "lifnr": "SUP-STACK", "lgort": "0100", "menge": 5}
    lot = httpx.post(f"{ERP}/events/goods-receipt", json=body, headers=TOKEN, timeout=10).json()["qals"][
        "prueflos"
    ]
    bad = httpx.post(
        f"{ERP}/events/usage-decision", json={"prueflos": lot, "vcode": "Z9"}, headers=TOKEN, timeout=10
    )
    assert bad.status_code == 422


def test_f04_ac06_lims_approved_sets_the_status_and_approved_at_to_the_demo_now() -> None:
    lot = f"9{uuid.uuid4().int % 10**7:07d}"
    sample = {"inspection_lot_no": lot, "material_no": "RM-STACK", "batch_no": "B-STACK"}
    sample_id = httpx.post(f"{LIMS}/events/sample-collected", json=sample, headers=TOKEN, timeout=10).json()[
        "sample"
    ]["sample_id"]
    now = demo_now()
    response = httpx.post(f"{LIMS}/events/approved", json={"sample_id": sample_id}, headers=TOKEN, timeout=10)
    assert response.status_code == 200
    assert response.json()["sample"]["status"] == "approved"
    assert datetime.fromisoformat(response.json()["sample"]["approved_at"]).astimezone(UTC) == now


def test_f04_fr05_qms_opens_and_closes_a_deviation_for_a_batch() -> None:
    opened = httpx.post(
        f"{QMS}/events/deviation-opened",
        json={
            "title": "Stack test",
            "severity": "minor",
            "links": [{"material_no": "RM-STACK", "batch_no": "B-STACK"}],
        },
        headers=TOKEN,
        timeout=10,
    )
    assert opened.status_code == 200
    number = opened.json()["deviation"]["deviation_no"]
    assert any(
        d["deviation_no"] == number
        for d in httpx.get(f"{QMS}/deviations", params={"batch_no": "B-STACK"}).json()
    )
    closed = httpx.post(
        f"{QMS}/events/deviation-closed", json={"deviation_no": number}, headers=TOKEN, timeout=10
    )
    assert closed.json()["deviation"]["status"] == "closed"
