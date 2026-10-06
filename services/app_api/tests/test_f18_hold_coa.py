"""F18 T4 [TDD]: Place Hold and Release on COA: endpoints, versioning, audit, roles, composition.

F18-FR-08, FR-09, FR-10, F18-AC-03, F18-AC-04 and OQ-101 to OQ-103. Today is 2026-10-12 (demo clock).
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from r2r_core.profile import load_profile
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import D, batch, load_mirror

pytestmark = pytest.mark.integration

ROW = "RM10031|B2077|9001"  # sampling since 8 Oct, cycle start 2 Oct (support_f09)
OTHER = "RM10031|B2078|9002"
HOLD = f"/api/rows/{ROW}/hold"
COA = f"/api/rows/{ROW}/coa-release"
ALEX = {"X-Demo-User": "alex"}
SAM = {"X-Demo-User": "sam"}
QUINN = {"X-Demo-User": "quinn"}
PAT = {"X-Demo-User": "pat"}
ADMIN = {"X-Demo-User": "admin"}
REASON = {"on": True, "reason": "Awaiting supplier confirmation"}


@pytest.fixture(autouse=True)
def mirror(app_factory: sessionmaker[Session]) -> None:
    rows = [
        batch(),
        batch("B2078", lot="9002", on_hold=True),
        batch("B2079", lot="9003", stage_key="released", ud_effective=True),
        batch("B2080", lot="9004", stage_key="pending", cycle_start_date=None, current_stage_entry_date=None),
    ]
    load_mirror(app_factory, load_profile("site_a"), rows)


def find(client: TestClient, key: str = ROW) -> dict[str, Any]:
    rows = client.get("/api/overview?include_released=true").json()["rows"]
    return next(r for r in rows if r["row_key"] == key)


def audit(factory: sessionmaker[Session], action: str) -> list[dict[str, Any]]:
    with factory() as session:
        found = session.execute(
            text(
                "SELECT actor_user_key, row_key, details_json FROM audit_event WHERE action = :a ORDER BY id"
            ),
            {"a": action},
        )
        return [dict(r) for r in found.mappings()]


# --- Place Hold -------------------------------------------------------------------------------


def test_f18_ac03_alex_places_a_hold_and_the_row_becomes_an_exception(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    before = client.get("/api/overview").json()
    plan_before = find(client)["plan"]
    response = client.post(HOLD, json=REASON, headers=ALEX)
    assert response.status_code == 200, response.text
    after = client.get("/api/overview").json()
    held = find(client)
    assert held["flags"]["on_hold"] is True and held["flags"]["manual_hold"] is True
    assert held["flags"]["erp_hold"] is False
    assert held["manual_hold_reason"] == "Awaiting supplier confirmation"
    assert after["on_hold_count"] == before["on_hold_count"] + 1
    assert held["plan"] == plan_before  # F18-FR-09: the plan maths is unchanged
    keys = [r["row_key"] for r in after["rows"]]
    assert keys.index(ROW) < keys.index("RM10031|B2077|9001") + 1
    sampling = next(e for e in after["flow_strip"] if e["stage_key"] == "sampling")
    assert sampling["count"] == next(e for e in before["flow_strip"] if e["stage_key"] == "sampling")["count"]
    [event] = audit(app_factory, "hold_placed")
    assert event["actor_user_key"] == "alex" and event["row_key"] == ROW
    assert event["details_json"]["reason"] == "Awaiting supplier confirmation"
    assert event["details_json"]["previous"] is None


def test_f18_fr09_a_manual_hold_sorts_into_the_exception_block(client: TestClient) -> None:
    """Exceptions first: an ERP-held row (B2078) leads; the manually held row follows it, ahead of the rest."""
    client.post(HOLD, json=REASON, headers=ALEX)
    keys = [r["row_key"] for r in client.get("/api/overview").json()["rows"]]
    assert set(keys[:2]) == {ROW, OTHER}


def test_f18_fr09_the_on_hold_filter_uses_the_displayed_hold(client: TestClient) -> None:
    flagged = lambda: {r["row_key"] for r in client.get("/api/overview?flags[]=on_hold").json()["rows"]}  # noqa: E731
    assert flagged() == {OTHER}
    client.post(HOLD, json=REASON, headers=ALEX)
    assert flagged() == {OTHER, ROW}


def test_f18_fr08_release_hold_clears_only_the_manual_hold(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    other_hold = f"/api/rows/{OTHER}/hold"
    assert client.post(other_hold, json=REASON, headers=ALEX).status_code == 200
    flags = find(client, OTHER)["flags"]
    assert (flags["erp_hold"], flags["manual_hold"], flags["on_hold"]) == (True, True, True)
    cleared = client.post(other_hold, json={"on": False, "reason": "Supplier confirmed"}, headers=ALEX)
    assert cleared.status_code == 200
    flags = find(client, OTHER)["flags"]
    assert (flags["erp_hold"], flags["manual_hold"], flags["on_hold"]) == (True, False, True)
    [event] = audit(app_factory, "hold_released")
    assert event["details_json"]["previous"]["reason"] == "Awaiting supplier confirmation"


def test_f18_fr08_hold_versions_are_insert_only(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    client.post(HOLD, json=REASON, headers=ALEX)
    client.post(HOLD, json={"on": False, "reason": "Resolved"}, headers=ALEX)
    with app_factory() as session:
        found = session.execute(
            text("SELECT version, is_current FROM override_value WHERE field = 'manual_hold' ORDER BY id")
        )
        assert [tuple(r) for r in found] == [(1, False), (2, True)]


@pytest.mark.parametrize(
    ("headers", "allowed"), [(PAT, True), (ALEX, True), (ADMIN, True), (SAM, False), (QUINN, False)]
)
def test_f18_fr08_hold_roles(client: TestClient, headers: dict[str, str], allowed: bool) -> None:
    status = client.post(HOLD, json=REASON, headers=headers).status_code
    assert status == (200 if allowed else 403)


@pytest.mark.parametrize(
    ("headers", "allowed"), [(ALEX, True), (ADMIN, True), (PAT, False), (SAM, False), (QUINN, False)]
)
def test_f18_fr08_coa_roles(client: TestClient, headers: dict[str, str], allowed: bool) -> None:
    status = client.post(COA, json=REASON, headers=headers).status_code
    assert status == (200 if allowed else 403)


@pytest.mark.parametrize("reason", ["", "  ", "ab", "x" * 201])
def test_f18_fr08_the_reason_is_required_and_bounded(client: TestClient, reason: str) -> None:
    assert client.post(HOLD, json={"on": True, "reason": reason}, headers=ALEX).status_code == 422
    assert client.post(COA, json={"on": True, "reason": reason}, headers=ALEX).status_code == 422
    assert client.post(HOLD, json={"on": True, "reason": "  abc  "}, headers=ALEX).status_code == 200


def test_f18_fr08_clearing_also_needs_a_reason(client: TestClient) -> None:
    client.post(HOLD, json=REASON, headers=ALEX)
    assert client.post(HOLD, json={"on": False, "reason": ""}, headers=ALEX).status_code == 422


def test_f18_fr09_no_op_changes_are_conflicts(client: TestClient) -> None:
    assert (
        client.post(HOLD, json={"on": False, "reason": "nothing to release"}, headers=ALEX).status_code == 409
    )
    assert client.post(HOLD, json=REASON, headers=ALEX).status_code == 200
    assert client.post(HOLD, json=REASON, headers=ALEX).status_code == 409
    assert client.post(COA, json={"on": False, "reason": "nothing to undo"}, headers=ALEX).status_code == 409


def test_f18_fr09_a_released_row_cannot_be_held_or_coa_released(client: TestClient) -> None:
    released = "RM10031|B2079|9003"
    assert client.post(f"/api/rows/{released}/hold", json=REASON, headers=ALEX).status_code == 409
    assert client.post(f"/api/rows/{released}/coa-release", json=REASON, headers=ALEX).status_code == 409


def test_f18_fr09_a_pending_row_can_be_held_but_not_coa_released(client: TestClient) -> None:
    pending = "RM10031|B2080|9004"
    assert client.post(f"/api/rows/{pending}/hold", json=REASON, headers=ALEX).status_code == 200
    assert client.post(f"/api/rows/{pending}/coa-release", json=REASON, headers=ALEX).status_code == 409


def test_f18_fr08_unknown_row_is_404(client: TestClient) -> None:
    assert client.post("/api/rows/NOPE|B1|1/hold", json=REASON, headers=ALEX).status_code == 404


def test_f18_fr08_a_forbidden_attempt_is_audited_and_changes_nothing(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    client.post(HOLD, json=REASON, headers=SAM)
    assert audit(app_factory, "hold_placed") == []
    assert [e["actor_user_key"] for e in audit(app_factory, "forbidden")] == ["sam"]


# --- Release on COA -------------------------------------------------------------------------------


def test_f18_ac04_coa_release_moves_expected_completion_to_cycle_start_plus_14(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    before = find(client)
    assert before["plan"]["expected_completion"] == "2026-10-15"
    response = client.post(COA, json={"on": True, "reason": "COA received from supplier"}, headers=ALEX)
    assert response.status_code == 200, response.text
    row = find(client)
    assert row["plan"]["expected_completion"] == str(D(10, 2).replace(day=16))  # 2 Oct + 14 days
    assert row["flags"]["release_on_coa"] is True
    assert row["coa_release_reason"] == "COA received from supplier"
    assert row["plan"]["compressed"] is False
    [event] = audit(app_factory, "coa_release_set")
    assert event["details_json"]["reason"] == "COA received from supplier"


def test_f18_ac04_undo_restores_the_previous_plan(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    before = find(client)["plan"]
    client.post(COA, json=REASON, headers=ALEX)
    undone = client.post(COA, json={"on": False, "reason": "COA was for another batch"}, headers=ALEX)
    assert undone.status_code == 200
    assert find(client)["plan"] == before
    assert find(client)["flags"]["release_on_coa"] is False
    assert len(audit(app_factory, "coa_release_cleared")) == 1


def test_f18_fr10_the_release_on_coa_tag_filter_finds_the_row(client: TestClient) -> None:
    assert client.get("/api/overview?flags[]=release_on_coa").json()["rows"] == []
    client.post(COA, json=REASON, headers=ALEX)
    found = client.get("/api/overview?flags[]=release_on_coa").json()["rows"]
    assert [r["row_key"] for r in found] == [ROW]


def test_f18_fr10_coa_release_goes_late_from_the_cycle_start(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    old = batch("B2081", lot="9005", cycle_start_date=D(9, 10), current_stage_entry_date=D(9, 15))
    load_mirror(app_factory, load_profile("site_a"), [old])
    key = old["row_key"]
    assert client.post(f"/api/rows/{key}/coa-release", json=REASON, headers=ALEX).status_code == 200
    row = find(client, key)
    assert row["plan"]["expected_completion"] == "2026-09-24"
    assert (row["plan"]["late"], row["plan"]["days_remaining"]) == (True, -18)
    assert client.get("/api/overview").json()["rows"][0]["row_key"] == key


# --- the fields the table needs -------------------------------------------------------------------


def test_f18_fr03_rows_carry_the_table_columns(client: TestClient) -> None:
    row = find(client)
    for key in (
        "supplier_batch",
        "gr_date",
        "qc_testing_entry",
        "lims_approved_date",
        "ud_date",
        "next_inspection_date",
    ):
        assert key in row
