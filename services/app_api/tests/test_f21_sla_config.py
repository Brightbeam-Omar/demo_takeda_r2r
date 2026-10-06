"""T8: what the SLA Configuration page reads from /api/reference (F21-FR-06, OQ-134)."""

import pytest
from app_api.deps import profile_file
from app_api.services.stage_events import STAGE_EVENTS
from fastapi.testclient import TestClient
from r2r_core.profile import SiteProfile, load_profile
from sqlalchemy.orm import Session, sessionmaker
from support_f09 import batch, load_mirror

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def profile() -> SiteProfile:
    return load_profile("site_a")


@pytest.fixture(autouse=True)
def mirror(app_factory: sessionmaker[Session], profile: SiteProfile) -> None:
    load_mirror(app_factory, profile, [batch()])


def test_f21_oq134_the_reference_names_the_active_profile_file(client: TestClient) -> None:
    assert client.get("/api/reference").json()["profile_file"] == "site_a.yaml"


@pytest.mark.parametrize(
    ("value", "expected"),
    [("site_a", "site_a.yaml"), ("site_b.yaml", "site_b.yaml"), ("/etc/profiles/site_c.yaml", "site_c.yaml")],
)
def test_f21_oq134_the_profile_file_follows_site_profile(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: str
) -> None:
    monkeypatch.setenv("SITE_PROFILE", value)
    assert profile_file() == expected


def test_f21_oq134_every_stage_metric_has_entry_and_exit_events_and_a_window(
    client: TestClient, profile: SiteProfile
) -> None:
    metrics = {m["metric_id"]: m for m in client.get("/api/reference").json()["metrics"]}
    assert metrics["M3"]["entry_event"] == "Transferred to site (3PL) or inbound check completed"
    assert metrics["M3"]["exit_event"] == "Sample collected"
    assert metrics["M7"]["exit_event"] == "Usage decision posted"
    assert metrics["M3"]["window"] == "Weekly (ISO week)"
    assert metrics["M1"]["window"] == "Tier 2"  # computed in the app, awaiting its signal
    assert (metrics["M5"]["entry_event"], metrics["M5"]["exit_event"]) == (None, None)  # not bound to a stage


def test_f21_oq134_the_lookup_covers_every_non_terminal_stage_of_the_profile(profile: SiteProfile) -> None:
    keys = {stage.key for stage in profile.stages if not stage.terminal and stage.sla_days > 0}
    assert keys <= set(STAGE_EVENTS)
