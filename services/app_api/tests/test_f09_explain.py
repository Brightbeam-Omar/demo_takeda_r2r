"""F09 T6 [TDD]: the Explain payloads (F09-FR-06, F09-AC-06, F09-AC-07)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from r2r_core.profile import SiteProfile, load_profile
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import RUN, D, batch, load_mirror

pytestmark = pytest.mark.integration

B1042 = "RM10023|B1042|9000"
B2077 = "RM10031|B2077|9001"
REFS = {"erp": {"mcha": "RM10023|B1042", "qals": "9000", "mseg": ["4900001234"]}, "lims": {"sample": "S-1"}}


@pytest.fixture
def mirror(app_factory: sessionmaker[Session]) -> SiteProfile:
    profile = load_profile("site_a")
    rows = [
        batch("B1042", "RM10023", lot="9000", stage_key="qc_testing", stage_rule_id="R-QCT", lims_status="in_progress",
              sample_collected_date=D(9, 2), current_stage_entry_date=D(9, 2), source_refs_json=REFS,
              system_need_by_locked=D(10, 21)),
        batch(),
        batch("B3", "RM10040", stage_key="qc_testing", stage_rule_id="R-QCT", lims_status="in_progress",
              sample_collected_date=D(9, 2), current_stage_entry_date=D(9, 2), system_need_by_locked=None),
        batch("B4", "RM10041", stage_key="sampling", system_need_by_locked=None),
        batch("B5", "RM10042", stage_key="released", stage_rule_id="R-REL", ud_effective=True, ud_code="A",
              current_stage_entry_date=D(10, 9), system_need_by_locked=None),
    ]  # fmt: skip
    metric_rows = [
        {"metric_id": "M3", "week_start": D(10, 5), "row_key": f"R|B{n}|1", "entry_date": D(10, 1),
         "exit_date": D(10, 6), "duration_days": 5, "sla_days": 7, "on_time": n != 3, "run_id": RUN}
        for n in range(1, 5)
    ]  # fmt: skip
    metrics = [
        {"metric_id": "M3", "week_start": D(10, 5), "completed": 4, "on_time": 3, "pct": "75.0", "run_id": RUN},
        {"metric_id": "M3", "week_start": D(9, 28), "completed": 0, "on_time": 0, "pct": None, "run_id": RUN},
    ]  # fmt: skip
    load_mirror(app_factory, profile, rows, metrics=metrics, metric_rows=metric_rows)
    return profile


def explain(client: TestClient, row: str, field: str) -> dict[str, Any]:
    response = client.get(f"/api/rows/{row}/explain", params={"field": field})
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def test_f09_ac06_stage_explain_for_b1042_names_rule_r_qct_with_values_and_refs(
    client: TestClient, mirror: SiteProfile
) -> None:
    body = explain(client, B1042, "stage")
    assert body["kind"] == "stage" and body["rule"]["id"] == "R-QCT" and body["stage_label"] == "QCL Testing"
    assert "lims_status" in body["rule"]["condition_sql"] and body["rule"]["description"]
    assert body["rule"]["inputs"] == [
        "lims_status",
        "offsite_test",
        "sample_collected_date",
        "sample_shipped_date",
    ]
    assert body["input_values"] == {
        "lims_status": "in_progress", "offsite_test": None, "sample_collected_date": "2026-09-02",
        "sample_shipped_date": None,
    }  # fmt: skip
    assert body["source_refs"] == REFS
    assert body["freshness"]["contract_run_id"] == RUN and body["freshness"]["last_success_at"]


def test_f09_fr06_stage_explain_shows_the_published_derived_inputs(
    client: TestClient, mirror: SiteProfile
) -> None:
    body = explain(client, B2077, "stage")
    assert body["rule"]["id"] == "R-SMP" and body["input_values"] == {"cycle_start_date": "2026-10-02"}
    released = explain(client, "RM10042|B5|9001", "stage")
    assert released["input_values"] == {"ud_effective": True}


def test_f09_fr06_expected_completion_explains_the_plan_inputs_and_the_formula(
    client: TestClient, mirror: SiteProfile
) -> None:
    plain = explain(client, B2077, "expected_completion")
    assert plain["entry_date"] == "2026-10-08" and plain["need_by_adjusted"] is False
    assert (plain["available_days"], plain["budget_days"], plain["compressed"]) == (56, 56, False)
    assert plain["base_slas"] == {"sampling": 7, "qc_testing": 42, "qa_release": 7}
    assert plain["expected_completion"] == "2026-10-15" and "full SLAs" in plain["formula"]

    client.put(
        f"/api/rows/{B2077}/need-by",
        json={"adjusted_date": "2026-11-26", "reason_code": "CAMPAIGN_PULLED_FORWARD"},
    )
    squeezed = explain(client, B2077, "expected_completion")
    assert squeezed["need_by_adjusted"] and squeezed["adjusted_reason_code"] == "CAMPAIGN_PULLED_FORWARD"
    assert squeezed["system_need_by"] == "2026-12-03" and squeezed["operative_need_by"] == "2026-11-26"
    assert squeezed["effective_slas"] == {"sampling": 6, "qc_testing": 37, "qa_release": 6}
    assert squeezed["compression_ratio"] == "0.875" and "49/56" in squeezed["formula"]
    assert squeezed["applicable_slas"] is not None


def test_f09_fr06_the_formula_covers_forward_overdue_and_no_plan(
    client: TestClient, mirror: SiteProfile
) -> None:
    assert "forward" in explain(client, "RM10041|B4|9001", "expected_completion")["formula"]
    client.put(
        f"/api/rows/{B1042}/need-by", json={"adjusted_date": "2026-09-01", "reason_code": "SUPPLIER_DELAY"}
    )
    late = explain(client, B1042, "expected_completion")
    assert "already late" in late["formula"]
    released = explain(client, "RM10042|B5|9001", "expected_completion")
    assert released["expected_completion"] is None and "No expected completion" in released["formula"]


def test_f09_fr06_unknown_rows_and_fields(client: TestClient, mirror: SiteProfile) -> None:
    assert client.get("/api/rows/NOPE%7CX%7C1/explain", params={"field": "stage"}).status_code == 404
    assert client.get(f"/api/rows/{B2077}/explain", params={"field": "colour"}).status_code == 422
    assert client.get("/api/explain", params={"field": "other:1"}).status_code == 422


def test_f09_ac07_metric_explain_lists_the_contributing_rows(client: TestClient, mirror: SiteProfile) -> None:
    body = client.get("/api/explain", params={"field": "metric:M3", "week": "2026-10-05"}).json()
    assert body["kind"] == "metric" and (body["completed"], body["on_time"], body["pct"]) == (4, 3, "75.0")
    assert len(body["rows"]) == body["completed"] == 4
    assert sum(r["on_time"] for r in body["rows"]) == body["on_time"]
    assert client.get("/api/explain", params={"field": "metric:M3", "week": "2026-01-05"}).status_code == 404
    assert client.get("/api/explain", params={"field": "metric:M9"}).status_code == 404


def test_f09_fr06_a_metric_without_a_signal_returns_its_reason_and_no_rows(
    client: TestClient, mirror: SiteProfile
) -> None:
    body = client.get("/api/explain", params={"field": "metric:M1"}).json()
    assert body["status"] == "awaiting_signal" and "3PL" in body["null_reason"] and body["rows"] == []


def test_f09_fr06_the_current_week_is_the_default_for_a_metric(
    client: TestClient, mirror: SiteProfile
) -> None:
    body = client.get("/api/explain", params={"field": "metric:M3"})
    assert body.status_code == 404  # the demo week (12 Oct) is not among the published fixture weeks


def test_f09_fr06_flow_explain_matches_the_flow_strip_and_lists_rules_and_rows(
    client: TestClient, mirror: SiteProfile
) -> None:
    body = client.get("/api/explain", params={"field": "flow:qc_testing"}).json()
    strip = {e["stage_key"]: e for e in client.get("/api/overview").json()["flow_strip"]}
    assert (
        body["count"] == strip["qc_testing"]["count"] == 2
        and body["breached"] == strip["qc_testing"]["breached"]
    )
    assert sorted(body["row_keys"]) == sorted([B1042, "RM10040|B3|9001"])
    assert body["mode"] == "snapshot" and [r["id"] for r in body["rules"]] == ["R-QCT"]
    due = client.get("/api/explain", params={"field": "flow:released", "period": "this_week"}).json()
    assert due["mode"] == "due_in_period" and due["count"] == 0 and due["filters"]["period"] == "this_week"
    assert client.get("/api/explain", params={"field": "flow:nowhere"}).status_code == 404
