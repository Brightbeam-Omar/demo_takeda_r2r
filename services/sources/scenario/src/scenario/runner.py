"""Running a step (F13-FR-03, FR-07, FR-08): preconditions, then the actions in order, with progress lines.

``Runner.start`` checks the preconditions at once (a failure is an error the caller can show), then runs the
actions on a thread. Every progress line is kept in the run, so a browser that subscribes late still sees
the lines it missed (OQ-147). One run at a time: a second request, or a reset, is refused (OQ-150).
"""

import json
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Engine, text

from scenario.clock_api import advance_hours
from scenario.gateway import CallFailed, Gateway
from scenario.lookups import check_precondition, resolve_var
from scenario.pipeline_api import DagsterClient, wait_for_run
from scenario.steps import DEFAULT_USER, Action, Step, StepError, fill

SYNC_TIMEOUT_SECONDS = 120  # F13-FR-08
PIPELINE_TIMEOUT_SECONDS = 300
SYSTEM_ACTOR = "system"  # the audit actor of `make scenario` runs (OQ-054); it is not an app user


class Busy(Exception):
    """Another step or a reset is running."""


class UnknownStep(Exception):
    pass


class PreconditionFailed(Exception):
    def __init__(self, messages: list[str]) -> None:
        super().__init__("; ".join(messages))
        self.messages = messages


@dataclass
class Run:
    id: str
    kind: str  # "step" or "reset"
    name: str
    actor: str
    status: str = "running"  # running, succeeded, failed
    events: list[dict[str, Any]] = field(default_factory=list)
    changed: threading.Condition = field(default_factory=threading.Condition)
    started: float = field(default_factory=time.perf_counter)

    def emit(self, kind: str, message: str, **extra: Any) -> None:
        """Append one progress line. ``elapsed_ms`` is infrastructure time, not demo time."""
        with self.changed:
            self.events.append(
                {
                    "seq": len(self.events),
                    "kind": kind,
                    "message": message,
                    "elapsed_ms": round((time.perf_counter() - self.started) * 1000),
                    **extra,
                }
            )
            self.changed.notify_all()

    def finish(self, status: str, message: str) -> None:
        with (
            self.changed
        ):  # one hold of the lock (it is re-entrant), so a reader never sees the status without the line
            self.status = status
            self.emit("done" if status == "succeeded" else "failed", message, status=status)

    def wait_for_events(self, after: int, timeout: float) -> list[dict[str, Any]]:
        """The events with ``seq >= after``; waits up to ``timeout`` seconds when there are none yet."""
        with self.changed:
            if len(self.events) <= after and self.status == "running":
                self.changed.wait(timeout)
            return list(self.events[after:])


def write_audit(engine: Engine, at: Any, actor: str, action: str, details: dict[str, Any]) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO audit_event (at, actor_user_key, action, details_json) "
                "VALUES (:at, :actor, :action, CAST(:details AS jsonb))"
            ),
            {"at": at, "actor": actor, "action": action, "details": json.dumps(details)},
        )


class RunRegistry:
    """The runs of this process and the one-at-a-time lock."""

    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}
        self._lock = threading.Lock()
        self.active: Run | None = None

    def begin(self, kind: str, name: str, actor: str) -> Run:
        with self._lock:
            if self.active is not None and self.active.status == "running":
                raise Busy(f"{self.active.kind} {self.active.name} is running")
            run = Run(id=uuid.uuid4().hex[:8], kind=kind, name=name, actor=actor)
            self._runs[run.id] = run
            self.active = run
            return run

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)


@dataclass
class Context:
    """What the actions of one run share."""

    variables: dict[str, Any] = field(default_factory=dict)
    pipeline_run_id: str | None = None


class Runner:
    def __init__(
        self,
        steps: list[Step],
        gateway: Gateway,
        engine: Engine,
        dagster: Callable[[], DagsterClient],
        registry: RunRegistry,
        now: Callable[[], Any],
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.steps = {step.id: step for step in steps}
        self.gateway = gateway
        self.engine = engine
        self.dagster = dagster
        self.registry = registry
        self.now = now
        self.sleep = sleep

    # --- the step list and the checks -----------------------------------------------------------

    def listing(self) -> list[dict[str, Any]]:
        """Every step with its precondition status (F13-FR-03). An unreachable service shows as unknown."""
        listed = []
        for step in self.steps.values():
            try:
                failed = self.failed_preconditions(step)
                status, messages = ("met" if not failed else "unmet"), failed
            except (CallFailed, HTTPException) as error:
                status, messages = "unknown", [str(error)]
            listed.append(
                {
                    "id": step.id,
                    "title": step.title,
                    "talk_track": step.talk_track,
                    "preconditions": status,
                    "messages": messages,
                    "actions": [action.label for action in step.actions],
                }
            )
        return listed

    def failed_preconditions(self, step: Step) -> list[str]:
        messages = (check_precondition(self.gateway, p) for p in step.preconditions)
        return [message for message in messages if message]

    # --- running ------------------------------------------------------------------------------

    def start(self, step_id: str, actor: str = SYSTEM_ACTOR, wait: bool = False) -> Run:
        step = self.steps.get(step_id)
        if step is None:
            raise UnknownStep(step_id)
        run = self.registry.begin("step", step.id, actor)
        try:
            failed = self.failed_preconditions(step)
        except Exception as error:
            run.finish("failed", f"cannot check the preconditions: {error}")
            self._audit(run, step.id, "failed", str(error))
            raise
        if failed:
            run.finish("failed", failed[0])
            self._audit(run, step.id, "precondition_failed", "; ".join(failed))
            raise PreconditionFailed(failed)
        run.emit("start", f"{step.title}", step=step.id, talk_track=step.talk_track)
        thread = threading.Thread(target=self._execute, args=(run, step), name=f"step-{step.id}", daemon=True)
        thread.start()
        if wait:
            thread.join()
        return run

    def _execute(self, run: Run, step: Step) -> None:
        context = Context()
        try:
            for name, spec in step.vars.items():
                context.variables[name] = resolve_var(self.gateway, name, spec)
            for number, action in enumerate(step.actions, start=1):
                run.emit("action_start", f"[{number}/{len(step.actions)}] {action.label}", action=number)
                detail = self._do(run, action, context)
                run.emit("action_done", detail or "done", action=number)
        except (CallFailed, StepError, HTTPException) as error:
            message = error.detail if isinstance(error, HTTPException) else str(error)
            run.finish("failed", f"{step.id} failed: {message}")
            self._audit(run, step.id, "failed", str(message))
            return
        except Exception as error:  # a bug must still end the run, or the page would wait for ever
            run.finish("failed", f"{step.id} failed unexpectedly: {error!r}")
            self._audit(run, step.id, "failed", repr(error))
            return
        run.finish("succeeded", f"{step.id} finished")
        self._audit(run, step.id, "succeeded", "")

    def _audit(self, run: Run, step_id: str, outcome: str, message: str) -> None:
        """F13-FR-07. A failure to audit must not hide the step's own result, so it is only logged."""
        try:
            write_audit(
                self.engine,
                self.now(),
                run.actor,
                "scenario_step",
                {"step_id": step_id, "outcome": outcome, "run_id": run.id, "message": message},
            )
        except Exception as error:
            run.emit("line", f"warning: the audit event could not be written: {error}")

    # --- actions ------------------------------------------------------------------------------

    def _do(self, run: Run, action: Action, context: Context) -> str:
        params = fill(action.params, context.variables)
        if action.kind == "event":
            return self._event(params)
        if action.kind == "clock_advance":
            hours = params["hours"] if "hours" in params else params["days"] * 24
            moment = advance_hours(self.engine, int(hours))
            return f"demo clock is now {moment.isoformat()}"
        if action.kind == "run_pipeline":
            return self._pipeline(run, context)
        if action.kind == "wait_sync":
            return self._wait_sync(run, context)
        return self._agent(params)

    def _event(self, params: dict[str, Any]) -> str:
        service, method, path = params["service"], params.get("method", "POST"), params["path"]
        user = params.get("as_user", DEFAULT_USER if service == "app" else None)
        self.gateway.call(service, method, path, body=params.get("body"), user=user)
        return f"{method} {service} {path}{f' (as {user})' if user else ''}: ok"

    def _pipeline(self, run: Run, context: Context) -> str:
        client = self.dagster()
        run_id = client.launch()
        run.emit("line", f"Dagster run {run_id} started")
        status = wait_for_run(client, run_id, PIPELINE_TIMEOUT_SECONDS, self.sleep)
        if status != "SUCCESS":
            raise CallFailed(f"the pipeline run {run_id} ended {status}")
        context.pipeline_run_id = run_id
        return f"pipeline run {run_id} succeeded"

    def _wait_sync(self, run: Run, context: Context) -> str:
        if context.pipeline_run_id is None:
            raise StepError("wait_sync needs a run_pipeline action before it in the same step")
        wait_for_sync(self.gateway, context.pipeline_run_id, self.sleep, SYNC_TIMEOUT_SECONDS)
        return f"the app has synced run {context.pipeline_run_id}"

    def _agent(self, params: dict[str, Any]) -> str:
        user = params.get("as_user", DEFAULT_USER)
        answer = self.gateway.call("agents", "POST", "/agents/air_gap/run", body={}, user=user)
        return f"{len(answer['created'])} proposal(s) created, {len(answer['skipped'])} skipped (as {user})"


def wait_for_sync(
    gateway: Gateway, run_id: str, sleep: Callable[[float], None], timeout_seconds: float
) -> None:
    """F13-FR-08 (OQ-151): every watermark is at ``run_id`` and no sync event is pending or claimed."""
    waited = 0.0
    behind: list[str] = ["no watermarks yet"]
    while waited <= timeout_seconds:
        status = gateway.call("app", "GET", "/api/sync/status", user=DEFAULT_USER)
        behind = [m["object_name"] for m in status["watermarks"] if m["run_id"] != run_id]
        busy = [e for e in status["events"] if e["status"] in ("pending", "claimed")]
        if status["watermarks"] and not behind and not busy:
            return
        sleep(1.0)
        waited += 1.0
    still = ", ".join(behind) or "a pending event"
    raise CallFailed(
        f"the app did not sync run {run_id} within {int(timeout_seconds)} s; still behind: {still}"
    )
