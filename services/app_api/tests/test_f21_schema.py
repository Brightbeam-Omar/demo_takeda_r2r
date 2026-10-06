"""T7: the Schema Reference endpoint (F21-FR-06, F21-AC-06)."""

import json
from pathlib import Path

import pytest
from app_api.models import MIRRORS
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

CONTRACT = json.loads((Path(__file__).parents[3] / "specs" / "contract.json").read_text(encoding="utf-8"))


def test_f21_ac06_the_schema_lists_every_published_object_the_app_mirrors(client: TestClient) -> None:
    body = client.get("/api/schema").json()
    names = [o["name"] for o in body["objects"]]
    assert set(names) == set(MIRRORS)  # nothing mirrored is missing from the reference, nothing extra
    assert names == [o["name"] for o in CONTRACT["objects"]]


def test_f21_fr06_an_object_has_a_description_a_grain_and_typed_described_columns(client: TestClient) -> None:
    body = client.get("/api/schema").json()
    runs = next(o for o in body["objects"] if o["name"] == "pipeline_runs_v")
    assert runs["grain"] == "One row per pipeline run."
    skipped = next(c for c in runs["columns"] if c["name"] == "skipped")
    assert skipped["type"] == "integer" and "unchanged" in skipped["description"]


def test_f21_ac06_the_mirror_columns_match_the_reference_columns() -> None:
    for obj in CONTRACT["objects"]:
        mirrored = [name for name, _ in MIRRORS[obj["name"]][1]]
        assert [c["name"] for c in obj["columns"]] == mirrored, obj["name"]


def test_f21_fr06_a_missing_file_is_a_503_with_the_fix(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CONTRACT_JSON", str(tmp_path / "nope.json"))
    response = client.get("/api/schema")
    assert response.status_code == 503 and "make contract-json" in response.json()["detail"]


def test_f21_fr06_every_role_may_read_it_and_an_unknown_user_may_not(client: TestClient) -> None:
    assert client.get("/api/schema", headers={"X-Demo-User": "sam"}).status_code == 200
    assert client.get("/api/schema", headers={"X-Demo-User": "ghost"}).status_code == 401
