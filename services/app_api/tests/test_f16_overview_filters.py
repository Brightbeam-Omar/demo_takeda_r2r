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
