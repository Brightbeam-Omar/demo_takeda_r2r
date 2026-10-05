"""F16 T6 [TDD]: the adjusted needs-by and insights windows' endpoints (F16-FR-06..09, OQ-087, 088, 090)."""

from datetime import timedelta
from typing import Any

import pytest
from app_api.services import store
from fastapi.testclient import TestClient
from r2r_core import clock
from r2r_core.clock import FixedClock
from r2r_core.profile import SiteProfile, load_profile
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import NOW, D, batch, load_mirror

pytestmark = pytest.mark.integration

PULL = {"adjusted_date": "2026-11-26", "reason_code": "CAMPAIGN_PULLED_FORWARD", "note": "moved"}


@pytest.fixture(scope="module")
def profile() -> SiteProfile:
    return load_profile("site_a")


def qa(batch_no: str, material: str, hours: int | None, **over: Any) -> dict[str, Any]:
    """A lot in QA release; with ``hours`` it is approved by the lab that long ago and not yet in the ERP."""
    row = batch(
        batch_no, material, stage_key="qa_release", stage_rule_id="R-QAR", current_stage_entry_date=D(10, 11),
        system_need_by_locked=None, system_need_by_date=None,
        lims_status="approved" if hours is not None else "none",
        lims_approved_at=NOW - timedelta(hours=hours) if hours is not None else None,
    )  # fmt: skip
    return row | over


@pytest.fixture
def mirror(app_factory: sessionmaker[Session], profile: SiteProfile) -> None:
    rows = [
        batch("B2077", "RM10031"),  # sampling, system need-by 3 Dec
        batch("B2", "RM10032", campaign="CMP-ALPHA", system_need_by_locked=D(12, 10)),
        qa("B3", "RM10033", None, campaign="CMP-ALPHA", system_need_by_locked=D(12, 1)),
        batch("B4", "RM10034", stage_key="released", stage_rule_id="R-REL", ud_effective=True, ud_code="A",
              current_stage_entry_date=D(10, 9), system_need_by_locked=D(12, 5)),
        qa("B5003", "RM10035", 25),  # 1 d
        qa("B5001", "RM10036", 100, campaign="CMP-ALPHA"),  # 4 d
        qa("B5002", "RM10037", 60),  # 2 d
        qa("B5009", "RM10038", 23),  # under the 24 h threshold: not an air gap
    ]  # fmt: skip
    load_mirror(app_factory, profile, rows)


def key(batch_no: str, material: str) -> str:
    return f"{material}|{batch_no}|9001"


def adjust(client: TestClient, batch_no: str, material: str, user: str = "pat", **body: Any) -> None:
    response = client.put(
        f"/api/rows/{key(batch_no, material)}/need-by", json=PULL | body, headers={"X-Demo-User": user}
    )
    assert response.status_code == 200, response.text


def adjusted(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get("/api/overview/adjusted", params=params)
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def insights(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get("/api/overview/insights", params=params)
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


# --- adjusted needs-by (FR-06, FR-07) --------------------------------------------------------------------


@pytest.mark.usefixtures("mirror")
def test_f16_ac04_a_pull_forward_lists_delta_reason_label_and_who_set_it(client: TestClient) -> None:
    assert adjusted(client) == {"total": 0, "rows": []}
    adjust(client, "B2077", "RM10031")
    body = adjusted(client)
    assert body["total"] == 1
    entry = body["rows"][0]
    assert entry["batch_no"] == "B2077" and entry["material_no"] == "RM10031"
    assert entry["material_desc"] == "Material RM10031"
    assert (entry["system_need_by_date"], entry["adjusted_date"], entry["delta_days"]) == (
        "2026-12-03", "2026-11-26", -7,
    )  # fmt: skip
    assert (entry["reason_code"], entry["reason_label"]) == (
        "CAMPAIGN_PULLED_FORWARD",
        "Campaign Pulled Forward",
    )
    assert entry["set_by"] == "Pat"  # app_user.display_name, not the user_key


@pytest.mark.usefixtures("mirror")
def test_f16_fr07_a_push_out_has_a_positive_delta(client: TestClient) -> None:
    adjust(client, "B2", "RM10032", adjusted_date="2026-12-15", reason_code="CAMPAIGN_PUSHED_OUT")
    assert adjusted(client)["rows"][0]["delta_days"] == 5


@pytest.mark.usefixtures("mirror")
def test_f16_oq090_newest_override_first_and_set_by_is_that_versions_author(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    adjust(client, "B2077", "RM10031", user="pat")
    clock.set_clock_source(FixedClock(NOW + timedelta(minutes=5)))
    store.clear_cache()
    adjust(client, "B2", "RM10032", user="admin", adjusted_date="2026-12-01")
    assert [(r["batch_no"], r["set_by"]) for r in adjusted(client)["rows"]] == [
        ("B2", "Admin"),
        ("B2077", "Pat"),
    ]

    # A newer version of the older row moves it to the top, and Set By follows the author of that version.
    clock.set_clock_source(FixedClock(NOW + timedelta(minutes=10)))
    store.clear_cache()
    adjust(client, "B2077", "RM10031", user="admin", adjusted_date="2026-11-20")
    assert [(r["batch_no"], r["set_by"]) for r in adjusted(client)["rows"]] == [
        ("B2077", "Admin"),
        ("B2", "Admin"),
    ]


@pytest.mark.usefixtures("mirror")
def test_f16_fr06_a_cleared_adjustment_is_not_listed(client: TestClient) -> None:
    adjust(client, "B2077", "RM10031")
    cleared = client.put(f"/api/rows/{key('B2077', 'RM10031')}/need-by", json={"adjusted_date": None})
    assert cleared.status_code == 200
    assert adjusted(client)["total"] == 0


@pytest.mark.usefixtures("mirror")
def test_f16_fr06_released_rows_are_not_counted(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    with app_factory() as session:  # the API refuses to adjust a released row, so write the version directly
        session.execute(
            text(
                "INSERT INTO override_value (row_key, field, value_json, reason_code, version, "
                "author_user_key, created_at, is_current) VALUES (:k, 'adjusted_need_by_date', "
                "CAST('\"2026-11-26\"' AS jsonb), 'CAMPAIGN_PULLED_FORWARD', 1, 'pat', :at, true)"
            ),
            {"k": key("B4", "RM10034"), "at": NOW},
        )
        session.commit()
    store.clear_cache()
    assert adjusted(client)["total"] == 0
    assert client.get("/api/overview").json()["adjusted_count"] == 0


@pytest.mark.usefixtures("mirror")
def test_f16_fr06_every_filter_applies_except_stage(client: TestClient) -> None:
    adjust(client, "B2077", "RM10031")  # sampling, CMP-BRAVO
    adjust(client, "B2", "RM10032", adjusted_date="2026-12-01")  # sampling, CMP-ALPHA
    adjust(client, "B3", "RM10033", adjusted_date="2026-11-20")  # qa_release, CMP-ALPHA

    assert adjusted(client)["total"] == 3
    assert adjusted(client, stage="sampling")["total"] == 3  # the stage filter does not narrow it (OQ-059(5))
    assert sorted(r["batch_no"] for r in adjusted(client, **{"campaign[]": "CMP-ALPHA"})["rows"]) == [
        "B2",
        "B3",
    ]
    assert adjusted(client, q="B2077")["total"] == 1
    assert adjusted(client, **{"class[]": "consumable"})["total"] == 0


@pytest.mark.usefixtures("mirror")
def test_f16_oq087_bookmarked_narrows_the_adjusted_list_and_count(client: TestClient) -> None:
    adjust(client, "B2077", "RM10031")
    adjust(client, "B2", "RM10032", adjusted_date="2026-12-01")
    client.post(f"/api/bookmarks/{key('B2', 'RM10032')}")
    body = adjusted(client, bookmarked="true")
    assert [r["batch_no"] for r in body["rows"]] == ["B2"]
    assert client.get("/api/overview", params={"bookmarked": "true"}).json()["adjusted_count"] == 1
    assert client.get("/api/overview").json()["adjusted_count"] == 2


@pytest.mark.usefixtures("mirror")
def test_f16_fr06_the_overview_count_matches_the_list_under_the_same_filters(client: TestClient) -> None:
    adjust(client, "B2077", "RM10031")
    adjust(client, "B2", "RM10032", adjusted_date="2026-12-01")
    for params in ({}, {"campaign[]": "CMP-ALPHA"}, {"stage": "qa_release"}):
        assert (
            client.get("/api/overview", params=params).json()["adjusted_count"]
            == adjusted(client, **params)["total"]
        )


@pytest.mark.usefixtures("mirror")
def test_f16_fr07_a_viewer_may_read_the_window(client: TestClient) -> None:
    adjust(client, "B2077", "RM10031")
    response = client.get("/api/overview/adjusted", headers={"X-Demo-User": "sam"})
    assert response.status_code == 200 and response.json()["total"] == 1


# --- insights (FR-08, FR-09) -----------------------------------------------------------------------------


@pytest.mark.usefixtures("mirror")
def test_f16_ac05_every_air_gap_row_worst_first_with_whole_days(client: TestClient) -> None:
    body = insights(client)
    assert body["total"] == 3  # B5009 is under the 24 h threshold, so it is not an air gap (OQ-088)
    assert [(r["batch_no"], r["days_gap"]) for r in body["rows"]] == [
        ("B5001", 4),
        ("B5002", 2),
        ("B5003", 1),
    ]
    first = body["rows"][0]
    assert (first["material_no"], first["material_desc"]) == ("RM10036", "Material RM10036")
    assert (first["stage_key"], first["stage_label"], first["air_gap_hours"]) == (
        "qa_release",
        "QA Release",
        100,
    )


@pytest.mark.usefixtures("mirror")
def test_f16_oq088_the_smallest_gap_is_one_day(client: TestClient) -> None:
    assert min(r["days_gap"] for r in insights(client)["rows"]) == 1


@pytest.mark.usefixtures("mirror")
def test_f16_fr09_there_is_no_cap_of_five(
    client: TestClient, app_factory: sessionmaker[Session], profile: SiteProfile
) -> None:
    many = [qa(f"BX{n}", f"RM2{n:04d}", 30 + n) for n in range(8)]
    load_mirror(app_factory, profile, many)
    store.clear_cache()
    assert insights(client)["total"] == 8
    assert len(insights(client)["rows"]) == 8
    top = client.get("/api/overview").json()["alerts"][0]
    assert (
        top["kind"] == "air_gap" and top["count"] == 8 and len(top["rows"]) == 5
    )  # the F10 band keeps its top 5


@pytest.mark.usefixtures("mirror")
def test_f16_fr08_the_count_matches_the_overview_alert_and_filters_except_stage_apply(
    client: TestClient,
) -> None:
    alert = next(a for a in client.get("/api/overview").json()["alerts"] if a["kind"] == "air_gap")
    assert insights(client)["total"] == alert["count"] == 3
    assert insights(client, stage="sampling")["total"] == 3  # stage is ignored
    only_alpha = insights(client, **{"campaign[]": "CMP-ALPHA"})
    assert [r["batch_no"] for r in only_alpha["rows"]] == ["B5001"]


@pytest.mark.usefixtures("mirror")
def test_f16_ac06_a_campaign_without_air_gaps_has_none(client: TestClient) -> None:
    assert insights(client, **{"campaign[]": "CMP-NONE"}) == {"total": 0, "rows": []}


@pytest.mark.usefixtures("mirror")
def test_f16_oq087_bookmarked_narrows_the_insights(client: TestClient) -> None:
    client.post(f"/api/bookmarks/{key('B5002', 'RM10037')}")
    assert [r["batch_no"] for r in insights(client, bookmarked="true")["rows"]] == ["B5002"]
    alert = next(
        a
        for a in client.get("/api/overview", params={"bookmarked": "true"}).json()["alerts"]
        if a["kind"] == "air_gap"
    )
    assert alert["count"] == 1


def test_f16_fr09_the_reference_carries_the_air_gap_threshold_for_the_window_text(client: TestClient) -> None:
    assert client.get("/api/reference").json()["air_gap_threshold_hours"] == 24
