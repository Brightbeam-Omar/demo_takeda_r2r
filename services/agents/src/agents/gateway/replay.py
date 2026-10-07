"""Replay and recording (F12-FR-03, OQ-139): the demo runs offline from recorded model answers.

One key per model call: ``sha256`` of the agent, the prompt version, the turn, the system prompt, the tool
specs and the message list so far. The messages already hold the candidate facts and every earlier tool
result, so a recording is only found for the exact situation it was made in. A run is therefore a short chain
of files, ``recordings/<agent>/<key>.json``, one per model call.

A miss raises ``ReplayMiss``, which names the key and says what to do; the API turns it into a clear message.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from r2r_core import clock

from agents.gateway.base import Block, ModelGateway, ModelResult, Msg, ToolSpec
from agents.gateway.recording_schema import RecordedCall

HINT = (
    "Recordings exist only for the demo-start state (canonical seed, clock at the opening time). "
    "Run `make demo-reset` and `make record-agents` to record this situation, or use LLM_PROVIDER=anthropic."
)


class ReplayMiss(Exception):
    """No recording matches this model call."""

    def __init__(self, key: str, agent_key: str, turn: int) -> None:
        self.key = key
        self.agent_key = agent_key
        self.turn = turn
        self.hint = HINT
        super().__init__(
            f"No recording for key {key} (agent {agent_key}, model call {turn}). "
            f"{HINT} Command: make record-agents"
        )


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def replay_key(
    *,
    agent_key: str,
    prompt_version: str,
    turn: int,
    system: str,
    tools: list[ToolSpec] | None,
    messages: list[Msg],
) -> str:
    payload = {
        "agent_key": agent_key,
        "prompt_version": prompt_version,
        "turn": turn,
        "system": system,
        "tools": [t.model_dump(mode="json") for t in tools or []],
        "messages": [m.model_dump(mode="json") for m in messages],
    }
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def recording_path(directory: Path, agent_key: str, key: str) -> Path:
    return directory / agent_key / f"{key}.json"


class ReplayGateway(ModelGateway):
    provider = "replay"

    def __init__(self, directory: Path, model_id: str = "replay") -> None:
        self.directory = directory
        self.model_id = model_id

    def generate(
        self,
        *,
        system: str,
        messages: list[Msg],
        tools: list[ToolSpec] | None,
        turn: int,
        agent_key: str,
        prompt_version: str,
    ) -> ModelResult:
        key = replay_key(
            agent_key=agent_key,
            prompt_version=prompt_version,
            turn=turn,
            system=system,
            tools=tools,
            messages=messages,
        )
        path = recording_path(self.directory, agent_key, key)
        if not path.is_file():
            raise ReplayMiss(key, agent_key, turn)
        recorded = RecordedCall.model_validate_json(path.read_text())
        return ModelResult(
            content=list[Block](recorded.content),
            stop_reason=recorded.stop_reason,
            tokens_in=recorded.tokens_in,
            tokens_out=recorded.tokens_out,
            latency_ms=recorded.latency_ms,
            model_id=recorded.model_id,
            replayed=True,
        )


class RecordingGateway(ModelGateway):
    """Wraps a live provider and writes every answer to the recordings folder (``make record-agents``)."""

    def __init__(self, inner: ModelGateway, directory: Path) -> None:
        self.inner = inner
        self.directory = directory
        self.provider = inner.provider
        self.model_id = inner.model_id

    def generate(
        self,
        *,
        system: str,
        messages: list[Msg],
        tools: list[ToolSpec] | None,
        turn: int,
        agent_key: str,
        prompt_version: str,
    ) -> ModelResult:
        result = self.inner.generate(
            system=system,
            messages=messages,
            tools=tools,
            turn=turn,
            agent_key=agent_key,
            prompt_version=prompt_version,
        )
        key = replay_key(
            agent_key=agent_key,
            prompt_version=prompt_version,
            turn=turn,
            system=system,
            tools=tools,
            messages=messages,
        )
        recorded = RecordedCall(
            key=key,
            agent_key=agent_key,
            prompt_version=prompt_version,
            turn=turn,
            model_id=result.model_id,
            recorded_at=clock.now().isoformat(),
            stop_reason=result.stop_reason,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            latency_ms=result.latency_ms,
            content=result.content,
        )
        path = recording_path(self.directory, agent_key, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(recorded.model_dump_json(indent=2) + "\n")
        return result


def clear_recordings(directory: Path, agent_key: str) -> int:
    """Delete one agent's recordings, so a re-record leaves no stale file. Returns the count."""
    folder = directory / agent_key
    files = sorted(folder.glob("*.json")) if folder.is_dir() else []
    for file in files:
        file.unlink()
    return len(files)
