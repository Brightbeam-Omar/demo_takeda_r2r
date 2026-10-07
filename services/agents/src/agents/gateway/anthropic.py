"""The ``anthropic`` provider: the official SDK with tool use (1500 tokens, 60 s, 2 retries).

There is no ``temperature``: the SDK has none for this model (plan.md, Deviations).

The key is read from ``ANTHROPIC_API_KEY`` when the provider is built and handed straight to the SDK client.
It is never copied into a message, a trace, a recording, an error text or a log line (OQ-146).
"""

import os
import time
from typing import Any

import anthropic

from agents.gateway.base import (
    MAX_TOKENS,
    RETRIES,
    TIMEOUT_SECONDS,
    GatewayError,
    ModelGateway,
    ModelResult,
    Msg,
    TextBlock,
    ToolSpec,
    ToolUseBlock,
)


class AnthropicGateway(ModelGateway):
    provider = "anthropic"

    def __init__(self, model_id: str, client: Any | None = None) -> None:
        self.model_id = model_id
        if client is None:
            key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not key:
                raise GatewayError("LLM_PROVIDER=anthropic needs ANTHROPIC_API_KEY in the environment")
            client = anthropic.Anthropic(api_key=key, timeout=TIMEOUT_SECONDS, max_retries=RETRIES)
        self._client = client

    def generate(
        self, *, system: str, messages: list[Msg], tools: list[ToolSpec] | None, turn: int
    ) -> ModelResult:
        request: dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": MAX_TOKENS,
            "system": system,
            "messages": [m.model_dump(mode="json", exclude_none=True) for m in messages],
        }
        if tools:
            request["tools"] = [t.model_dump(mode="json") for t in tools]
        started = time.perf_counter()
        try:
            response = self._client.messages.create(**request)
        except anthropic.APIError as error:
            # Only the class and the status: the SDK's text can echo request details.
            status = getattr(error, "status_code", None)
            raise GatewayError(f"the model call failed ({type(error).__name__}, status {status})") from None
        latency_ms = round((time.perf_counter() - started) * 1000)
        content: list[TextBlock | ToolUseBlock] = []
        for block in response.content:
            if block.type == "text":
                content.append(TextBlock(text=block.text))
            elif block.type == "tool_use":
                content.append(ToolUseBlock(id=block.id, name=block.name, input=dict(block.input)))
        return ModelResult(
            content=list(content),
            stop_reason=str(response.stop_reason),
            tokens_in=int(response.usage.input_tokens),
            tokens_out=int(response.usage.output_tokens),
            latency_ms=latency_ms,
            model_id=str(response.model),
        )
