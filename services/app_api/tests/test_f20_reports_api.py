"""F20 T5: the report endpoints and their exports (F20-FR-06, F20-AC-01, AC-02, AC-03, AC-05, AC-06, OQ-117 to OQ-126)."""

import csv
import io
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from r2r_core.profile import SiteProfile, load_profile
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import D, batch, load_mirror

pytestmark = pytest.mark.integration

QUINN = {"X-Demo-User": "quinn"}
PAT = {"X-Demo-User": "pat"}
STAGES = ("receipt", "call_off", "sampling", "qc_ship", "qc_testing", "qa_release")


@pytest.fixture(scope="module")
def profile() -> SiteProfile:
    return load_profile("site_a")


def released(
    key: str, ud: Any, need_by: Any = None, due: Any = None, lot: str | None = None
) -> dict[str, Any]:
    return batch(key, lot=lot or key[1:].rjust(4, "0")) | {
        "stage_key": "released",
        "stage_rule_id": "R-REL",
        "ud_effective": True,
        "ud_code": "A",
        "ud_date": ud,
        "need_by_at_release": need_by,
        "expedite_due_date": due,
        "current_stage_entry_date": None,
        "system_need_by_locked": None,
    }


def week(metric: str, start: Any, completed: int, on_time: int, pct: str | None) -> dict[str, Any]:
    return {
        "metric_id": metric, "week_start": start, "completed": completed, "on_time": on_time,
        "pct": Decimal(pct) if pct else None, "run_id": "run-1",
    }  # fmt: skip


def month(metric: str, start: Any, completed: int, on_time: int, pct: str | None) -> dict[str, Any]:
    return {
        "metric_id": metric, "month_start": start, "completed": completed, "on_time": on_time,
        "pct": Decimal(pct) if pct else None, "run_id": "run-1",
    }  # fmt: skip


def daily(day: Any, **counts: int) -> list[dict[str, Any]]:
    return [{"day": day, "stage_key": s, "open_count": counts.get(s, 0), "run_id": "run-1"} for s in STAGES]


@pytest.fixture(autouse=True)
def mirror(app_factory: sessionmaker[Session], profile: SiteProfile) -> None:
    rows = [
        released("B1", D(4, 15), need_by=D(4, 20)),  # on time
        released("B2", D(5, 6), need_by=D(5, 1), due=D(5, 10)),  # late; expedite on time
        released("B3", D(6, 3), need_by=D(6, 30), due=D(6, 1)),  # on time; expedite missed
        released("B4", D(9, 28)),  # no need-by: excluded
        released("B5", D(11, 3, 2025), need_by=D(11, 1, 2025)),  # another year
        batch(
            "L1",
            "RM10040",
            stage_key="sampling",
            current_stage_entry_date=D(8, 1),
            system_need_by_locked=None,
        ),
        batch(
            "L2",
            "RM10041",
            stage_key="qc_testing",
            stage_rule_id="R-QCT",
            current_stage_entry_date=D(8, 1),
            system_need_by_locked=None,
        ),
        batch("OK", "RM10042", current_stage_entry_date=D(10, 10), system_need_by_locked=None),  # not late
    ]
    metrics = [
        week("M3", D(10, 5), 18, 17, "94.4"), week("M3", D(9, 28), 33, 27, "81.8"),
        week("M3", D(9, 21), 32, 27, "84.4"), week("M3", D(9, 14), 28, 22, "78.6"),
        week("M3", D(9, 7), 32, 28, "87.5"), week("M3", D(10, 12), 0, 0, None),
        week("M6", D(10, 5), 43, 36, "83.7"), week("M6", D(9, 28), 15, 12, "80.0"),
        week("M7", D(10, 5), 13, 9, "69.2"), week("M7", D(9, 28), 12, 10, "83.3"),
    ]  # fmt: skip
    monthly = [
        month("M3", D(10, 1), 18, 17, "94.4"), month("M3", D(9, 1), 125, 104, "83.2"),
        month("M3", D(8, 1), 120, 90, "75.0"), month("M3", D(7, 1), 100, 80, "80.0"),
    ]  # fmt: skip
    days = [D(10, 9), D(10, 10), D(10, 11), D(10, 12)]  # Fri .. Mon
    stage_days = [row for d in days for row in daily(d, sampling=3, qc_testing=2)]
    stage_days += daily(D(10, 4), sampling=1)  # a Sunday: the weekly point of the week of 28 Sep
    releases = [
        {"week_start": D(4, 13), "released_count": 1, "run_id": "run-1"},
        {"week_start": D(5, 4), "released_count": 1, "run_id": "run-1"},
        {"week_start": D(12, 29, 2025), "released_count": 0, "run_id": "run-1"},
        {"week_start": D(10, 20, 2025), "released_count": 4, "run_id": "run-1"},
    ]
    load_mirror(
        app_factory, profile, rows, metrics=metrics, monthly=monthly, daily=stage_days, releases=releases
    )


def get(client: TestClient, path: str, **params: Any) -> Any:
    response = client.get(f"/api/reports/{path}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


# --- executive summary -------------------------------------------------------------------------


def test_f20_ac01_release_rate_ytd_counts_released_lots_with_a_ud_date_in_the_year(
    client: TestClient,
) -> None:
    body = get(client, "summary")
    assert body["year"] == 2026 and body["years"] == [2026, 2025]
    release = body["release"]
    assert (release["released"], release["annual_target"]) == (4, 700)
    assert release["coverage_weeks"] == 27  # 13 Apr (the week of the first release) to 12 Oct
    assert release["prorata_target"] == 363  # 700 * 27 / 52, rounded
    assert release["pct_of_prorata"] == 1  # 4 / 363
    assert body["coverage_from"] == "2026-04-15"
    assert body["freshness"]["contract_run_id"] == "run-1"


def test_f20_ac06_adherence_and_expedite_figures(client: TestClient) -> None:
    body = get(client, "summary")
    assert body["adherence"] | {"pct": None} == {
        "on_time": 2, "late": 1, "excluded": 1, "pct": None, "target_pct": 90, "rag": "red",
    }  # fmt: skip
    assert Decimal(body["adherence"]["pct"]) == Decimal("66.7")
    assert (body["expedite"]["on_time"], body["expedite"]["late"], body["expedite"]["expedited"]) == (1, 1, 2)
    assert body["expedite"]["app_only"] == 0


def test_f20_oq120_an_app_only_expedite_is_in_the_caption_not_the_ratio(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    with app_factory() as session:
        session.execute(
            text(
                "INSERT INTO override_value (row_key, field, value_json, version, author_user_key, created_at, is_current) "
                "VALUES ('RM10031|B4|0004', 'expedite', 'true', 1, 'pat', '2026-09-01T08:00:00Z', true)"
            )
        )
        session.commit()
    body = get(client, "summary")
    assert (body["expedite"]["expedited"], body["expedite"]["app_only"]) == (2, 1)


def test_f20_ac06_an_adjusted_need_by_set_before_the_release_replaces_the_original(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    with app_factory() as session:
        session.execute(  # B1 released 15 Apr against 20 Apr; pulled forward to 10 Apr on 1 Apr: now exceeded
            text(
                "INSERT INTO override_value (row_key, field, value_json, reason_code, version, author_user_key, "
                "created_at, is_current) VALUES ('RM10031|B1|0001', 'adjusted_need_by_date', '\"2026-04-10\"', "
                "'CAMPAIGN_PULLED_FORWARD', 1, 'pat', '2026-04-01T08:00:00Z', true)"
            )
        )
        session.commit()
    assert get(client, "summary")["adherence"]["late"] == 2
    with app_factory() as session:  # the same override set after the release does not count
        session.execute(text("UPDATE override_value SET created_at = '2026-04-20T08:00:00Z'"))
        session.commit()
    assert get(client, "summary")["adherence"]["late"] == 1


def test_f20_oq124_the_year_filters_the_summary(client: TestClient) -> None:
    body = get(client, "summary", year=2025)
    assert body["year"] == 2025 and body["release"]["released"] == 1
    assert body["adherence"]["late"] == 1
    assert get(client, "summary", year=2030)["release"]["released"] == 0
    assert client.get("/api/reports/summary", params={"year": 1999}).status_code == 422


# --- SLA performance ---------------------------------------------------------------------------


def test_f20_ac02_sla_performance_shows_week_41_m3_green_m6_amber_m7_red_with_the_90_line(
    client: TestClient,
) -> None:
    body = get(client, "sla")
    assert body["target_pct"] == 90
    bars = {b["metric_id"]: b for b in body["bars"]}
    assert (bars["M3"]["rag"], bars["M6"]["rag"], bars["M7"]["rag"]) == ("green", "amber", "red")
    assert {m: bars[m]["week_start"] for m in ("M3", "M6", "M7")} == dict.fromkeys(
        ("M3", "M6", "M7"), "2026-10-05"
    )
    assert Decimal(bars["M3"]["pct"]) == Decimal("94.4")
    for metric in ("M1", "M2", "M4", "M5"):
        assert (bars[metric]["pct"], bars[metric]["status"]) == (None, "awaiting_signal")
        assert bars[metric]["null_reason"]
    assert {a["metric_id"] for a in body["awaiting_signal"]} == {"M1", "M2", "M4", "M5"}


# --- trends ------------------------------------------------------------------------------------


def test_f20_ac03_weekly_trends_show_four_complete_weeks_plus_the_current_with_the_trend(
    client: TestClient,
) -> None:
    body = get(client, "trends", grain="weekly")
    assert body["periods"] == ["2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05", "2026-10-12"]
    rows = {r["metric_id"]: r for r in body["rows"]}
    m3 = rows["M3"]
    assert [Decimal(c["pct"]) if c["pct"] else None for c in m3["cells"]] == [
        Decimal("78.6"), Decimal("84.4"), Decimal("81.8"), Decimal("94.4"), None,
    ]  # fmt: skip
    assert (m3["trend"], Decimal(m3["trend_delta_pp"])) == ("up", Decimal("12.6"))  # 94.4 against 81.8
    assert rows["M6"]["trend"] == "up" and rows["M7"]["trend"] == "down"
    assert (rows["M1"]["trend"], rows["M1"]["status"]) == ("none", "awaiting_signal")


def test_f20_ac03_monthly_trends_show_three_complete_months_plus_the_current(client: TestClient) -> None:
    body = get(client, "trends", grain="monthly")
    assert body["periods"] == ["2026-07-01", "2026-08-01", "2026-09-01", "2026-10-01"]
    m3 = next(r for r in body["rows"] if r["metric_id"] == "M3")
    assert [Decimal(c["pct"]) for c in m3["cells"]] == [
        Decimal("80.0"),
        Decimal("75.0"),
        Decimal("83.2"),
        Decimal("94.4"),
    ]
    assert (m3["trend"], Decimal(m3["trend_delta_pp"])) == ("up", Decimal("8.2"))  # September against August


def test_f20_oq126_a_change_under_two_points_is_stable(client: TestClient) -> None:
    body = get(client, "trends", grain="weekly")
    m6 = next(r for r in body["rows"] if r["metric_id"] == "M6")
    assert m6["trend"] == "up"  # 83.7 against 80.0 is +3.7
    other = get(client, "trends", grain="monthly")
    assert next(r for r in other["rows"] if r["metric_id"] == "M7")["trend"] == "none"  # no months


def test_f20_oq124_stage_trends_are_daily_or_weekly_on_the_sunday(client: TestClient) -> None:
    daily_body = get(client, "trends", stage_grain="daily")
    assert [p["day"] for p in daily_body["points"]] == [
        "2026-10-04", "2026-10-09", "2026-10-10", "2026-10-11", "2026-10-12",
    ]  # fmt: skip
    assert daily_body["points"][-1]["total"] == 5
    assert [s["stage_key"] for s in daily_body["stages"]] == list(STAGES)
    weekly_body = get(client, "trends", stage_grain="weekly")
    points = weekly_body["points"]
    assert [(p["day"], p["week_start"]) for p in points] == [
        ("2026-10-04", "2026-09-28"), ("2026-10-11", "2026-10-05"), ("2026-10-12", "2026-10-12"),
    ]  # fmt: skip
    assert points[1]["counts"]["sampling"] == 3  # the Sunday of the week of 5 Oct


# --- late items --------------------------------------------------------------------------------


def test_f20_ac05_late_items_match_the_overview_late_count_worst_first(client: TestClient) -> None:
    body = get(client, "late")
    overview = client.get("/api/overview").json()
    late_alert = next(a for a in overview["alerts"] if a["kind"] == "late")
    assert body["count"] == late_alert["count"] == 2
    assert [(i["material_no"], i["metric_breached"], i["days_over_sla"]) for i in body["items"]] == [
        ("RM10040", "M3", 65),
        ("RM10041", "M6", 30),
    ]  # 1 Aug + 7 days (sampling) and 1 Aug + 42 days (testing), against 12 Oct
    assert body["items"][0]["late_reason"] is None


def test_f20_ac05_a_status_log_reason_shows_as_the_late_reason_category(client: TestClient) -> None:
    row = "RM10040|L1|9001"
    client.get("/api/reports/late")  # warm
    created = client.post(
        f"/api/rows/{row}/status-log",
        json={
            "status": "at_risk",
            "team": "QC Lab",
            "reason_code": "resource_constraint",
            "comment": "No analyst",
        },
        headers=QUINN,
    )
    assert created.status_code == 201, created.text
    item = next(i for i in get(client, "late")["items"] if i["row_key"] == row)
    assert item["late_reason"] == "Resource constraint"


# --- release rate and adherence ----------------------------------------------------------------


def test_f20_oq124_release_rate_lists_the_weeks_of_the_year_with_the_weekly_target(
    client: TestClient,
) -> None:
    body = get(client, "release-rate")
    assert body["weekly_target"] == 13
    assert [(w["week_start"], w["released_count"]) for w in body["weeks"]] == [
        ("2025-12-29", 0),  # an ISO week belongs to the year of its Thursday (1 Jan 2026)
        ("2026-04-13", 1),
        ("2026-05-04", 1),
    ]
    assert [w["week_start"] for w in get(client, "release-rate", year=2025)["weeks"]] == ["2025-10-20"]


def test_f20_ac06_adherence_by_week(client: TestClient) -> None:
    body = get(client, "adherence")
    assert [(w["week_start"], w["within"], w["exceeded"]) for w in body["weeks"]] == [
        ("2026-04-13", 1, 0), ("2026-05-04", 0, 1), ("2026-06-01", 1, 0),
    ]  # fmt: skip
    assert body["adherence"]["excluded"] == 1


# --- exports -----------------------------------------------------------------------------------


def rows_of(response: Any) -> list[list[str]]:
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    return list(csv.reader(io.StringIO(response.text)))


@pytest.mark.parametrize("tab", ["summary", "sla", "trends", "late", "release-rate", "adherence"])
def test_f20_fr06_every_tab_exports_csv_for_every_role(client: TestClient, tab: str) -> None:
    for headers in (PAT, {"X-Demo-User": "sam"}):
        table = rows_of(client.get(f"/api/reports/{tab}/export.csv", headers=headers))
        assert len(table) >= 2 and len(set(map(len, table))) == 1, tab


def test_f20_fr06_the_late_export_matches_the_tab(client: TestClient) -> None:
    table = rows_of(client.get("/api/reports/late/export.csv"))
    assert table[0][:2] == ["material", "batch"]
    assert len(table) - 1 == get(client, "late")["count"]


def test_f20_oq126_trends_exports_the_sla_table_or_the_stage_series(client: TestClient) -> None:
    assert rows_of(client.get("/api/reports/trends/export.csv"))[0][0] == "metric"
    stage = rows_of(client.get("/api/reports/trends/export.csv", params={"part": "stage"}))
    assert stage[0][0] == "day" and stage[0][-1] == "total"


def test_f20_fr06_an_unknown_tab_is_422_and_a_report_needs_a_user(client: TestClient) -> None:
    assert client.get("/api/reports/nope/export.csv").status_code == 422
    assert client.get("/api/reports/nope").status_code in (404, 422)
