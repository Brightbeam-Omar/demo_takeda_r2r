"""F18 T8 [TDD]: the three CSV exports (F18-FR-07, F18-AC-05, OQ-104). Today is 2026-10-12."""

import csv
import io
from typing import Any

import pytest
from fastapi.testclient import TestClient
from r2r_core.profile import load_profile
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import D, batch, load_mirror

pytestmark = pytest.mark.integration

SAMPLING = [("B1", "9001"), ("B2", "9002"), ("B3", "9003")]


@pytest.fixture(autouse=True)
def mirror(app_factory: sessionmaker[Session]) -> None:
    rows = [batch(b, lot=lot) for b, lot in SAMPLING]
    rows[1]["campaign"] = "CMP-ALPHA"
    rows[2]["on_hold"] = True
    rows += [
        batch(
            "B4", lot="9004", stage_key="qc_testing", current_stage_entry_date=D(10, 5), sample_id="S-0000004"
        ),
        batch(
            "B5",
            lot="9005",
            stage_key="qc_ship",
            current_stage_entry_date=D(10, 6),
            sample_id="S-0000005",
            offsite_test=True,
            offsite=True,
            external_lab="External Lab A",
        ),
        batch(
            "B6",
            lot="9006",
            stage_key="qa_release",
            current_stage_entry_date=D(10, 9),
            lims_status="approved",
        ),
        batch("B7", lot="9007", stage_key="released", ud_effective=True),
    ]
    for row in rows:
        row["storage_location"], row["location_type"] = "0100", "onsite"
    load_mirror(app_factory, load_profile("site_a"), rows)


def parse(response: Any) -> list[dict[str, str]]:
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    return list(csv.DictReader(io.StringIO(response.text)))


def test_f18_fr07_the_table_export_is_the_overview_and_the_old_path_is_an_alias(client: TestClient) -> None:
    table = client.get("/api/export/table.csv")
    alias = client.get("/api/export.csv")
    assert table.text == alias.text
    assert len(parse(table)) == client.get("/api/overview").json()["total"]


def test_f18_ac05_sampling_plan_row_count_equals_the_sampling_rows_under_the_filters(
    client: TestClient,
) -> None:
    rows = parse(client.get("/api/export/sampling-plan.csv"))
    overview = client.get("/api/overview", params={"stage": "sampling"}).json()
    assert len(rows) == overview["total"] == 3
    assert [r["batch_no"] for r in rows] == [r["batch_no"] for r in overview["rows"]]  # exceptions first


def test_f18_fr07_sampling_plan_columns_and_values(client: TestClient) -> None:
    response = client.get("/api/export/sampling-plan.csv")
    header = response.text.splitlines()[0]
    assert (
        header
        == "material_no,material_desc,batch_no,lot,location,operative_need_by,expected_completion,days_in_stage,tags"
    )
    first = next(r for r in parse(response) if r["batch_no"] == "B1")
    assert (first["lot"], first["location"]) == ("9001", "0100 Onsite")
    assert (first["operative_need_by"], first["expected_completion"], first["days_in_stage"]) == (
        "2026-12-03",
        "2026-10-15",
        "4",
    )


def test_f18_fr07_sampling_plan_honours_the_filters_but_ignores_stage_cards_and_search(
    client: TestClient,
) -> None:
    campaign = parse(client.get("/api/export/sampling-plan.csv", params={"campaign[]": "CMP-ALPHA"}))
    assert [r["batch_no"] for r in campaign] == ["B2"]
    held = parse(client.get("/api/export/sampling-plan.csv", params={"flags[]": "on_hold"}))
    assert [r["batch_no"] for r in held] == ["B3"]
    # A stage card for another stage does not empty the plan; neither does the search text.
    other = parse(client.get("/api/export/sampling-plan.csv", params={"stage": "qc_testing", "q": "zzz"}))
    assert len(other) == 3


def test_f18_fr07_tags_are_joined_with_a_bar(client: TestClient) -> None:
    rows = {r["batch_no"]: r for r in parse(client.get("/api/export/sampling-plan.csv"))}
    assert rows["B3"]["tags"] == "ON HOLD"
    assert rows["B1"]["tags"] == ""


def test_f18_fr07_the_qc_queue_has_qc_ship_and_qc_testing_rows_in_its_own_columns(client: TestClient) -> None:
    response = client.get("/api/export/qc-queue.csv")
    assert response.text.splitlines()[0] == (
        "material_no,batch_no,lot,sample_id,offsite,external_lab,stage,stage_entry,expected_completion,operative_need_by,tags"
    )
    rows = {r["batch_no"]: r for r in parse(response)}
    assert set(rows) == {"B4", "B5"}
    assert rows["B5"]["offsite"] == "true" and rows["B5"]["external_lab"] == "External Lab A"
    assert (rows["B4"]["sample_id"], rows["B4"]["stage_entry"]) == ("S-0000004", "2026-10-05")
    assert rows["B5"]["tags"] == "OFFSITE TEST"
    assert len(rows) == len(
        client.get("/api/overview", params=[("stage", "qc_ship"), ("stage", "qc_testing")]).json()["rows"]
    )


def test_f18_fr07_every_role_may_export(client: TestClient) -> None:
    for user in ("sam", "quinn", "alex", "pat", "admin"):
        for path in ("table", "sampling-plan", "qc-queue"):
            assert client.get(f"/api/export/{path}.csv", headers={"X-Demo-User": user}).status_code == 200


def test_f18_fr07_an_invalid_period_is_a_422(client: TestClient) -> None:
    assert client.get("/api/export/sampling-plan.csv", params={"period": "custom"}).status_code == 422
