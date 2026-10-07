"""``ModelGateway`` (02-architecture section 4): one interface over the model providers.

Messages use one provider-neutral shape (the same content blocks the Anthropic API uses). A provider only
implements ``generate``; ``complete`` wraps it so that every call writes the ``model_request`` and
``model_response`` trace steps, with tokens and latency, whatever the provider.
"""

import time
from abc import ABC, abstractmethod
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from agents.harness.trace import TraceSink

MAX_TOKENS = 1500
TIMEOUT_SECONDS = 60.0
RETRIES = 2


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class ToolResultBlock(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str
    is_error: bool = False


Block = Annotated[TextBlock | ToolUseBlock | ToolResultBlock, Field(discriminator="type")]


class Msg(BaseModel):
    role: Literal["user", "assistant"]
    content: list[Block]

    @classmethod
    def user(cls, text: str) -> "Msg":
        return cls(role="user", content=[TextBlock(text=text)])


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class ModelResult(BaseModel):
    content: list[Block]
    stop_reason: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    model_id: str
    replayed: bool = (
        False  # True when the answer came from a recording (tokens and latency are the recorded ones)
    )

    def tool_uses(self) -> list[ToolUseBlock]:
        return [block for block in self.content if isinstance(block, ToolUseBlock)]


class GatewayError(Exception):
    """A provider failed (network, auth, rate limit, bad request). The message never contains credentials."""


class ModelGateway(ABC):
    """Base class: ``complete`` traces, ``generate`` talks to the provider."""

    provider: str
    model_id: str

    @abstractmethod
    def generate(
        self,
        *,
        system: str,
        messages: list[Msg],
        tools: list[ToolSpec] | None,
        turn: int,
        agent_key: str,
        prompt_version: str,
    ) -> ModelResult: ...

    def complete(
        self,
        *,
        system: str,
        messages: list[Msg],
        tools: list[ToolSpec] | None,
        trace: TraceSink,
        turn: int,
        agent_key: str,
        prompt_version: str,
    ) -> ModelResult:
        trace.step(
            "model_request",
            {
                "provider": self.provider,
                "model_id": self.model_id,
                "turn": turn,
                "agent_key": agent_key,
                "prompt_version": prompt_version,
                "max_tokens": MAX_TOKENS,
                "system": system,
                "messages": [m.model_dump(mode="json") for m in messages],
                "tools": [t.name for t in tools or []],
            },
        )
        started = time.perf_counter()
        try:
            result = self.generate(
                system=system,
                messages=messages,
                tools=tools,
                turn=turn,
                agent_key=agent_key,
                prompt_version=prompt_version,
            )
        except Exception as error:
            trace.step(
                "model_response",
                {"error": type(error).__name__, "message": str(error)},
                latency_ms=round((time.perf_counter() - started) * 1000),
            )
            raise
        trace.step(
            "model_response",
            {
                "content": [b.model_dump(mode="json") for b in result.content],
                "stop_reason": result.stop_reason,
                "model_id": result.model_id,
                "provider": self.provider,
                "replayed": result.replayed,
            },
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            latency_ms=result.latency_ms,
        )
        return result
