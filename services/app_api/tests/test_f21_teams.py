"""T6 [TDD]: the Team Dashboard endpoint (F21-FR-06, F21-AC-05, OQ-133)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from r2r_core.profile import SiteProfile, load_profile
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import D, batch, load_mirror

pytestmark = pytest.mark.integration

# Today is 12 Oct 2026. With no need-by a sampling lot is due 7 days after it entered the stage: LATE_34 was
# due 8 Sep (34 days over), LATE_4 was due 8 Oct (4 days over), AMBER is due tomorrow, GREEN in 5 days.
LATE_34 = {"current_stage_entry_date": D(9, 1), "sampling_entry": D(9, 1), "system_need_by_locked": None}
LATE_4 = {"current_stage_entry_date": D(10, 1), "sampling_entry": D(10, 1), "system_need_by_locked": None}
AMBER = {
    "current_stage_entry_date": D(10, 6),
    "sampling_entry": D(10, 6),
    "system_need_by_locked": None,
}  # 1 day left
GREEN = {"current_stage_entry_date": D(10, 10), "sampling_entry": D(10, 10), "system_need_by_locked": None}


@pytest.fixture(scope="module")
def profile() -> SiteProfile:
    return load_profile("site_a")


def qc(batch_no: str, material: str, **over: Any) -> dict[str, Any]:
    row = {
        "stage_key": "qc_testing", "stage_rule_id": "R-QCT", "current_stage_entry_date": D(9, 20),
        "qc_testing_entry": D(9, 20), "system_need_by_locked": None,
    }  # fmt: skip
    return batch(batch_no, material, **row, **over)


@pytest.fixture(autouse=True)
def mirror(app_factory: sessionmaker[Session], profile: SiteProfile) -> None:
    rows = [
        batch("B1", "RM10001", stage_key="pending", stage_rule_id="R-PND", current_stage_entry_date=None),
        batch("B2", "RM10002", **LATE_34),
        batch("B3", "RM10003", **LATE_4),
        batch("B4", "RM10004", **AMBER),
        batch("B5", "RM10005", **GREEN),
        qc("B6", "RM10006"),  # 22 days in a 42-day stage: green
        batch("B7", "RM10007", stage_key="qa_release", stage_rule_id="R-QAR", current_stage_entry_date=D(10, 1),
              qa_release_entry=D(10, 1), system_need_by_locked=None),  # 7-day stage, entered 11 days ago: late
        batch("B8", "RM10008", stage_key="released", stage_rule_id="R-REL", ud_effective=True, ud_code="A"),
    ]  # fmt: skip
    load_mirror(app_factory, profile, rows)


def teams(client: TestClient, **kwargs: Any) -> dict[str, Any]:
    response = client.get("/api/teams", **kwargs)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def by_team(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {team["team"]: team for team in body["teams"]}


def test_f21_fr06_each_team_owns_its_stages_from_the_stage_reference(client: TestClient) -> None:
    body = teams(client)
    found = by_team(body)
    assert [t["team"] for t in body["teams"]] == ["Logistics", "Warehouse", "Manufacturing", "QC Lab", "QA"]
    assert found["Warehouse"]["stage_keys"] == ["receipt", "call_off"]
    assert found["QC Lab"]["stage_keys"] == ["qc_ship", "qc_testing"]
    assert found["QA"]["stage_keys"] == ["qa_release"]  # the terminal Released stage is not a team's work


def test_f21_oq133_open_rows_skip_pending_and_released(client: TestClient) -> None:
    found = by_team(teams(client))
    assert found["Logistics"]["open"] == 0  # the pending lot has not entered a stage
    assert found["Manufacturing"]["open"] == 4
    assert found["QC Lab"]["open"] == 1
    assert found["QA"]["open"] == 1


def test_f21_fr06_late_oldest_late_and_at_risk(client: TestClient) -> None:
    found = by_team(teams(client))
    sampling = found["Manufacturing"]
    assert sampling["late"] == 2
    assert sampling["oldest_late_days"] == 34  # due 8 Sep, today 12 Oct
    assert sampling["amber"] == 1
    assert sampling["at_risk_pct"] == 25.0  # one amber lot of four open
    assert found["QC Lab"]["late"] == 0
    assert found["QC Lab"]["oldest_late_days"] is None
    assert found["QA"]["late"] == 1


def test_f21_ac05_the_late_counts_sum_to_the_overview_late_count(client: TestClient) -> None:
    body = teams(client)
    overview = client.get("/api/overview").json()
    late_alert = next(a for a in overview["alerts"] if a["kind"] == "late")["count"]
    assert sum(t["late"] for t in body["teams"]) == late_alert == body["totals"]["late"] == 3


def test_f21_oq133_the_page_is_a_snapshot_that_ignores_filters(client: TestClient) -> None:
    plain = teams(client)
    filtered = client.get(
        "/api/teams", params={"stage": ["receipt"], "type[]": ["peptide"], "period": "this_week"}
    )
    assert filtered.status_code == 200
    assert filtered.json() == plain


def test_f21_fr06_every_role_may_read_it(client: TestClient) -> None:
    for user in ("sam", "pat", "quinn", "alex", "admin"):
        assert client.get("/api/teams", headers={"X-Demo-User": user}).status_code == 200
    assert client.get("/api/teams", headers={"X-Demo-User": "ghost"}).status_code == 401
