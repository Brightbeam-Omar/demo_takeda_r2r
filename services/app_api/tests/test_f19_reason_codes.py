"""F19 T6 [TDD]: labelled reason codes, the OTHER-needs-a-note rule and the migration (F19-FR-06, OQ-112)."""

from collections.abc import Callable
from typing import Any

import pytest
from app_api.db import migrate
from fastapi.testclient import TestClient
from r2r_core.db import make_engine
from r2r_core.profile import load_profile
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import batch, load_mirror

pytestmark = pytest.mark.integration

ROW = "RM10031|B2077|9001"
URL = f"/api/rows/{ROW}/need-by"
NEW_CODES = [
    "CAMPAIGN_PULLED_FORWARD", "CAMPAIGN_PUSHED_BACK", "VERBAL_CONFIRMATION", "SHELF_LIFE_CONSTRAINT",
    "SUPPLIER_DELAY", "RETEST_REQUIRED", "EXPEDITE_PRODUCTION", "EXPEDITE_SHIPPING", "TESTING_CAPACITY", "OTHER",
]  # fmt: skip


@pytest.fixture
def mirror(app_factory: sessionmaker[Session]) -> None:
    load_mirror(app_factory, load_profile("site_a"), [batch()])


@pytest.mark.usefixtures("mirror")
def test_f19_fr06_the_reference_lists_the_ten_labelled_codes(client: TestClient) -> None:
    codes = client.get("/api/reference").json()["reason_codes"]
    assert sorted(c["code"] for c in codes) == sorted(NEW_CODES)
    labels = {c["code"]: c["label"] for c in codes}
    assert labels["CAMPAIGN_PULLED_FORWARD"] == "Campaign pulled forward"
    assert labels["VERBAL_CONFIRMATION"] == "Verbal confirmation received"
    assert labels["OTHER"] == "Other — see notes"


@pytest.mark.usefixtures("mirror")
@pytest.mark.parametrize("note", [None, "", "   "])
def test_f19_fr06_other_without_a_note_is_422_and_with_a_note_is_saved(
    client: TestClient, note: str | None
) -> None:
    body: dict[str, Any] = {"adjusted_date": "2026-11-26", "reason_code": "OTHER", "note": note}
    refused = client.put(URL, json=body)
    assert refused.status_code == 422 and "note" in refused.text
    accepted = client.put(URL, json=body | {"note": "Agreed on the phone with planning"})
    assert accepted.status_code == 200
    assert accepted.json()["adjusted_reason_code"] == "OTHER"


@pytest.mark.usefixtures("mirror")
def test_f19_fr06_a_retired_code_is_no_longer_accepted(client: TestClient) -> None:
    body = {"adjusted_date": "2026-11-26", "reason_code": "CAMPAIGN_PUSHED_OUT"}
    assert client.put(URL, json=body).status_code == 422


@pytest.mark.usefixtures("mirror")
def test_f19_fr06_other_needs_no_note_when_the_date_is_cleared(client: TestClient) -> None:
    client.put(URL, json={"adjusted_date": "2026-11-26", "reason_code": "SUPPLIER_DELAY"})
    assert client.put(URL, json={"adjusted_date": None}).status_code == 200


def test_f19_fr06_the_migration_appends_new_current_versions_for_retired_codes_and_audits_them(
    make_test_database: Callable[[str], str],
) -> None:
    dsn = make_test_database("app_reason_migration")
    migrate(dsn, "0009")
    engine = make_engine(dsn)
    insert = (
        "INSERT INTO override_value (row_key, field, value_json, reason_code, note, version, author_user_key, "
        "created_at, is_current) VALUES (:k, 'adjusted_need_by_date', CAST(:v AS jsonb), :c, :n, :ver, :a, "
        "'2026-10-05T09:00:00Z', :cur)"
    )
    rows = [
        ("R1", '"2026-11-20"', "CAMPAIGN_PUSHED_OUT", None, 1, "pat", True),
        ("R2", '"2026-11-21"', "LAB_CAPACITY", "Lab is full", 1, "pat", True),
        ("R3", '"2026-11-22"', "CONSOLIDATED_TESTING", "Testing with R4", 1, "admin", True),
        ("R4", '"2026-11-23"', "DOCUMENTATION_ISSUE", None, 1, "pat", True),
        ("R5", '"2026-11-24"', "SUPPLIER_DELAY", None, 1, "pat", True),
        ("R6", '"2026-11-25"', "LAB_CAPACITY", None, 1, "pat", False),  # superseded: history stays as it is
        ("R6", '"2026-11-26"', "EXPEDITE_SHIPPING", None, 2, "pat", True),
        ("R7", "null", None, None, 1, "pat", True),  # a cleared override has no code
    ]
    with engine.begin() as c:
        c.execute(
            text("INSERT INTO demo_clock (id, now_utc, frozen) VALUES (1, '2026-10-12T07:00:00Z', false)")
        )
        for k, v, code, note, version, author, current in rows:
            c.execute(
                text(insert),
                {"k": k, "v": v, "c": code, "n": note, "ver": version, "a": author, "cur": current},
            )
    migrate(dsn)
    with engine.connect() as c:
        current = {
            r[0]: tuple(r[1:])
            for r in c.execute(
                text(
                    "SELECT row_key, reason_code, note, version, author_user_key FROM override_value WHERE is_current"
                )
            )
        }
        total = c.execute(text("SELECT count(*) FROM override_value")).scalar()
        old = c.execute(
            text("SELECT is_current FROM override_value WHERE row_key = 'R1' AND version = 1")
        ).scalar()
        audits = [
            tuple(r)
            for r in c.execute(
                text(
                    "SELECT actor_user_key, row_key, details_json FROM audit_event WHERE action = 'reason_code_migrated' ORDER BY id"
                )
            )
        ]
    engine.dispose()
    assert current["R1"] == ("CAMPAIGN_PUSHED_BACK", None, 2, "pat")
    assert current["R2"] == ("TESTING_CAPACITY", "Lab is full", 2, "pat")
    assert current["R3"] == ("OTHER", "CONSOLIDATED_TESTING: Testing with R4", 2, "admin")
    assert current["R4"] == ("OTHER", "DOCUMENTATION_ISSUE", 2, "pat")
    assert current["R5"] == ("SUPPLIER_DELAY", None, 1, "pat")  # a valid code is left alone
    assert current["R6"] == ("EXPEDITE_SHIPPING", None, 2, "pat")
    assert current["R7"] == (None, None, 1, "pat")
    assert total == 8 + 4  # four new versions; nothing was deleted
    assert old is False  # the superseded version is flagged, never edited or removed
    assert [(a[0], a[1], a[2]["old"], a[2]["new"]) for a in audits] == [
        ("system", "R1", "CAMPAIGN_PUSHED_OUT", "CAMPAIGN_PUSHED_BACK"),
        ("system", "R2", "LAB_CAPACITY", "TESTING_CAPACITY"),
        ("system", "R3", "CONSOLIDATED_TESTING", "OTHER"),
        ("system", "R4", "DOCUMENTATION_ISSUE", "OTHER"),
    ]
