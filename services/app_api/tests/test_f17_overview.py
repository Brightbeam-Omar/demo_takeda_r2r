"""F17 T5 [TDD]: in-flight default, repeated stages, released tag, batch count, skip counts, expected deliveries
(F17-FR-04, FR-05, FR-08, FR-10; F17-AC-02, AC-03)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from r2r_core.profile import SiteProfile, load_profile
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import D, batch, load_mirror

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def profile() -> SiteProfile:
    return load_profile("site_a")


def delivery(ebeln: str, scheduled: Any, **over: Any) -> dict[str, Any]:
    row = {
        "ebeln": ebeln, "ebelp": "00010", "material_no": "RM10010", "material_desc": "Excipient 010",
        "molecule_type": "small_molecule", "material_class": "drug_substance", "supplier_id": "SUP001",
        "supplier_name": "Supplier 001", "campaign": "CMP-ALPHA", "scheduled_date": scheduled,
        "quantity": 100, "planned_location": "0100", "planned_location_type": "onsite", "overdue": False,
        "run_id": "run-1",
    }  # fmt: skip
    return row | over


@pytest.fixture(autouse=True)
def mirror(app_factory: sessionmaker[Session], profile: SiteProfile) -> None:
    rows = [
        batch("B1", "RM10010", stage_key="pending", stage_rule_id="R-PND", current_stage_entry_date=None),
        batch("B2", "RM10011", stage_key="receipt", stage_rule_id="R-RCP"),
        batch("B3", "RM10012", stage_key="call_off", stage_rule_id="R-CLO", received_location_type="3pl"),
        batch("B4", "RM10013"),  # onsite sampling: skipped call-off
        batch("B5", "RM10014", received_location_type="3pl"),  # 3pl sampling: call-off done
        batch("B6", "RM10015", stage_key="qc_testing", stage_rule_id="R-QCT", offsite=True),  # offsite
        batch("B7", "RM10016", stage_key="qc_testing", stage_rule_id="R-QCT"),  # onsite: skipped qc ship + call-off
        batch("B8", "RM10017", stage_key="qa_release", stage_rule_id="R-QAR", molecule_type="peptide"),
        batch("B9", "RM10018", stage_key="released", stage_rule_id="R-REL", ud_effective=True, ud_code="A"),
        batch("B9", "RM10018", lot="9002", stage_key="qa_release", stage_rule_id="R-QAR"),  # re-eval of B9
    ]  # fmt: skip
    rows[-1]["lot_type"] = "09"
    reeval = batch("B8", "RM10017", lot="9003", stage_key="sampling", molecule_type="peptide")
    rows.append(reeval | {"lot_type": "09"})  # a second open lot of B8: 10 lots, 9 batches in flight
    deliveries = [
        delivery("4500000001", D(10, 9), overdue=True),
        delivery("4500000002", D(10, 14)),
        delivery(
            "4500000003", D(10, 26), material_no="RM10011", molecule_type="peptide", campaign="CMP-BRAVO"
        ),
        delivery("4500000004", D(11, 20), material_class=None),
    ]
    load_mirror(app_factory, profile, rows, expected_deliveries=deliveries)


def overview(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get("/api/overview", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def lots(client: TestClient, **params: Any) -> list[str]:
    return sorted(f"{r['batch_no']}/{r['lot_type']}" for r in overview(client, **params)["rows"])


# --- F17-FR-10 in-flight default ----------------------------------------------------------------------


def test_f17_fr10_the_default_table_is_in_flight_lots_pending_included(client: TestClient) -> None:
    body = overview(client)
    assert body["total"] == 10
    assert "B9/01" not in lots(client)
    assert "B1/01" in lots(client)  # pending is in flight


def test_f17_fr10_the_batch_count_counts_distinct_material_and_batch(client: TestClient) -> None:
    body = overview(client)
    assert (body["total"], body["batch_count"]) == (10, 9)  # B8 has two open lots
    assert (
        overview(client, include_released="true")["batch_count"] == 9
    )  # B9's released lot is the same batch


def test_f17_fr10_include_released_adds_released_rows(client: TestClient) -> None:
    assert "B9/01" in lots(client, include_released="true")
    assert overview(client, include_released="true")["total"] == 11


def test_f17_fr10_the_released_stage_or_flag_shows_released_rows(client: TestClient) -> None:
    assert lots(client, stage="released") == ["B9/01"]
    assert lots(client, **{"flags[]": "released"}) == ["B9/01"]


def test_f17_fr10_the_flow_strip_still_counts_released(client: TestClient) -> None:
    flow = {e["stage_key"]: e["count"] for e in overview(client)["flow_strip"]}
    assert flow["released"] == 1
    assert sum(count for key, count in flow.items() if key != "released") == 10


def test_f17_fr10_export_follows_the_same_default(client: TestClient) -> None:
    text = client.get("/api/export.csv").text
    assert len(text.strip().splitlines()) == 1 + 10
    assert (
        len(client.get("/api/export.csv", params={"include_released": "true"}).text.strip().splitlines())
        == 12
    )


# --- F17-FR-05 repeated stage --------------------------------------------------------------------------


def test_f17_ac02_repeated_stage_params_are_ored_and_the_cards_do_not_change(client: TestClient) -> None:
    everything = {e["stage_key"]: e["count"] for e in overview(client)["flow_strip"]}
    picked = overview(client, stage=["sampling", "qc_testing"])
    assert sorted(r["batch_no"] for r in picked["rows"]) == ["B4", "B5", "B6", "B7", "B8"]
    assert {e["stage_key"]: e["count"] for e in picked["flow_strip"]} == everything


# --- F17-FR-08 tags -------------------------------------------------------------------------------------


def test_f17_fr08_released_ored_with_another_tag_and_anded_with_stage(client: TestClient) -> None:
    both = lots(client, **{"flags[]": ["released", "offsite"]})
    assert both == ["B6/01", "B9/01"]
    assert lots(client, stage="qc_testing", **{"flags[]": ["released", "offsite"]}) == ["B6/01"]


def test_f17_oq097_release_on_coa_is_accepted_and_matches_no_row(client: TestClient) -> None:
    assert overview(client, **{"flags[]": "release_on_coa"})["rows"] == []


# --- F17-FR-04 skip counts ------------------------------------------------------------------------------


def skips(client: TestClient, **params: Any) -> dict[str, Any]:
    return {e["stage_key"]: e["skip_count"] for e in overview(client, **params)["flow_strip"]}


def test_f17_ac03_skip_counts_cover_rows_past_the_stage_whose_condition_is_false(client: TestClient) -> None:
    found = skips(client)
    # call_off: past it and not received at a 3PL -> B4, B8/09 (sampling), B6, B7 (qc_testing), B8, B9/09 (qa_release)
    assert found["call_off"] == 6
    # qc_ship: past it and not offsite -> B7 (qc_testing), B8 and B9/09 (qa_release); B6 is offsite
    assert found["qc_ship"] == 3
    assert all(
        found[key] is None
        for key in ("pending", "receipt", "sampling", "qc_testing", "qa_release", "released")
    )


def test_f17_oq095_skip_counts_honour_every_filter_except_stage(client: TestClient) -> None:
    assert skips(client, **{"type[]": "peptide"})["call_off"] == 2  # B8 and its re-eval lot
    assert skips(client, stage="receipt")["call_off"] == 6


# --- F17-FR-04 expected deliveries ---------------------------------------------------------------------


def deliveries(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get("/api/expected-deliveries", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_f17_ac01_all_dates_counts_every_open_line_and_is_not_added_to_the_pipeline(
    client: TestClient,
) -> None:
    body = deliveries(client)
    assert (body["count"], body["mode"]) == (4, "snapshot")
    assert [r["ebeln"] for r in body["rows"]] == ["4500000001", "4500000002", "4500000003", "4500000004"]
    assert overview(client)["total"] == 10  # the two are never summed


def test_f17_fr04_a_period_keeps_lines_scheduled_up_to_its_end_overdue_ones_included(
    client: TestClient,
) -> None:
    body = deliveries(client, period="this_week")  # demo today is Mon 12 Oct 2026: window 12-18 Oct
    assert (body["count"], body["mode"]) == (2, "due_in_period")
    assert [r["ebeln"] for r in body["rows"]] == ["4500000001", "4500000002"]
    assert body["overdue_count"] == 1


def test_f17_oq094_type_class_and_campaign_apply_but_stage_and_tags_do_not(client: TestClient) -> None:
    assert [r["ebeln"] for r in deliveries(client, **{"type[]": "peptide"})["rows"]] == ["4500000003"]
    assert [r["ebeln"] for r in deliveries(client, **{"class[]": "unknown"})["rows"]] == ["4500000004"]
    assert [r["ebeln"] for r in deliveries(client, **{"campaign[]": "CMP-BRAVO"})["rows"]] == ["4500000003"]
    assert deliveries(client, stage="sampling", **{"flags[]": "late"})["count"] == 4


def test_f17_fr04_a_delivery_row_has_the_window_columns(client: TestClient) -> None:
    [first, *_] = deliveries(client)["rows"]
    assert set(first) == {
        "ebeln", "ebelp", "material_no", "material_desc", "molecule_type", "material_class", "supplier_id",
        "supplier_name", "campaign", "scheduled_date", "quantity", "planned_location",
        "planned_location_type", "overdue",
    }  # fmt: skip
    assert (first["scheduled_date"], first["quantity"], first["overdue"]) == ("2026-10-09", 100.0, True)
