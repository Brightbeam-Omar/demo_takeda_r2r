"""F09 T5: row detail, metrics, reference, audit and export (F09-AC-10)."""

import csv
import io
from typing import Any

import pytest
from fastapi.testclient import TestClient
from r2r_core.profile import SiteProfile, load_profile
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import RUN, D, batch, load_mirror

pytestmark = pytest.mark.integration

ROW = "RM10031|B2077|9001"


@pytest.fixture(scope="module")
def profile() -> SiteProfile:
    return load_profile("site_a")


@pytest.fixture
def mirror(app_factory: sessionmaker[Session], profile: SiteProfile) -> None:
    rows = [
        batch(),
        batch("B2077", lot="9002", lot_type="09", re_eval=True, stage_key="released", ud_effective=True,
              current_stage_entry_date=D(9, 1), system_need_by_locked=None),
        batch("B3150", "RM10045", campaign="CMP-CEDAR", molecule_type="peptide"),
    ]  # fmt: skip
    deviations = [
        {"deviation_no": "DEV-1", "material_no": "RM10031", "batch_no": "B2077", "title": "Odd result",
         "severity": "major", "status": "open", "opened_on": D(10, 1), "closed_on": None,
         "root_cause_category": None, "owner": "owner-1"},
    ]  # fmt: skip
    weeks = [
        {"metric_id": "M3", "week_start": D(10, 5), "completed": 10, "on_time": 9, "pct": "90.0", "run_id": RUN},
        {"metric_id": "M3", "week_start": D(9, 28), "completed": 10, "on_time": 8, "pct": "80.0", "run_id": RUN},
        {"metric_id": "M3", "week_start": D(9, 21), "completed": 10, "on_time": 5, "pct": "50.0", "run_id": RUN},
        {"metric_id": "M3", "week_start": D(9, 14), "completed": 0, "on_time": 0, "pct": None, "run_id": RUN},
    ]  # fmt: skip
    load_mirror(app_factory, profile, rows, deviations=deviations, metrics=weeks)


def test_f09_fr01_row_detail_has_facts_overrides_comments_deviations_and_siblings(
    client: TestClient, mirror: None
) -> None:
    client.put(
        f"/api/rows/{ROW}/need-by",
        json={"adjusted_date": "2026-11-26", "reason_code": "SUPPLIER_DELAY", "note": "n"},
    )
    client.put(
        f"/api/rows/{ROW}/need-by", json={"adjusted_date": "2026-11-20", "reason_code": "SUPPLIER_DELAY"}
    )
    client.post(f"/api/rows/{ROW}/status-log", json={"status": "on_track", "comment": "first"})
    detail = client.get(f"/api/rows/{ROW}").json()
    assert detail["facts"]["row_key"] == ROW and detail["facts"]["stage_rule_id"] == "R-SMP"
    assert detail["freshness"]["contract_run_id"] == RUN
    assert detail["current_overrides"]["adjusted_need_by_date"]["version"] == 2
    assert [o["version"] for o in detail["override_history"]] == [2, 1]
    assert [c["comment"] for c in detail["status_log"]] == ["first"] and detail["status_log_count"] == 1
    assert [d["deviation_no"] for d in detail["deviations"]] == ["DEV-1"]
    assert [s["row_key"] for s in detail["siblings"]] == ["RM10031|B2077|9002"]  # the batch's other lot
    assert detail["plan"]["compressed"] is True and detail["operative_need_by"] == "2026-11-20"


def test_f09_fr01_an_unknown_row_is_404(client: TestClient, mirror: None) -> None:
    assert client.get("/api/rows/NOPE%7CX%7C1").status_code == 404


def test_f09_fr07_metrics_carry_weeks_colours_and_awaiting_signal(client: TestClient, mirror: None) -> None:
    body = client.get("/api/metrics").json()
    assert body["filtered"] is False and body["freshness"]["contract_run_id"] == RUN
    assert body["week_starts"] == ["2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05"]
    by_id = {m["metric_id"]: m for m in body["metrics"]}
    assert [w["rag"] for w in by_id["M3"]["weeks"]] == [None, "red", "amber", "green"]
    assert by_id["M1"]["status"] == "awaiting_signal" and by_id["M1"]["weeks"] == []
    assert "3PL" in by_id["M1"]["null_reason"]


def test_f09_endpoint_reference_lists_the_filter_values(client: TestClient, mirror: None) -> None:
    body = client.get("/api/reference").json()
    assert body["stages"][0]["stage_key"] == "pending" and body["stages"][-1]["terminal"] is True
    assert body["campaigns"] == ["CMP-BRAVO", "CMP-CEDAR"] and body["site_name"] and body["site_timezone"]
    assert "CAMPAIGN_PULLED_FORWARD" in [c["code"] for c in body["reason_codes"]]
    assert [t["key"] for t in body["molecule_types"]] == ["small_molecule", "large_molecule", "peptide"]
    assert body["terms"]["erp_blocked_tag"] == "SAP BLOCKED"
    assert body["release_badge"] == "ALPHA – LOCAL"
    assert {m["metric_id"] for m in body["metrics"]} >= {"M1", "M7"}


def test_f09_endpoint_audit_is_paginated_newest_first_and_filterable(
    client: TestClient, mirror: None
) -> None:
    for text_ in ("a", "b", "c"):
        client.post(f"/api/rows/{ROW}/status-log", json={"status": "on_track", "comment": text_})
    client.post(
        f"/api/rows/{ROW}/status-log",
        json={"status": "blocked", "comment": "x"},
        headers={"X-Demo-User": "quinn"},
    )
    page = client.get("/api/audit", params={"limit": 2}).json()
    assert page["total"] == 4 and [i["action"] for i in page["items"]] == ["status_logged", "status_logged"]
    rest = client.get("/api/audit", params={"limit": 2, "offset": 2}).json()["items"]
    assert [i["id"] for i in rest] == [2, 1]
    assert client.get("/api/audit", params={"actor": "quinn"}).json()["total"] == 1
    assert client.get("/api/audit", params={"action": "status_logged"}).json()["total"] == 4
    assert client.get("/api/audit", params={"row_key": "other"}).json()["total"] == 0
    assert client.get("/api/audit", params={"limit": 500}).status_code == 422


def parse(response: Any) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(response.text)))


def test_f09_ac10_export_rows_match_the_overview_total_with_the_same_filters(
    client: TestClient, mirror: None
) -> None:
    client.put(
        f"/api/rows/{ROW}/need-by", json={"adjusted_date": "2026-11-26", "reason_code": "SUPPLIER_DELAY"}
    )
    for params in ({}, {"type[]": "peptide"}, {"period": "this_week"}, {"stage": "released"}):
        total = client.get("/api/overview", params=params).json()["total"]
        response = client.get("/api/export.csv", params=params)
        assert response.headers["content-type"].startswith("text/csv")
        assert len(parse(response)) == total, params
    row = next(r for r in parse(client.get("/api/export.csv")) if r["row_key"] == ROW)
    assert (row["system_need_by_date"], row["adjusted_need_by_date"], row["operative_need_by"]) == (
        "2026-12-03",
        "2026-11-26",
        "2026-11-26",
    )
