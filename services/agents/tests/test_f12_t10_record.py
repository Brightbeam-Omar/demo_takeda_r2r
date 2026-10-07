"""F12 T10: ``make record-agents`` records the demo-start air gaps, safely [F12-FR-03, OQ-139, OQ-146]."""

from pathlib import Path

import pytest
from agent_support import ROW_KEY, B5003Model, ListTrace, source_transport
from agents.air_gap import agent as air_gap_agent
from agents.air_gap.schema import AirGapTicket
from agents.gateway.replay import ReplayGateway
from agents.harness.runner import run_agent
from agents.prompts import load_prompt
from agents.record import DEMO_START_HOURS, RecordError, record_all
from agents.settings import Settings
from agents.tools.http import ReadOnlyHttp
from datagen.params import load_params
from r2r_core.profile import load_profile

SENTINEL_KEY = "sk-ant-test-sentinel-0123456789"


def _http(**kwargs: object) -> ReadOnlyHttp:
    return ReadOnlyHttp.from_settings(Settings.from_env({}), transport=source_transport(**kwargs))  # type: ignore[arg-type]


def _record(tmp_path: Path, model: B5003Model | None = None, **kwargs: object) -> list:  # type: ignore[type-arg]
    return record_all(
        http=_http(**kwargs),
        live=model or B5003Model(),
        profile=load_profile("site_a"),
        directory=tmp_path,
        demo_user="admin",
        expected_hours=(30,),
    )


def test_f12_fr03_the_demo_start_hours_match_the_generator() -> None:
    """The recorder's list of four air gaps is the one datagen produces: B5003 at 30 h plus the older three."""
    ages = load_params().quirks.air_gap_ages_hours
    assert tuple(sorted([30, *ages], reverse=True)) == DEMO_START_HOURS
    assert len(DEMO_START_HOURS) == load_params().quirks.air_gap_lots


def test_f12_fr03_recording_writes_one_file_per_model_call_and_replays_to_the_same_proposal(
    tmp_path: Path,
) -> None:
    results = _record(tmp_path)
    assert [(r.candidate.batch_no, r.passed, r.model_calls) for r in results] == [("B5003", True, 4)]
    assert results[0].tokens_in == 10000 and results[0].tokens_out == 400
    files = list((tmp_path / "air_gap").glob("*.json"))
    assert len(files) == 4 and not (tmp_path / ".recording").exists()
    # the recordings answer the same run offline: same ticket, no model
    prompt = load_prompt("air_gap", "v1")
    trace = ListTrace()
    outcome = run_agent(
        air_gap_agent.build_spec(_http()),
        ReplayGateway(tmp_path),
        trace,
        user_message=prompt.render_user(
            row_key=ROW_KEY, batch_no="B5003", material_no="RM10067", air_gap_hours=30,
            threshold_hours=24, high_priority_days=14, today="2026-10-12",
        ),
        input_payload={"row_key": ROW_KEY},
        demo_user="admin",
    )  # fmt: skip
    assert outcome.status == "submitted" and isinstance(outcome.output, AirGapTicket)


def test_f12_fr03_it_refuses_a_stack_that_is_not_in_the_demo_start_state(tmp_path: Path) -> None:
    keep = tmp_path / "air_gap"
    keep.mkdir()
    (keep / "old.json").write_text("{}")
    with pytest.raises(RecordError, match="not the demo-start air gaps"):
        record_all(
            http=_http(), live=B5003Model(), profile=load_profile("site_a"), directory=tmp_path,
            demo_user="admin", expected_hours=(90, 70, 62, 30),
        )  # fmt: skip
    assert (keep / "old.json").exists()  # nothing touched


def test_f12_fr03_a_draft_that_fails_the_validator_replaces_nothing(tmp_path: Path) -> None:
    keep = tmp_path / "air_gap"
    keep.mkdir()
    (keep / "old.json").write_text("{}")
    with pytest.raises(RecordError, match="B5003"):
        _record(tmp_path, B5003Model(hours_in_gap=40))
    assert [f.name for f in keep.glob("*.json")] == ["old.json"] and not (tmp_path / ".recording").exists()


def test_f12_fr03_a_good_recording_replaces_the_old_files(tmp_path: Path) -> None:
    keep = tmp_path / "air_gap"
    keep.mkdir()
    (keep / "stale.json").write_text("{}")
    _record(tmp_path)
    assert "stale.json" not in {f.name for f in keep.glob("*.json")} and len(list(keep.glob("*.json"))) == 4


def test_f12_oq146_recordings_never_contain_the_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", SENTINEL_KEY)
    _record(tmp_path)
    assert all(SENTINEL_KEY not in f.read_text() for f in tmp_path.rglob("*.json"))
