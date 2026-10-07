"""The recording file format: the model's answer plus metadata. The metadata is not part of the key."""

from pydantic import BaseModel

from agents.gateway.base import Block


class RecordedCall(BaseModel):
    key: str
    agent_key: str
    prompt_version: str
    turn: int
    model_id: str
    recorded_at: str
    stop_reason: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    content: list[Block]
