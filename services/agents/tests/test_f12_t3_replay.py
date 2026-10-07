"""F12 T3 [TDD]: replay key per model call, recordings, replay miss [F12-FR-03, F12-AC-09, OQ-139]."""

import json
from pathlib import Path

import pytest
from agent_support import ListTrace
from agents.gateway.base import (
    ModelGateway,
    ModelResult,
    Msg,
    TextBlock,
    ToolResultBlock,
    ToolSpec,
    ToolUseBlock,
)
from agents.gateway.replay import RecordingGateway, ReplayGateway, ReplayMiss, clear_recordings, replay_key

SENTINEL_KEY = "sk-ant-test-sentinel-0123456789"
TOOL = ToolSpec(name="get_row", description="read a row", input_schema={"type": "object"})


def _messages() -> list[Msg]:
    return [
        Msg.user("Candidate B5003"),
        Msg(role="assistant", content=[ToolUseBlock(id="toolu_1", name="get_row", input={"row_key": "r1"})]),
        Msg(role="user", content=[ToolResultBlock(tool_use_id="toolu_1", content='{"batch_no":"B5003"}')]),
    ]


def _key(**changes: object) -> str:
    args: dict[str, object] = {
        "agent_key": "air_gap",
        "prompt_version": "v1",
        "turn": 2,
        "system": "system prompt",
        "tools": [TOOL],
        "messages": _messages(),
    }
    args.update(changes)
    return replay_key(**args)  # type: ignore[arg-type]


def test_f12_fr03_key_is_a_stable_sha256() -> None:
    assert _key() == _key()
    assert len(_key()) == 64 and set(_key()) <= set("0123456789abcdef")


@pytest.mark.parametrize(
    "change",
    [
        {"agent_key": "other"},
        {"prompt_version": "v2"},
        {"turn": 3},
        {"system": "a different system prompt"},
        {"tools": []},
        {"messages": _messages()[:2]},
        {"messages": [Msg.user("Candidate B5004"), *_messages()[1:]]},
    ],
)
def test_f12_fr03_key_moves_with_every_input(change: dict[str, object]) -> None:
    assert _key(**change) != _key()


def test_f12_fr03_key_ignores_dict_order_in_tool_input() -> None:
    a = [Msg(role="assistant", content=[ToolUseBlock(id="t", name="n", input={"a": 1, "b": 2})])]
    b = [Msg(role="assistant", content=[ToolUseBlock(id="t", name="n", input={"b": 2, "a": 1})])]
    assert _key(messages=a) == _key(messages=b)


class ScriptedGateway(ModelGateway):
    provider = "scripted"
    model_id = "scripted-model"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, *, system, messages, tools, turn, agent_key, prompt_version) -> ModelResult:  # type: ignore[no-untyped-def]
        self.calls += 1
        return ModelResult(
            content=[
                TextBlock(text="done"),
                ToolUseBlock(id="toolu_9", name="submit_ticket", input={"title": "t"}),
            ],
            stop_reason="tool_use",
            tokens_in=300,
            tokens_out=40,
            latency_ms=900,
            model_id="scripted-model",
        )


def _complete(gateway: ModelGateway, trace: ListTrace | None = None) -> ModelResult:
    return gateway.complete(
        system="system prompt",
        messages=_messages(),
        tools=[TOOL],
        trace=trace or ListTrace(),
        turn=2,
        agent_key="air_gap",
        prompt_version="v1",
    )


def test_f12_fr03_record_then_replay_gives_the_same_answer_without_the_model(tmp_path: Path) -> None:
    inner = ScriptedGateway()
    recorded = _complete(RecordingGateway(inner, tmp_path))
    assert inner.calls == 1
    files = list((tmp_path / "air_gap").glob("*.json"))
    assert [f.stem for f in files] == [_key()]  # one file per call, named by the key

    trace = ListTrace()
    replayed = _complete(ReplayGateway(tmp_path), trace)
    assert replayed.content == recorded.content
    assert (replayed.tokens_in, replayed.tokens_out, replayed.latency_ms) == (300, 40, 900)  # recorded values
    assert replayed.replayed is True and replayed.model_id == "scripted-model"
    assert trace.steps[1]["payload"]["replayed"] is True  # type: ignore[index]
    assert inner.calls == 1


def test_f12_fr03_recording_keeps_metadata_but_not_the_key_inputs_secret(tmp_path: Path) -> None:
    _complete(RecordingGateway(ScriptedGateway(), tmp_path))
    data = json.loads(next((tmp_path / "air_gap").glob("*.json")).read_text())
    assert {"key", "agent_key", "prompt_version", "turn", "model_id", "recorded_at"} <= set(data)
    assert (data["agent_key"], data["prompt_version"], data["turn"], data["model_id"]) == (
        "air_gap",
        "v1",
        2,
        "scripted-model",
    )


def test_f12_ac09_a_miss_names_the_key_and_the_hint(tmp_path: Path) -> None:
    trace = ListTrace()
    with pytest.raises(ReplayMiss) as raised:
        _complete(ReplayGateway(tmp_path), trace)
    error = raised.value
    assert error.key == _key()
    assert "make record-agents" in str(error) and _key() in str(error)
    assert "demo-start" in error.hint  # the hint says which state the recordings are valid for
    assert [s["step_type"] for s in trace.steps] == ["model_request", "model_response"]  # traced, not lost


def test_f12_fr03_a_changed_prompt_is_a_miss_not_a_stale_replay(tmp_path: Path) -> None:
    _complete(RecordingGateway(ScriptedGateway(), tmp_path))
    with pytest.raises(ReplayMiss):
        ReplayGateway(tmp_path).complete(
            system="system prompt, edited",
            messages=_messages(),
            tools=[TOOL],
            trace=ListTrace(),
            turn=2,
            agent_key="air_gap",
            prompt_version="v1",
        )


def test_f12_fr03_clear_recordings_removes_only_that_agents_files(tmp_path: Path) -> None:
    _complete(RecordingGateway(ScriptedGateway(), tmp_path))
    other = tmp_path / "other_agent"
    other.mkdir()
    (other / "x.json").write_text("{}")
    assert clear_recordings(tmp_path, "air_gap") == 1
    assert not list((tmp_path / "air_gap").glob("*.json")) and (other / "x.json").exists()


def test_f12_oq146_recordings_never_contain_the_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", SENTINEL_KEY)
    _complete(RecordingGateway(ScriptedGateway(), tmp_path))
    assert all(SENTINEL_KEY not in f.read_text() for f in tmp_path.rglob("*.json"))
