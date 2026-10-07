"""The generic agent loop (F12-FR-04, F12-FR-05): build messages, call the model, run its tool calls, repeat.

It ends when the model calls the **output tool** with valid input, when it has made more than
``MAX_TOOL_CALLS`` tool calls (the run is aborted and the trace says so), or when the model stops without
submitting. Every step is traced as it happens. The loop knows nothing about air gaps: an agent is a prompt, a
tool registry and an output schema, so later agents plug in the same way (T2-03 to T2-05).
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from agents.gateway.base import ModelGateway, Msg, ToolResultBlock, ToolSpec, ToolUseBlock
from agents.harness.trace import TraceSink
from agents.tools.registry import MAX_TOOL_CALLS, ToolRegistry

MAX_SCHEMA_RETRIES = 1  # a malformed submission is sent back once with the error, then the run ends (OQ-145)
Status = Literal["submitted", "tool_limit", "no_submission", "schema_error"]


@dataclass(frozen=True)
class AgentSpec:
    """Everything that makes one agent: who it is, what it says, what it may read and what it must return."""

    key: str
    prompt_version: str
    system: str
    tools: ToolRegistry
    output_tool: ToolSpec
    output_model: type[BaseModel]


@dataclass
class RunOutcome:
    status: Status
    output: BaseModel | None = None
    message: str = ""
    tool_calls: int = 0
    systems_read: list[str] = field(default_factory=list)


def _result_text(value: str) -> Any:
    try:
        return json.loads(value)
    except ValueError:
        return value


def run_agent(
    spec: AgentSpec,
    gateway: ModelGateway,
    trace: TraceSink,
    *,
    user_message: str,
    input_payload: dict[str, Any],
    demo_user: str | None,
    max_tool_calls: int = MAX_TOOL_CALLS,
) -> RunOutcome:
    trace.step("input", input_payload)
    messages = [Msg.user(user_message)]
    tools = [*spec.tools.specs(), spec.output_tool]
    outcome = RunOutcome(status="no_submission")
    schema_failures = 0
    for turn in range(1, max_tool_calls + 4):
        result = gateway.complete(
            system=spec.system,
            messages=messages,
            tools=tools,
            trace=trace,
            turn=turn,
            agent_key=spec.key,
            prompt_version=spec.prompt_version,
        )
        messages.append(Msg(role="assistant", content=result.content))
        uses = result.tool_uses()
        if not uses:
            outcome.message = "the model stopped without submitting an answer"
            trace.step("decision", {"outcome": "no_submission", "stop_reason": result.stop_reason})
            return outcome
        answers: list[ToolResultBlock] = []
        for use in uses:
            if use.name == spec.output_tool.name:
                try:
                    outcome.output = spec.output_model.model_validate(use.input)
                except ValidationError as error:
                    schema_failures += 1
                    problems = _problems(error)
                    trace.step("decision", {"outcome": "schema_error", "problems": problems})
                    if schema_failures > MAX_SCHEMA_RETRIES:
                        outcome.status = "schema_error"
                        outcome.message = "; ".join(problems)
                        return outcome
                    answers.append(
                        ToolResultBlock(
                            tool_use_id=use.id,
                            content="The submission does not match the schema: " + "; ".join(problems),
                            is_error=True,
                        )
                    )
                    continue
                outcome.status = "submitted"
                return outcome
            outcome.tool_calls += 1
            if outcome.tool_calls > max_tool_calls:
                outcome.status = "tool_limit"
                outcome.message = f"aborted: more than {max_tool_calls} tool calls"
                trace.step("decision", {"outcome": "aborted", "reason": outcome.message})
                return outcome
            answers.append(_run_tool(spec, trace, use, outcome, demo_user))
        messages.append(Msg(role="user", content=list(answers)))
    outcome.message = "the model did not submit within the turn limit"
    trace.step("decision", {"outcome": "no_submission", "reason": outcome.message})
    return outcome


def _run_tool(
    spec: AgentSpec, trace: TraceSink, use: ToolUseBlock, outcome: RunOutcome, demo_user: str | None
) -> ToolResultBlock:
    trace.step(
        "tool_call",
        {"tool_use_id": use.id, "name": use.name, "input": use.input, "system": _system(spec, use.name)},
    )
    started = time.perf_counter()
    output = spec.tools.call(use.name, use.input, demo_user)
    latency_ms = round((time.perf_counter() - started) * 1000)
    if output.system not in outcome.systems_read and not output.is_error:
        outcome.systems_read.append(output.system)
    trace.step(
        "tool_result",
        {
            "tool_use_id": use.id,
            "name": use.name,
            "system": output.system,
            "is_error": output.is_error,
            "result": _result_text(output.content),
        },
        latency_ms=latency_ms,
    )
    return ToolResultBlock(tool_use_id=use.id, content=output.content, is_error=output.is_error)


def _system(spec: AgentSpec, name: str) -> str:
    return spec.tools.system_of(name) if name in spec.tools.names() else "none"


def _problems(error: ValidationError) -> list[str]:
    return [f"{'.'.join(str(p) for p in e['loc']) or 'output'}: {e['msg']}" for e in error.errors()]
