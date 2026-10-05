"""F09 T3 [TDD]: the Overview: filters, period, order, flow strip, alerts (F09-FR-02, FR-03, AC-04, 05, 08)."""

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from r2r_core.profile import SiteProfile, load_profile
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import NOW, D, batch, load_mirror

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def profile() -> SiteProfile:
    return load_profile("site_a")


def qa(batch_no: str, material: str = "RM10045", **over: Any) -> dict[str, Any]:
    """A lot in QA release since 11 Oct with no need-by (forward plan: due 18 Oct)."""
    row = batch(
        batch_no, material, stage_key="qa_release", stage_rule_id="R-QAR", lims_status="approved",
        current_stage_entry_date=D(10, 11), system_need_by_locked=None, system_need_by_date=None,
        lims_approved_at=NOW - timedelta(hours=2),
    )  # fmt: skip
    return row | over


@pytest.fixture
def mirror(app_factory: sessionmaker[Session], profile: SiteProfile) -> list[dict[str, Any]]:
    rows = [
        batch("B1", "RM10010"),  # sampling, need-by 3 Dec: due 15 Oct
        batch("B2", "RM10011", current_stage_entry_date=D(10, 1), system_need_by_locked=D(10, 5)),  # late
        qa("B3", ud_rejected=True, ud_code="R"),
        qa("B4", on_hold=True, batch_status_code="H"),
        qa("B5", lims_approved_at=NOW - timedelta(hours=30)),  # air gap
        qa("B6", lims_approved_at=NOW - timedelta(hours=40)),  # air gap, older
        qa("B7", material="RM10046", molecule_type="peptide", campaign="CMP-ALPHA"),
        batch("B8", "RM10047", stage_key="released", stage_rule_id="R-REL", ud_effective=True, ud_code="A",
              current_stage_entry_date=D(10, 9), system_need_by_locked=None),
    ]  # fmt: skip
    load_mirror(app_factory, profile, rows)
    return rows


def keys(client: TestClient, **params: Any) -> list[str]:
    response = client.get("/api/overview", params=params)
    assert response.status_code == 200, response.text
    return [row["batch_no"] for row in response.json()["rows"]]


def test_f09_ac04_default_order_is_late_rejected_on_hold_air_gap_then_the_rest(
    client: TestClient, mirror: list[dict[str, Any]]
) -> None:
    assert keys(client) == ["B2", "B3", "B4", "B5", "B6", "B1", "B7", "B8"]


def test_f09_fr02_the_response_shape_and_freshness(client: TestClient, mirror: list[dict[str, Any]]) -> None:
    body = client.get("/api/overview").json()
    assert body["total"] == 8 and body["mode"] == "snapshot" and body["on_hold_count"] == 1
    assert body["freshness"]["contract_run_id"] == "run-1" and body["freshness"]["freshness_minutes"] == 0
    assert body["flow_strip"][0]["stage_key"] == "pending"
    first = body["rows"][0]
    for field in ("operative_need_by", "adjusted_need_by_date", "expedite", "manual_status", "plan",
                  "air_gap", "air_gap_hours", "late", "days_in_stage", "deviation_light", "inbound_light",
                  "flags", "comment_count"):  # fmt: skip
        assert field in first, field


def test_f09_ac05_this_week_includes_overdue_and_excludes_released(
    client: TestClient, mirror: list[dict[str, Any]]
) -> None:
    response = client.get("/api/overview", params={"period": "this_week"}).json()
    names = [r["batch_no"] for r in response["rows"]]
    assert response["mode"] == "due_in_period"
    assert "B2" in names and "B8" not in names  # overdue rolls in, released is out
    assert "B1" in names  # due 15 Oct, inside the week of 12 to 18 Oct
    assert "B7" in names and "B3" in names  # due 18 Oct, the Sunday


def test_f09_fr02_next_week_and_custom_windows(client: TestClient, mirror: list[dict[str, Any]]) -> None:
    assert "B1" in keys(client, period="next_week") and "B8" not in keys(client, period="next_week")
    assert keys(client, period="custom", **{"from": "2026-10-01", "to": "2026-10-14"}) == ["B2"]
    assert client.get("/api/overview", params={"period": "custom"}).status_code == 422
    assert client.get("/api/overview", params={"period": "someday"}).status_code == 422


def test_f09_fr02_filters_are_ored_within_and_anded_across(
    client: TestClient, mirror: list[dict[str, Any]]
) -> None:
    assert keys(client, **{"type[]": "peptide"}) == ["B7"]
    assert set(keys(client, **{"campaign[]": ["CMP-ALPHA", "CMP-BRAVO"]})) == {f"B{n}" for n in range(1, 9)}
    assert keys(client, **{"type[]": "peptide", "campaign[]": "CMP-BRAVO"}) == []
    assert set(keys(client, **{"flags[]": ["on_hold", "ud_rejected"]})) == {"B3", "B4"}
    assert keys(client, q="b7") == ["B7"] and keys(client, q="RM10046") == ["B7"]
    assert client.get("/api/overview", params={"flags[]": "bogus"}).status_code == 422


def test_f09_fr02_the_flow_strip_ignores_the_stage_filter_and_marks_breaches(
    client: TestClient, mirror: list[dict[str, Any]]
) -> None:
    body = client.get("/api/overview", params={"stage": "qa_release"}).json()
    strip = {e["stage_key"]: e for e in body["flow_strip"]}
    assert strip["sampling"]["count"] == 2 and strip["sampling"]["breached"]  # B1, B2 (B2 is late)
    assert strip["qa_release"]["count"] == 5 and not strip["qa_release"]["breached"]
    assert (
        strip["sampling"]["late_count"] == 1 and strip["qa_release"]["late_count"] == 0
    )  # F10 review: "N late" on the card
    assert strip["released"]["count"] == 1
    assert body["total"] == 5 and {r["stage_key"] for r in body["rows"]} == {"qa_release"}


def test_f09_fr03_alerts_count_air_gaps_late_on_hold_and_rejected(
    client: TestClient, mirror: list[dict[str, Any]]
) -> None:
    alerts = {a["kind"]: a for a in client.get("/api/overview").json()["alerts"]}
    assert [r["batch_no"] for r in alerts["air_gap"]["rows"]] == ["B6", "B5"]  # oldest first
    assert alerts["air_gap"]["count"] == 2 and alerts["air_gap"]["rows"][0]["air_gap_hours"] == 40
    assert alerts["late"]["count"] == 1 and alerts["on_hold"]["count"] == 1
    assert alerts["rejected"]["count"] == 1 and alerts["rejected"]["detail"] == {
        "ud_rejected": 1,
        "lims_rejected": 0,
    }


def test_f09_ac08_b5003_is_an_air_gap_alert_with_at_least_30_hours(
    client: TestClient, app_factory: sessionmaker[Session], profile: SiteProfile
) -> None:
    load_mirror(app_factory, profile, [qa("B5003", "RM10067", lims_approved_at=NOW - timedelta(hours=30))])
    alert = next(a for a in client.get("/api/overview").json()["alerts"] if a["kind"] == "air_gap")
    assert [r["batch_no"] for r in alert["rows"]] == ["B5003"] and alert["rows"][0]["air_gap_hours"] >= 30


def test_f09_fr02_an_empty_mirror_gives_an_empty_overview(client: TestClient) -> None:
    body = client.get("/api/overview").json()
    assert body["total"] == 0 and body["rows"] == [] and body["freshness"]["contract_run_id"] is None


def test_f09_fr03_the_air_gap_alert_lists_at_most_five_rows(
    client: TestClient, app_factory: sessionmaker[Session], profile: SiteProfile
) -> None:
    rows = [qa(f"G{n}", lims_approved_at=NOW - timedelta(hours=30 + n)) for n in range(7)]
    load_mirror(app_factory, profile, rows)
    alert = next(a for a in client.get("/api/overview").json()["alerts"] if a["kind"] == "air_gap")
    assert alert["count"] == 7 and [r["batch_no"] for r in alert["rows"]] == ["G6", "G5", "G4", "G3", "G2"]


def test_f09_fr02_last_week_and_this_month_windows(client: TestClient, mirror: list[dict[str, Any]]) -> None:
    # the demo Monday is 12 Oct: last week ended on Sunday 11 Oct, so only the overdue lot is in
    assert keys(client, period="last_week") == ["B2"]
    # this month ends on 31 Oct: everything due in October and not released is in
    assert set(keys(client, period="this_month")) == {"B1", "B2", "B3", "B4", "B5", "B6", "B7"}


def test_f15_oq079_last_and_next_month_windows(client: TestClient, mirror: list[dict[str, Any]]) -> None:
    # past windows keep the same rule (expected completion on or before the window end, not released); the
    # latest lot here was due on 8 Oct, so nothing was due by the end of September
    assert keys(client, period="last_month") == []
    assert set(keys(client, period="next_month")) >= set(keys(client, period="this_month"))
    assert client.get("/api/overview", params={"period": "soon"}).status_code == 422


def test_f09_fr02_weeks_follow_the_site_date_not_the_utc_date(
    client: TestClient, mirror: list[dict[str, Any]]
) -> None:
    from datetime import UTC, datetime

    from r2r_core import clock
    from r2r_core.clock import FixedClock

    # Sunday 18 Oct 23:30 UTC is already Monday 19 Oct in the site timezone (summer time ended on 25 Oct)
    clock.set_clock_source(FixedClock(datetime(2026, 10, 18, 23, 30, tzinfo=UTC)))
    names = keys(client, period="this_week")
    assert "B1" in names and "B7" in names  # due 15 and 18 Oct: overdue by the new Monday, still rolled in
    assert {"B1", "B2", "B7"} <= set(keys(client, period="last_week"))  # the window ends on Sunday 18 Oct
    assert "B8" not in names
