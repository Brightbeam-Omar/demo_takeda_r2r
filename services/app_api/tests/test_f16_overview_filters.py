"""F16: the overview filters added for the filter panel: the reserved ``unknown`` class and ``bookmarked``."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from r2r_core.profile import load_profile
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import batch, load_mirror

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def mirror(app_factory: sessionmaker[Session]) -> None:
    rows = [
        batch("B1", "RM10010", material_class="consumable"),
        batch("B2", "RM10011", material_class="drug_substance"),
        batch("B3", "RM10012", material_class=None),
        batch("B4", "RM10013", material_class=None),
    ]
    load_mirror(app_factory, load_profile("site_a"), rows)


def batches(client: TestClient, **params: Any) -> list[str]:
    response = client.get("/api/overview", params=params)
    assert response.status_code == 200, response.text
    return sorted(row["batch_no"] for row in response.json()["rows"])


def test_f16_oq086_unknown_is_the_rows_whose_class_is_null(client: TestClient) -> None:
    assert batches(client, **{"class[]": "unknown"}) == ["B3", "B4"]


def test_f16_oq086_unknown_combines_with_real_classes_as_or(client: TestClient) -> None:
    assert batches(client, **{"class[]": ["unknown", "consumable"]}) == ["B1", "B3", "B4"]


def test_f16_oq086_a_real_class_does_not_match_the_unknown_rows(client: TestClient) -> None:
    assert batches(client, **{"class[]": "drug_substance"}) == ["B2"]


# --- bookmarked (F16-FR-04, OQ-087) ----------------------------------------------------------------------

ROW2 = "RM10011|B2|9001"
ROW3 = "RM10012|B3|9001"


def star(client: TestClient, row_key: str, user: str = "pat") -> None:
    assert client.post(f"/api/bookmarks/{row_key}", headers={"X-Demo-User": user}).status_code == 201


def test_f16_fr04_bookmarked_keeps_only_the_users_bookmarks(client: TestClient) -> None:
    star(client, ROW2)
    star(client, ROW3)
    assert batches(client, bookmarked="true") == ["B2", "B3"]
    assert batches(client) == ["B1", "B2", "B3", "B4"]


def test_f16_fr04_bookmarks_are_per_user_in_the_overview(client: TestClient) -> None:
    star(client, ROW2, "pat")
    quinn = {"X-Demo-User": "quinn"}
    assert client.get("/api/overview", params={"bookmarked": "true"}, headers=quinn).json()["rows"] == []
    assert client.get("/api/overview", headers=quinn).json()["bookmarks"] == []
    assert client.get("/api/overview").json()["bookmarks"] == [ROW2]


def test_f16_fr04_bookmarked_combines_with_the_other_filters(client: TestClient) -> None:
    star(client, ROW2)
    star(client, ROW3)
    assert batches(client, bookmarked="true", **{"class[]": "unknown"}) == ["B3"]


def test_f16_oq087_bookmarked_narrows_the_flow_strip_and_alerts_too(client: TestClient) -> None:
    star(client, ROW2)
    body = client.get("/api/overview", params={"bookmarked": "true"}).json()
    assert sum(entry["count"] for entry in body["flow_strip"]) == 1
    assert body["total"] == 1


def test_f16_fr04_export_honours_bookmarked(client: TestClient) -> None:
    star(client, ROW2)
    lines = client.get("/api/export.csv", params={"bookmarked": "true"}).text.strip().splitlines()
    assert len(lines) == 2  # header + the one bookmarked row
