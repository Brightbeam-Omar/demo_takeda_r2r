"""F19 T7: the mirror of the new published objects, sample_count and the row detail (F19-FR-04, FR-08)."""

import json
from typing import Any

import pytest
from app_api.models import MIRRORS, OBJECTS_WITH_RUN_ID
from fastapi.testclient import TestClient
from r2r_core.profile import load_profile
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from support import FakeReader, published
from support_f09 import NOW, D, batch, load_mirror
from test_f08_mirror import sync

ROW = "RM10031|B2077|9001"
ITEMS = [
    {"seq": 1, "check_code": "PHYS", "check_label": "Physical evaluation", "outcome": "PASS"},
    {"seq": 2, "check_code": "QTYR", "check_label": "Quantity received verification", "outcome": "FAIL"},
]


def test_f19_fr08_the_new_objects_are_mirrored_and_carry_a_run_id() -> None:
    assert {"inbound_checks_v", "change_controls_v", "samples_v", "deviations_v"} <= set(MIRRORS)
    assert {"inbound_checks_v", "change_controls_v", "samples_v", "deviations_v"} <= set(OBJECTS_WITH_RUN_ID)
    assert len(MIRRORS) == 15  # F20 adds three
    deviation_columns = [c for c, _ in MIRRORS["deviations_v"][1]]
    assert deviation_columns[-5:] == [
        "causal_factor",
        "investigation_summary",
        "description",
        "owner",
        "run_id",
    ]
    assert MIRRORS["samples_v"][2] == ("row_key", "sample_id")
    assert MIRRORS["change_controls_v"][2] == ("cc_no", "material_no", "batch_no")
    assert MIRRORS["inbound_checks_v"][2] == ("row_key",)


@pytest.mark.integration
def test_f19_fr08_a_sync_mirrors_all_fifteen_objects_with_one_watermark_each(
    app_factory: sessionmaker[Session],
) -> None:
    done = sync(app_factory, FakeReader(published("run-A")))
    assert (done.status, done.error) == ("done", None)
    with app_factory() as session:
        marks = {r[0] for r in session.execute(text("SELECT object_name FROM watermark"))}
        counts = {
            table: session.execute(text(f"SELECT count(*) FROM {table}")).scalar()
            for table in ("mirror_inbound_checks", "mirror_change_controls", "mirror_samples")
        }
    assert marks == set(MIRRORS) and len(marks) == 15
    assert counts == {"mirror_inbound_checks": 3, "mirror_change_controls": 3, "mirror_samples": 3}


@pytest.fixture
def loaded(app_factory: sessionmaker[Session]) -> None:
    other = batch("B9", lot="9002")
    deviation = {
        "deviation_no": "DEV-1", "material_no": "RM10031", "batch_no": "B2077", "title": "Odd result",
        "severity": "moderate", "status": "closed", "opened_on": D(10, 1), "closed_on": D(10, 5),
        "root_cause_category": "Transport", "causal_factor": "Carrier handling",
        "investigation_summary": "Handled with the carrier.", "description": "Odd result. Recorded.",
        "owner": "QA", "run_id": "run-1",
    }  # fmt: skip
    change = {
        "cc_no": "CC-000001", "material_no": "RM10031", "batch_no": "B2077", "title": "Update storage",
        "status": "approved", "current_state": "2-8 C", "proposed_state": "2-25 C", "opened_on": D(10, 2),
        "effective_on": D(11, 1), "run_id": "run-1",
    }  # fmt: skip
    inbound = [
        {"row_key": ROW, "prueflos": "9001", "status": "resolved", "deadline": D(10, 12), "failed_count": 1,
         "items_json": json.dumps(ITEMS), "run_id": "run-1"},
    ]  # fmt: skip
    samples = [
        {"row_key": ROW, "sample_id": "S-0000002", "status": "approved", "collected_date": D(10, 8),
         "approved_at": NOW, "run_id": "run-1"},
        {"row_key": ROW, "sample_id": "S-0000001", "status": "rejected", "collected_date": D(10, 3),
         "approved_at": None, "run_id": "run-1"},
    ]  # fmt: skip
    load_mirror(
        app_factory, load_profile("site_a"), [batch(), other],
        deviations=[deviation], change_controls=[change], inbound_checks=inbound, samples=samples,
    )  # fmt: skip


@pytest.mark.integration
@pytest.mark.usefixtures("loaded")
def test_f19_fr04_the_overview_row_has_the_sample_count_of_its_lot(client: TestClient) -> None:
    rows = {r["row_key"]: r for r in client.get("/api/overview").json()["rows"]}
    assert rows[ROW]["sample_count"] == 2
    assert rows["RM10031|B9|9002"]["sample_count"] == 0


@pytest.mark.integration
@pytest.mark.usefixtures("loaded")
def test_f19_fr08_the_row_detail_carries_inbound_changes_samples_and_the_extended_deviations(
    client: TestClient,
) -> None:
    detail: dict[str, Any] = client.get(f"/api/rows/{ROW}").json()
    check = detail["inbound_check"]
    assert (check["prueflos"], check["status"], check["deadline"], check["failed_count"]) == (
        "9001", "resolved", "2026-10-12", 1,
    )  # fmt: skip
    assert [(i["check_label"], i["outcome"]) for i in check["items"]] == [
        ("Physical evaluation", "PASS"),
        ("Quantity received verification", "FAIL"),
    ]
    [deviation] = detail["deviations"]
    assert (deviation["severity"], deviation["causal_factor"], deviation["investigation_summary"]) == (
        "moderate", "Carrier handling", "Handled with the carrier.",
    )  # fmt: skip
    assert (
        deviation["description"] == "Odd result. Recorded."
        and deviation["root_cause_category"] == "Transport"
    )
    [change] = detail["changes"]
    assert (change["cc_no"], change["status"], change["proposed_state"], change["effective_on"]) == (
        "CC-000001", "approved", "2-25 C", "2026-11-01",
    )  # fmt: skip
    assert [s["sample_id"] for s in detail["samples"]] == ["S-0000001", "S-0000002"]
    assert detail["samples"][0]["status"] == "rejected" and detail["samples"][1]["approved_at"]
    other = client.get("/api/rows/RM10031|B9|9002").json()
    assert other["inbound_check"] is None and other["samples"] == []
    assert [c["cc_no"] for c in other["changes"]] == []  # B9 is another batch


@pytest.mark.integration
def test_f19_fr08_a_stale_deviation_row_is_a_mixed_publish(app_factory: sessionmaker[Session]) -> None:
    """deviations_v carries a run_id since F19, so it is part of the F08 consistency rule."""
    sync(app_factory, FakeReader(published("run-A")))
    mixed = published("run-B")
    stale = {column: f"{column}-0" for column, _ in MIRRORS["deviations_v"][1]}
    mixed["deviations_v"] = [
        stale | {"run_id": "run-A", "opened_on": D(10, 1), "closed_on": None}
    ]  # one row of the previous run
    failed = sync(app_factory, FakeReader(mixed), run_id="run-B")
    assert failed.status == "failed" and failed.error is not None and "deviations_v" in failed.error
