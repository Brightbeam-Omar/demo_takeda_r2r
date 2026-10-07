"""F12 T11: optional autorun and the pause and resume endpoints [F12-FR-11, F12-FR-14, OQ-144]."""

from collections.abc import Callable

import pytest
from agent_support import ROW_KEY, B5003Model, source_transport
from agents.air_gap.candidates import row_keys_with_proposals
from agents.main import create_app
from agents.settings import Settings
from agents.tools.http import ReadOnlyHttp
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

pytestmark = pytest.mark.integration
TOKEN = {"X-Scenario-Token": "test-token"}


def _swap(client: TestClient, **transport: object) -> None:
    deps = client.app.state.deps  # type: ignore[attr-defined]
    deps.http = ReadOnlyHttp.from_settings(deps.settings, transport=source_transport(**transport))  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCENARIO_TOKEN", "test-token")


def test_f12_fr11_the_first_poll_only_remembers_the_state_then_a_new_run_triggers_the_agent(
    build_app: Callable[..., TestClient], agents_engine: Engine
) -> None:
    client = build_app()
    autorun = client.app.state.autorun  # type: ignore[attr-defined]
    autorun.enabled = True
    assert autorun.tick() is None and autorun.cursor == "run-1"  # nothing happens at start-up
    assert row_keys_with_proposals(agents_engine, open_only=False) == set()
    assert autorun.tick() is None  # the same run again: nothing
    _swap(client, sync_run="run-2")
    summary = autorun.tick()
    assert summary is not None and [r.row_key for r in summary.of("created")] == [ROW_KEY]
    assert autorun.cursor == "run-2" and autorun.tick() is None


def test_f12_fr11_autorun_never_proposes_again_for_a_row_that_had_a_proposal(
    build_app: Callable[..., TestClient], agents_engine: Engine
) -> None:
    client = build_app()
    client.post("/agents/air_gap/run", headers={"X-Demo-User": "alex"}, json={})
    pid = 1
    assert (
        client.post(
            f"/proposals/{pid}/reject", headers={"X-Demo-User": "alex"}, json={"reason": "not needed now"}
        ).status_code
        == 200
    )
    autorun = client.app.state.autorun  # type: ignore[attr-defined]
    autorun.enabled = True
    autorun.tick()
    _swap(client, sync_run="run-2")
    summary = autorun.tick()
    assert summary is not None and summary.of("created") == []
    assert summary.of("skipped")[0].message == "has been proposed before"
    with agents_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM proposal")).scalar_one() == 1


def test_f12_fr11_autorun_is_off_by_default() -> None:
    from agent_support import fake_app_api

    app = create_app(Settings.from_env({}), None, fake_app_api())
    assert app.state.autorun.enabled is False and app.state.autorun.tick() is None
    assert Settings.from_env({"AGENTS_AUTORUN": "true"}).autorun is True


def test_f12_fr14_pause_stops_the_poll_and_resume_sets_the_cursor_to_the_current_run(
    build_app: Callable[..., TestClient],
) -> None:
    client = build_app()
    autorun = client.app.state.autorun  # type: ignore[attr-defined]
    autorun.enabled = True
    autorun.tick()
    assert client.post("/agents/autorun/pause", headers=TOKEN).json() == {
        "enabled": True,
        "paused": True,
        "cursor": "run-1",
    }
    _swap(client, sync_run="run-2")
    assert autorun.tick() is None  # paused: a new run does not fire
    state = client.post("/agents/autorun/resume", headers=TOKEN).json()
    assert state == {
        "enabled": True,
        "paused": False,
        "cursor": "run-2",
    }  # the reset's fresh state is the baseline
    assert autorun.tick() is None  # so the first poll after a reset does not run the agent
    assert client.get("/agents/autorun", headers=TOKEN).json()["cursor"] == "run-2"


def test_f12_fr14_the_endpoints_need_the_scenario_token(build_app: Callable[..., TestClient]) -> None:
    client = build_app()
    assert client.post("/agents/autorun/pause").status_code == 401
    assert client.post("/agents/autorun/resume", headers={"X-Scenario-Token": "wrong"}).status_code == 401
    assert client.post("/agents/autorun/pause", headers=TOKEN).status_code == 200


def test_f12_fr11_an_unreadable_sync_status_is_logged_not_fatal(build_app: Callable[..., TestClient]) -> None:
    import httpx

    client = build_app(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    autorun = client.app.state.autorun  # type: ignore[attr-defined]
    autorun.enabled = True
    assert autorun.tick() is None and autorun.cursor is None
    assert B5003Model  # the model is unused here
