"""F12 T5: the generic runner loop, its limits and the prompt files [F12-FR-04, F12-FR-05]."""

from typing import Any

import pytest
from agent_support import ROW_KEY, ListTrace, source_transport
from agents.gateway.base import (
    Block,
    ModelGateway,
    ModelResult,
    Msg,
    TextBlock,
    ToolResultBlock,
    ToolSpec,
    ToolUseBlock,
)
from agents.harness.runner import AgentSpec, RunOutcome, run_agent
from agents.prompts import load_prompt
from agents.settings import Settings
from agents.tools.http import ReadOnlyHttp
from agents.tools.registry import read_only_tools
from pydantic import BaseModel, Field


class Toy(BaseModel):
    row_key: str
    title: str = Field(max_length=20)


SUBMIT = ToolSpec(name="submit_ticket", description="submit", input_schema=Toy.model_json_schema())


def use(name: str, **arguments: Any) -> ToolUseBlock:
    return ToolUseBlock(id=f"toolu_{name}_{len(arguments)}", name=name, input=arguments)


class Script(ModelGateway):
    """A model that answers each call with the next prepared list of content blocks."""

    provider = "scripted"
    model_id = "scripted"

    def __init__(self, *turns: list[Block]) -> None:
        self.turns = list(turns)
        self.seen: list[list[Msg]] = []

    def generate(self, *, system, messages, tools, turn, agent_key, prompt_version) -> ModelResult:  # type: ignore[no-untyped-def]
        self.seen.append(list(messages))
        content = self.turns.pop(0)
        stop = "tool_use" if any(isinstance(b, ToolUseBlock) for b in content) else "end_turn"
        return ModelResult(
            content=content, stop_reason=stop, tokens_in=100, tokens_out=20, latency_ms=5, model_id="scripted"
        )


def _spec() -> AgentSpec:
    http = ReadOnlyHttp.from_settings(Settings.from_env({}), transport=source_transport())
    return AgentSpec(
        key="toy",
        prompt_version="v1",
        system="system",
        tools=read_only_tools(http),
        output_tool=SUBMIT,
        output_model=Toy,
    )


def _run(*turns: list[Block], max_tool_calls: int = 8) -> tuple[RunOutcome, ListTrace, Script]:
    trace, gateway = ListTrace(), Script(*turns)
    outcome = run_agent(
        _spec(),
        gateway,
        trace,
        user_message="go",
        input_payload={"row_key": ROW_KEY},
        demo_user="alex",
        max_tool_calls=max_tool_calls,
    )
    return outcome, trace, gateway


def _kinds(trace: ListTrace) -> list[str]:
    return [str(s["step_type"]) for s in trace.steps]


def test_f12_fr04_the_loop_runs_tools_then_ends_on_a_valid_submission() -> None:
    outcome, trace, gateway = _run(
        [use("get_row", row_key=ROW_KEY)],
        [use("get_lims_sample", sample_id="S-0000404"), use("get_erp_lot", prueflos="10000459")],
        [use("list_deviations", batch_no="B5003")],
        [use("submit_ticket", row_key=ROW_KEY, title="Batch B5003 gap")],
    )
    assert outcome.status == "submitted" and outcome.output == Toy(row_key=ROW_KEY, title="Batch B5003 gap")
    assert outcome.tool_calls == 4 and set(outcome.systems_read) == {"app", "LIMS", "ERP", "QMS"}
    assert _kinds(trace) == [
        "input",
        "model_request", "model_response", "tool_call", "tool_result",
        "model_request", "model_response", "tool_call", "tool_result", "tool_call", "tool_result",
        "model_request", "model_response", "tool_call", "tool_result",
        "model_request", "model_response",
    ]  # fmt: skip
    # the tool answers go back to the model as tool_result blocks, one per call
    last = gateway.seen[-1][-1]
    assert [b.type for b in last.content] == ["tool_result"]


def test_f12_fr04_a_tool_error_goes_back_to_the_model_and_the_run_continues() -> None:
    outcome, _, gateway = _run(
        [use("get_erp_lot", prueflos="99999999")],
        [use("submit_ticket", row_key=ROW_KEY, title="t")],
    )
    assert outcome.status == "submitted"
    answer = gateway.seen[1][-1].content[0]
    assert isinstance(answer, ToolResultBlock) and answer.is_error and "no record" in answer.content
    assert outcome.systems_read == []  # a failed read is not evidence of reading a system


def test_f12_fr04_more_than_eight_tool_calls_aborts_with_a_trace_step() -> None:
    calls = [[use("get_row", row_key=f"r{i}")] for i in range(12)]
    outcome, trace, _ = _run(*calls)
    assert outcome.status == "tool_limit" and "more than 8" in outcome.message
    assert _kinds(trace).count("tool_call") == 8
    assert trace.steps[-1]["step_type"] == "decision"
    assert trace.steps[-1]["payload"]["outcome"] == "aborted"  # type: ignore[index]


def test_f12_oq145_a_malformed_submission_is_retried_once_then_ends() -> None:
    bad = [use("submit_ticket", row_key=ROW_KEY, title="x" * 50)]
    good = [use("submit_ticket", row_key=ROW_KEY, title="fine")]
    outcome, _, gateway = _run(bad, good)
    assert outcome.status == "submitted"
    retry = gateway.seen[1][-1].content[0]
    assert isinstance(retry, ToolResultBlock) and retry.is_error and "title" in retry.content
    outcome, trace, _ = _run(bad, bad)
    assert outcome.status == "schema_error" and "title" in outcome.message
    assert _kinds(trace).count("decision") == 2


def test_f12_fr04_a_model_that_stops_without_submitting_is_a_result_not_a_crash() -> None:
    outcome, trace, _ = _run([TextBlock(text="I think it is fine.")])
    assert outcome.status == "no_submission"
    assert trace.steps[-1]["step_type"] == "decision"


def test_f12_fr05_prompt_files_load_and_render_strictly() -> None:
    prompt = load_prompt("air_gap", "v1")
    assert "read-only" in prompt.system.lower() or "only **read**" in prompt.system
    assert "Cite only evidence" in prompt.system
    for field in ("row_key", "title", "summary", "evidence", "hours_in_gap", "open_deviations"):
        assert f"`{field}`" in prompt.system
    for field in ("recommended_action", "priority", "recipient_role"):
        assert f"`{field}`" in prompt.system
    text = prompt.render_user(
        row_key=ROW_KEY, batch_no="B5003", material_no="RM10067", air_gap_hours=30,
        threshold_hours=24, high_priority_days=14, today="2026-10-12",
    )  # fmt: skip
    assert "B5003" in text and "14 days" in text and "2026-10-12" in text
    with pytest.raises(Exception, match="undefined"):
        prompt.render_user(row_key="x")
