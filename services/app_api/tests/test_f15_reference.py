"""F15 T2: ``/api/reference`` carries the profile terms and labelled lists (F15-FR-05, F15-AC-03, OQ-081, OQ-082)."""

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from app_api.deps import get_profile
from r2r_core.profile import profiles_dir

pytestmark = pytest.mark.integration


def test_f15_ac03_site_a_terms_and_labels(client: TestClient) -> None:
    body = client.get("/api/reference").json()
    assert body["terms"]["erp_blocked_tag"] == "SAP BLOCKED"
    assert body["terms"]["insights_banner"] == "LIMS–SAP Insights"
    assert body["molecule_types"][0] == {"key": "small_molecule", "label": "Small Molecule"}
    assert body["classes"] == [
        {"key": "drug_substance", "label": "Drug Substance"},
        {"key": "consumable", "label": "Consumable"},
    ]


def test_f15_ac03_a_profile_with_erp_reads_erp_blocked_with_no_code_change(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = yaml.safe_load((profiles_dir() / "site_a.yaml").read_text())
    data["terms"] = {"erp": "ERP"}
    path = tmp_path / "test_profile.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True))
    monkeypatch.setenv("SITE_PROFILE", str(path))
    get_profile.cache_clear()  # the profile is cached per process
    try:
        terms = client.get("/api/reference").json()["terms"]
    finally:
        monkeypatch.undo()
        get_profile.cache_clear()
    assert terms["erp_blocked_tag"] == "ERP BLOCKED"
    assert terms["insights_banner"] == "LIMS–ERP Insights"


def test_f15_oq081_the_release_badge_is_served_at_runtime(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert client.get("/api/reference").json()["release_badge"] == "ALPHA – LOCAL"
    monkeypatch.setenv("RELEASE_BADGE", "ALPHA – DEMO")
    assert client.get("/api/reference").json()["release_badge"] == "ALPHA – DEMO"
