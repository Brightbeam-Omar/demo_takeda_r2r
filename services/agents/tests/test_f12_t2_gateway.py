"""F12 T2: the trace store, the gateway base and the anthropic provider [F12-FR-02, OQ-146]."""

import json
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
import pytest
from agent_support import ListTrace
from agents.gateway import build_gateway
from agents.gateway.anthropic import AnthropicGateway
from agents.gateway.base import GatewayError, Msg, ToolSpec
from agents.harness.trace import Trace, new_trace_id, read_trace
from agents.settings import Settings
from sqlalchemy import Engine

SENTINEL_KEY = "sk-ant-test-sentinel-0123456789"


class FakeMessages:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.requests: list[dict[str, Any]] = []
        self.response = response
        self.error = error

    def create(self, **request: Any) -> Any:
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.response


def _response() -> Any:
    return SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="Checking the lot."),
            SimpleNamespace(type="tool_use", id="toolu_1", name="get_row", input={"row_key": "r1"}),
        ],
        stop_reason="tool_use",
        usage=SimpleNamespace(input_tokens=120, output_tokens=33),
        model="claude-sonnet-5-5",
    )


def _gateway(messages: FakeMessages) -> AnthropicGateway:
    return AnthropicGateway("claude-sonnet-5-5", client=SimpleNamespace(messages=messages))


TOOL = ToolSpec(name="get_row", description="read a row", input_schema={"type": "object"})


def test_f12_fr02_request_uses_the_fixed_settings_and_tool_use() -> None:
    messages = FakeMessages(_response())
    trace = ListTrace()
    result = _gateway(messages).complete(
        system="be careful",
        messages=[Msg.user("hello")],
        tools=[TOOL],
        trace=trace,
        turn=1,
        agent_key="air_gap",
        prompt_version="v1",
    )
    request = messages.requests[0]
    assert (request["model"], request["max_tokens"]) == ("claude-sonnet-5-5", 1500)
    assert "temperature" not in request  # the SDK has no such parameter for this model (plan.md, Deviations)
    assert request["system"] == "be careful"
    assert request["messages"] == [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
    assert request["tools"] == [
        {"name": "get_row", "description": "read a row", "input_schema": {"type": "object"}}
    ]
    assert result.stop_reason == "tool_use"
    assert [(u.name, u.input) for u in result.tool_uses()] == [("get_row", {"row_key": "r1"})]
    assert (result.tokens_in, result.tokens_out) == (120, 33)


def test_f12_fr02_every_call_traces_request_and_response_with_tokens_and_latency() -> None:
    trace = ListTrace()
    _gateway(FakeMessages(_response())).complete(
        system="s",
        messages=[Msg.user("hi")],
        tools=None,
        trace=trace,
        turn=1,
        agent_key="air_gap",
        prompt_version="v1",
    )
    request, response = trace.steps
    assert request["step_type"] == "model_request"
    assert request["payload"]["model_id"] == "claude-sonnet-5-5"  # type: ignore[index]
    assert response["step_type"] == "model_response"
    assert (response["tokens_in"], response["tokens_out"]) == (120, 33)
    assert isinstance(response["latency_ms"], int)


def test_f12_fr02_a_provider_error_is_traced_and_raised_without_details() -> None:
    boom = anthropic.APIConnectionError(request=httpx.Request("POST", "https://x.test"))
    trace = ListTrace()
    with pytest.raises(GatewayError, match="APIConnectionError"):
        _gateway(FakeMessages(error=boom)).complete(
            system="s",
            messages=[Msg.user("hi")],
            tools=None,
            trace=trace,
            turn=1,
            agent_key="air_gap",
            prompt_version="v1",
        )
    assert [s["step_type"] for s in trace.steps] == ["model_request", "model_response"]
    assert trace.steps[1]["payload"]["error"] == "GatewayError"  # type: ignore[index]


def test_f12_fr02_missing_key_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(GatewayError, match="ANTHROPIC_API_KEY"):
        AnthropicGateway("claude-sonnet-5-5")


def test_f12_fr02_bedrock_is_a_stub_and_unknown_providers_are_refused() -> None:
    gateway = build_gateway(Settings.from_env({"LLM_PROVIDER": "bedrock"}))
    with pytest.raises(GatewayError, match="T2-10"):
        gateway.complete(
            system="s",
            messages=[Msg.user("hi")],
            tools=None,
            trace=ListTrace(),
            turn=1,
            agent_key="air_gap",
            prompt_version="v1",
        )
    with pytest.raises(GatewayError, match="unknown LLM_PROVIDER"):
        build_gateway(Settings.from_env({"LLM_PROVIDER": "nope"}))


def test_f12_oq146_the_key_is_not_in_the_request_the_trace_or_the_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OQ-146: the key reaches the SDK client only; nothing the gateway writes contains it."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", SENTINEL_KEY)
    captured: dict[str, Any] = {}

    def fake_client(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return SimpleNamespace(
            messages=FakeMessages(
                error=anthropic.APIConnectionError(
                    request=httpx.Request("POST", f"https://x.test/?k={SENTINEL_KEY}")
                )
            )
        )

    monkeypatch.setattr(anthropic, "Anthropic", fake_client)
    gateway = AnthropicGateway("claude-sonnet-5-5")
    assert (
        captured["api_key"] == SENTINEL_KEY and captured["max_retries"] == 2 and captured["timeout"] == 60.0
    )
    trace = ListTrace()
    with pytest.raises(GatewayError) as raised:
        gateway.complete(
            system="s",
            messages=[Msg.user("hi")],
            tools=None,
            trace=trace,
            turn=1,
            agent_key="air_gap",
            prompt_version="v1",
        )
    assert SENTINEL_KEY not in str(raised.value)
    assert SENTINEL_KEY not in json.dumps(trace.steps, default=str)
    assert SENTINEL_KEY not in repr(gateway.__dict__.get("model_id"))


@pytest.mark.integration
def test_f12_fr02_trace_ids_come_from_a_sequence_and_steps_keep_their_order(agents_engine: Engine) -> None:
    assert [new_trace_id(agents_engine), new_trace_id(agents_engine)] == ["TR-0001", "TR-0002"]
    trace = Trace(agents_engine, "TR-0001")
    trace.step("input", {"row_key": "r1"})
    trace.step("tool_call", {"name": "get_row"})
    trace.step("model_response", {"x": 1}, tokens_in=5, tokens_out=6, latency_ms=7)
    rows = read_trace(agents_engine, "TR-0001")
    assert [(r["seq"], r["step_type"]) for r in rows] == [
        (1, "input"),
        (2, "tool_call"),
        (3, "model_response"),
    ]
    assert (rows[2]["tokens_in"], rows[2]["tokens_out"], rows[2]["latency_ms"]) == (5, 6, 7)
    with pytest.raises(ValueError, match="unknown trace step"):
        trace.step("nonsense", {})
