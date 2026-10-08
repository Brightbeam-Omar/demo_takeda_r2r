"""F14 T4: the replay check behind `make doctor` finds out whether the demo-start air gaps replay [F14-FR-05, OQ-160]."""

from collections.abc import Callable
from pathlib import Path

import pytest
from agent_support import B5003Model, source_transport
from agents.air_gap.replay_check import replay_check
from agents.record import record_all
from agents.settings import Settings
from agents.tools.http import ReadOnlyHttp
from fastapi.testclient import TestClient
from r2r_core.profile import load_profile


def _http() -> ReadOnlyHttp:
    return ReadOnlyHttp.from_settings(Settings.from_env({}), transport=source_transport())


def _record(directory: Path) -> None:
    record_all(
        http=_http(), live=B5003Model(), profile=load_profile("site_a"), directory=directory,
        demo_user="admin", expected_hours=(30,),
    )  # fmt: skip


def test_f14_fr05_recorded_air_gaps_replay(tmp_path: Path) -> None:
    _record(tmp_path)
    result = replay_check(_http(), load_profile("site_a"), tmp_path, "admin", expected_hours=(30,))
    assert result.demo_start is True
    assert result.recording_files == 4
    assert [(c.batch_no, c.replays, c.missing_key) for c in result.candidates] == [("B5003", True, None)]


def test_f14_fr05_an_empty_recordings_folder_names_the_missing_key(tmp_path: Path) -> None:
    result = replay_check(_http(), load_profile("site_a"), tmp_path, "admin", expected_hours=(30,))
    assert result.recording_files == 0
    [candidate] = result.candidates
    assert (
        candidate.replays is False and candidate.missing_key is not None and len(candidate.missing_key) == 64
    )


def test_f14_fr05_a_stack_that_is_not_in_the_demo_start_state_says_so(tmp_path: Path) -> None:
    _record(tmp_path)
    result = replay_check(_http(), load_profile("site_a"), tmp_path, "admin", expected_hours=(90, 70, 62, 30))
    assert result.demo_start is False


@pytest.mark.integration
def test_f14_fr05_the_route_returns_the_check(build_app: Callable[..., TestClient]) -> None:
    client = build_app()
    body = client.get("/agents/air_gap/replay-check", headers={"X-Demo-User": "admin"}).json()
    assert set(body) == {"recordings_dir", "recording_files", "demo_start", "candidates"}
