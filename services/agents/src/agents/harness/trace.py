"""The trace store (F12-FR-02, constitution P3): each step of a run is written to ``agent_trace`` at once.

Each step commits on its own, so a run that fails halfway (a replay miss, a refused tool call) still leaves
its trace to read. ``at`` is the demo clock, which does not tick, so the order of steps is ``seq``; latency is
measured with a monotonic timer and stored per step.
"""

from collections.abc import Mapping
from typing import Any, Protocol

from r2r_core import clock
from sqlalchemy import Engine, func, insert, select, text

from agents.db import agent_trace

STEP_TYPES = (
    "input",
    "tool_call",
    "tool_result",
    "model_request",
    "model_response",
    "validation",
    "decision",
    "action",
)


class TraceSink(Protocol):
    """What the gateway and the runner need from a trace: append a step."""

    trace_id: str

    def step(
        self,
        step_type: str,
        payload: Mapping[str, Any],
        *,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        latency_ms: int | None = None,
    ) -> int: ...


class MemoryTrace:
    """A trace kept in memory: for the recorder, which must leave no rows behind in the database."""

    def __init__(self, trace_id: str = "TR-REC") -> None:
        self.trace_id = trace_id
        self.steps: list[dict[str, Any]] = []

    def step(
        self,
        step_type: str,
        payload: Mapping[str, Any],
        *,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        latency_ms: int | None = None,
    ) -> int:
        self.steps.append(
            {
                "step_type": step_type,
                "payload": dict(payload),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "latency_ms": latency_ms,
            }
        )
        return len(self.steps)


def new_trace_id(engine: Engine) -> str:
    """``TR-0001``, ``TR-0002`` … from the sequence the demo reset restarts (OQ-144)."""
    with engine.begin() as connection:
        number = connection.execute(text("SELECT nextval('agent_trace_seq')")).scalar_one()
    return f"TR-{number:04d}"


class Trace:
    """Appends steps to one trace in the database."""

    def __init__(self, engine: Engine, trace_id: str, start_seq: int = 0) -> None:
        self.engine = engine
        self.trace_id = trace_id
        self._seq = start_seq

    @classmethod
    def resume(cls, engine: Engine, trace_id: str) -> "Trace":
        """Continue an existing trace (the human decision is appended to the run's trace)."""
        with engine.connect() as connection:
            last = connection.execute(
                select(func.coalesce(func.max(agent_trace.c.seq), 0)).where(
                    agent_trace.c.trace_id == trace_id
                )
            ).scalar_one()
        return cls(engine, trace_id, last)

    def step(
        self,
        step_type: str,
        payload: Mapping[str, Any],
        *,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        latency_ms: int | None = None,
    ) -> int:
        if step_type not in STEP_TYPES:
            raise ValueError(f"unknown trace step type {step_type!r}")
        self._seq += 1
        with self.engine.begin() as connection:
            connection.execute(
                insert(agent_trace).values(
                    trace_id=self.trace_id,
                    seq=self._seq,
                    step_type=step_type,
                    payload_json=dict(payload),
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    latency_ms=latency_ms,
                    at=clock.now(),
                )
            )
        return self._seq


def read_trace(engine: Engine, trace_id: str) -> list[dict[str, Any]]:
    """All steps of a trace in order."""
    with engine.connect() as connection:
        rows = connection.execute(
            select(agent_trace).where(agent_trace.c.trace_id == trace_id).order_by(agent_trace.c.seq)
        ).mappings()
        return [dict(row) for row in rows]
